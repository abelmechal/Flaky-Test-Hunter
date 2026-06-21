from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.fix_workflow import execute_fix


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
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length)) if length else {}
            self._json(execute_fix(payload.get("scenario_id", "")), 200)
        except Exception as exc:
            self._json(
                {"status": "error", "message": f"{type(exc).__name__}: {exc}"},
                400,
            )
