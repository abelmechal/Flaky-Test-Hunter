from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

try:
    from redis import Redis
    from redis.exceptions import RedisError
except ImportError:  # Redis remains optional for local contract testing.
    Redis = None

    class RedisError(Exception):
        pass


SEEDED_HISTORY = [
    {"reproduced": True, "timestamp": "2026-06-20T10:00:00Z"},
    {"reproduced": False, "timestamp": "2026-06-20T10:10:00Z"},
    {"reproduced": True, "timestamp": "2026-06-20T10:20:00Z"},
]


class RedisStore:
    """Uses Redis when configured and an in-memory store for local development."""

    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url = redis_url or os.getenv("REDIS_URL")
        self._memory: dict[str, str] = {}
        self._redis = (
            Redis.from_url(self.redis_url, decode_responses=True)
            if self.redis_url and Redis is not None
            else None
        )

    @staticmethod
    def history_key(issue_id: str) -> str:
        return f"issue:{issue_id}:history"

    @staticmethod
    def status_key(issue_id: str) -> str:
        return f"issue:{issue_id}:status"

    @staticmethod
    def session_key(chat_session_id: str) -> str:
        return f"session:{chat_session_id}:context"

    def _set(self, key: str, value: str) -> None:
        if self._redis is not None:
            try:
                self._redis.set(key, value)
                return
            except RedisError:
                pass
        self._memory[key] = value

    def _get(self, key: str) -> str | None:
        if self._redis is not None:
            try:
                return self._redis.get(key)
            except RedisError:
                pass
        return self._memory.get(key)

    def get_history(self, issue_id: str) -> list[dict[str, Any]]:
        raw = self._get(self.history_key(issue_id))
        return json.loads(raw) if raw else []

    def get_status(self, issue_id: str) -> str | None:
        return self._get(self.status_key(issue_id))

    def get_session_context(self, chat_session_id: str) -> dict[str, Any] | None:
        raw = self._get(self.session_key(chat_session_id))
        return json.loads(raw) if raw else None

    def save_history(self, issue_id: str, history: list[dict[str, Any]]) -> None:
        self._set(self.history_key(issue_id), json.dumps(history))

    def seed_history(self, issue_id: str) -> list[dict[str, Any]]:
        history = self.get_history(issue_id)
        if not history:
            history = list(SEEDED_HISTORY)
            self.save_history(issue_id, history)
        return history

    def record_result(self, issue_id: str, reproduced: bool) -> None:
        history = self.seed_history(issue_id)
        history.append(
            {
                "reproduced": reproduced,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
        )
        self.save_history(issue_id, history)
        self._set(self.status_key(issue_id), "reproduced" if reproduced else "passed")

    def save_session_context(
        self, chat_session_id: str, context: dict[str, Any]
    ) -> None:
        self._set(self.session_key(chat_session_id), json.dumps(context))
