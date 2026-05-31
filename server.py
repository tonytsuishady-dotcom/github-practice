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
    codex = shutil.which("codex")
    if not codex:
        return None

    proc: subprocess.Popen[str] | None = None
    try:
        proc = subprocess.Popen(
            [codex, "-s", "read-only", "-a", "untrusted", "app-server"],
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
            return None

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
            return None
        return normalize_rate_limits(rate_limits, account)
    except (OSError, subprocess.SubprocessError, TimeoutError, BrokenPipeError):
        return None
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()


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
        "email": account.get("email"),
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
