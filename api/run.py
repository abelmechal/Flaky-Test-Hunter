from __future__ import annotations

import asyncio
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Vercel functions have writable temporary storage only.
if os.getenv("VERCEL"):
    os.environ.setdefault("SCREENSHOT_DIR", "/tmp/flaky-test-hunter")

from app.demo_ui import run_demo_diagnosis


class handler(BaseHTTPRequestHandler):
    def _json(self, payload: dict, status: int) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = (
                json.loads(self.rfile.read(content_length))
                if content_length
                else {}
            )
            self._json(
                asyncio.run(run_demo_diagnosis(payload.get("scenario_id"))),
                200,
            )
        except Exception as exc:
            self._json(
                {
                    "status": "error",
                    "message": f"{type(exc).__name__}: {exc}",
                },
                500,
            )
