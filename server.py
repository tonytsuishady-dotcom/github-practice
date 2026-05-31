from __future__ import annotations

import json
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from codex_usage import get_last_error, read_codex_rate_limits


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
                        "detail": get_last_error(),
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


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 3000), SpiritHandler)
    print("Codex 灵兽小筑 demo: http://127.0.0.1:3000")
    server.serve_forever()
