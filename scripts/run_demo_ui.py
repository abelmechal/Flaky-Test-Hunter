from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from app.demo_ui import fixture_payload, run_demo_diagnosis


UI_DIR = ROOT / "ui"


class DemoHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        print(f"[demo-ui] {format % args}")

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(404)
            return
        body = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route == "/api/fixture":
            self._json(fixture_payload())
            return
        if route.startswith("/files/"):
            relative = unquote(route.removeprefix("/files/"))
            candidate = (ROOT / relative).resolve()
            try:
                candidate.relative_to(ROOT.resolve())
            except ValueError:
                self.send_error(403)
                return
            self._file(candidate)
            return
        if route == "/":
            self._file(UI_DIR / "northstar.html")
            return
        if route == "/triage.html":
            self._file(UI_DIR / "index.html")
            return
        candidate = (UI_DIR / route.lstrip("/")).resolve()
        try:
            candidate.relative_to(UI_DIR.resolve())
        except ValueError:
            self.send_error(403)
            return
        self._file(candidate)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/run":
            self.send_error(404)
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = (
                json.loads(self.rfile.read(content_length))
                if content_length
                else {}
            )
            self._json(
                asyncio.run(run_demo_diagnosis(payload.get("scenario_id")))
            )
        except Exception as exc:
            self._json(
                {
                    "status": "error",
                    "message": f"{type(exc).__name__}: {exc}",
                },
                status=500,
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Flaky-Test Hunter demo UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    server = ThreadingHTTPServer((args.host, args.port), DemoHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"Flaky-Test Hunter demo UI: {url}")
    print("Press Ctrl+C to stop.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping demo UI.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
