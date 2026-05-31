from __future__ import annotations

import json
import queue
import re
import shutil
import subprocess
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
INBOX = ROOT / "pet-inbox"
LAST_RATE_LIMIT_ERROR = "Not checked yet."


class SpiritHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/rate-limits":
            snapshot = read_codex_rate_limits()
            if snapshot:
                self.send_json(snapshot)
            else:
                self.send_json(
                    {
                        "source": "demo",
                        "message": "Codex app-server unavailable; using demo values.",
                        "detail": LAST_RATE_LIMIT_ERROR,
                    },
                    status=202,
                )
            return
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/feed":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            markdown = str(payload.get("markdown", "")).strip()
            file_name = sanitize(str(payload.get("fileName", "spirit-material")))
            created_at = str(payload.get("createdAt", ""))
            if not markdown:
                raise ValueError("markdown is required")

            INBOX.mkdir(exist_ok=True)
            stamp = stamp_from_iso(created_at)
            target = unique_path(INBOX / f"{stamp}-{file_name}.md")
            target.write_text(markdown + "\n", encoding="utf-8")
            self.send_json({"savedPath": str(target.relative_to(ROOT)).replace("\\", "/")})
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=400)

    def send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def sanitize(name: str) -> str:
    name = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "-", name, flags=re.UNICODE).strip("-")
    return name[:80] or "spirit-material"


def stamp_from_iso(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) >= 14:
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}-{digits[8:14]}"
    return "undated"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(2, 1000):
        candidate = path.with_name(f"{stem}-{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError("too many duplicate feed records")


def read_codex_rate_limits() -> dict | None:
    global LAST_RATE_LIMIT_ERROR
    codex = find_codex_executable()
    if not codex:
        LAST_RATE_LIMIT_ERROR = "codex executable was not found via PATH, Get-AppxPackage, or WindowsApps scan."
        return None

    attempts = [
        [codex, "app-server", "--stdio"],
        [codex, "app-server", "--listen", "stdio://"],
        [codex, "app-server"],
        [codex, "-s", "read-only", "-a", "untrusted", "app-server"],
    ]
    errors = []
    for command in attempts:
        snapshot, error = read_codex_rate_limits_with_command(command)
        if snapshot:
            LAST_RATE_LIMIT_ERROR = ""
            return snapshot
        errors.append(error)
    LAST_RATE_LIMIT_ERROR = " | ".join(error for error in errors if error)
    return None


def find_codex_executable() -> str | None:
    local_cli = find_local_codex_cli()
    if local_cli:
        return str(local_cli)

    from_path = shutil.which("codex")
    if from_path:
        path = Path(from_path)
        exe_sibling = path.with_name(path.name + ".exe")
        if path.suffix.lower() != ".exe" and exe_sibling.exists():
            return str(exe_sibling)
        return from_path

    appx_location = find_codex_appx_location()
    if appx_location:
        for rel in ("app/resources/codex.exe", "codex.exe", "app/resources/codex", "codex"):
            candidate = appx_location / rel
            if candidate.exists():
                return str(candidate)

    roots = [
        Path.home() / "AppData" / "Local" / "Microsoft" / "WindowsApps",
        Path("C:/Program Files/WindowsApps"),
    ]
    candidates: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        try:
            candidates.extend(root.glob("OpenAI.Codex_*/*/resources/codex.exe"))
            candidates.extend(root.glob("OpenAI.Codex_*/app/resources/codex.exe"))
            candidates.extend(root.glob("OpenAI.Codex_*/codex.exe"))
            candidates.extend(root.glob("OpenAI.Codex_*/*/resources/codex"))
            candidates.extend(root.glob("OpenAI.Codex_*/app/resources/codex"))
            candidates.extend(root.glob("OpenAI.Codex_*/codex"))
        except OSError:
            continue

    existing = [path for path in candidates if path.exists()]
    if not existing:
        return None
    existing.sort(key=lambda path: (path.suffix.lower() != ".exe", -path.stat().st_mtime))
    return str(existing[0])


def find_local_codex_cli() -> Path | None:
    root = Path.home() / "AppData" / "Local" / "OpenAI" / "Codex" / "bin"
    if not root.exists():
        return None
    try:
        candidates = list(root.glob("*/codex.exe"))
    except OSError:
        return None
    existing = [path for path in candidates if path.exists()]
    if not existing:
        return None
    existing.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return existing[0]


def find_codex_appx_location() -> Path | None:
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-AppxPackage OpenAI.Codex | Select-Object -First 1 -ExpandProperty InstallLocation)",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    location = completed.stdout.strip().splitlines()
    if completed.returncode != 0 or not location:
        return None
    path = Path(location[0].strip())
    return path if path.exists() else None


def read_codex_rate_limits_with_command(command: list[str]) -> tuple[dict | None, str]:
    proc: subprocess.Popen[str] | None = None
    label = " ".join(command[1:]) or "codex"
    try:
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        stdout_queue = start_stdout_reader(proc)
        initialized = rpc_request(
            proc,
            stdout_queue,
            {
                "method": "initialize",
                "id": 1,
                "params": {
                    "clientInfo": {
                        "name": "codex-spirit-companion",
                        "title": "Codex Spirit Companion",
                        "version": "0.1.0",
                    },
                    "capabilities": {"experimentalApi": True},
                },
            },
            expected_id=1,
            timeout=6,
        )
        if not initialized or "error" in initialized:
            return None, f"{label}: initialize failed {compact_message(initialized)}"

        write_rpc(proc, {"method": "initialized", "params": {}})
        account = rpc_request(
            proc,
            stdout_queue,
            {"method": "account/read", "id": 2, "params": {"refreshToken": False}},
            expected_id=2,
            timeout=6,
        )
        limits = rpc_request(
            proc,
            stdout_queue,
            {"method": "account/rateLimits/read", "id": 3},
            expected_id=3,
            timeout=10,
        )
        rate_limits = (limits or {}).get("result", {}).get("rateLimits")
        if not isinstance(rate_limits, dict):
            return None, f"{label}: rateLimits response missing {compact_message(limits)}"
        return normalize_rate_limits(rate_limits, account), ""
    except (OSError, subprocess.SubprocessError, TimeoutError, BrokenPipeError) as exc:
        stderr = read_stderr(proc)
        detail = f"{label}: {type(exc).__name__}: {exc}"
        return None, f"{detail}; stderr={stderr}" if stderr else detail
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()


def read_stderr(proc: subprocess.Popen[str] | None) -> str:
    if not proc or not proc.stderr:
        return ""
    if proc.poll() is None:
        return ""
    try:
        return proc.stderr.read(1000).strip()
    except Exception:
        return ""


def compact_message(message: object) -> str:
    if message is None:
        return "no response"
    text = json.dumps(message, ensure_ascii=False)
    return text[:500]


def write_rpc(proc: subprocess.Popen[str], payload: dict) -> None:
    if not proc.stdin:
        raise BrokenPipeError("codex app-server stdin is closed")
    proc.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
    proc.stdin.flush()


def start_stdout_reader(proc: subprocess.Popen[str]) -> queue.Queue[str]:
    lines: queue.Queue[str] = queue.Queue()

    def read_lines() -> None:
        if not proc.stdout:
            return
        for line in proc.stdout:
            lines.put(line)

    threading.Thread(target=read_lines, daemon=True).start()
    return lines


def rpc_request(
    proc: subprocess.Popen[str],
    stdout_queue: queue.Queue[str],
    payload: dict,
    expected_id: int,
    timeout: float,
) -> dict | None:
    write_rpc(proc, payload)

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = max(0.05, deadline - time.monotonic())
        try:
            line = stdout_queue.get(timeout=min(0.25, remaining))
        except queue.Empty:
            if proc.poll() is not None:
                return None
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if message.get("id") == expected_id:
            return message
    raise TimeoutError(f"timed out waiting for JSON-RPC id {expected_id}")


def normalize_rate_limits(rate_limits: dict, account_response: dict | None) -> dict:
    account = (account_response or {}).get("result", {}).get("account") or {}
    credits = rate_limits.get("credits") if isinstance(rate_limits.get("credits"), dict) else None
    return {
        "source": "codex-app-server",
        "planType": rate_limits.get("planType") or account.get("planType"),
        "primary": normalize_window(rate_limits.get("primary")),
        "secondary": normalize_window(rate_limits.get("secondary")),
        "credits": credits,
        "rateLimitReachedType": rate_limits.get("rateLimitReachedType"),
    }


def normalize_window(window: object) -> dict | None:
    if not isinstance(window, dict):
        return None
    used = float(window.get("usedPercent") or 0)
    resets_at = window.get("resetsAt")
    return {
        "usedPercent": max(0, min(100, round(used, 1))),
        "remainingPercent": max(0, min(100, round(100 - used, 1))),
        "windowDurationMins": window.get("windowDurationMins"),
        "resetsAt": resets_at,
        "resetLabel": format_reset_label(resets_at),
    }


def format_reset_label(value: object) -> str | None:
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None
    return time.strftime("%m月%d日 %H:%M 回转", time.localtime(timestamp))


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 3000), SpiritHandler)
    print("Codex 灵兽小筑 demo: http://127.0.0.1:3000")
    server.serve_forever()
