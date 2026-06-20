from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.contracts import ReproPlan

DEFAULT_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "sentry_issue.json"


class SentryIssueNotFoundError(LookupError):
    pass


class SentryClient:
    """Reads the seeded Sentry-shaped issue until the live API is connected."""

    def __init__(self, fixture_path: Path = DEFAULT_FIXTURE) -> None:
        self.fixture_path = fixture_path

    def fetch_seeded_issue(self, issue_id: str | None = None) -> dict[str, Any]:
        issue = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        if issue_id is not None and issue.get("id") != issue_id:
            raise SentryIssueNotFoundError(f"Sentry issue not found: {issue_id}")
        return issue

    def create_repro_plan(self, issue: dict[str, Any]) -> ReproPlan:
        try:
            raw_plan = issue["extra"]["repro_plan"]
        except (KeyError, TypeError) as exc:
            raise ValueError("Sentry issue does not contain extra.repro_plan") from exc
        return ReproPlan.model_validate(raw_plan)

    def fetch_repro_plan(self, issue_id: str | None = None) -> ReproPlan:
        return self.create_repro_plan(self.fetch_seeded_issue(issue_id))
