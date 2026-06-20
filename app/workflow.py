from __future__ import annotations

import os
from typing import Any

from app.contracts import ReproResult
from app.reasoning import format_diagnosis
from app.redis_store import RedisStore
from app.repro_client import ReproRunner, get_repro_runner, run_repro_plan
from app.sentry_client import SentryClient


class FlakyTestWorkflow:
    def __init__(
        self,
        sentry: SentryClient | None = None,
        repro_runner: ReproRunner | None = None,
        store: RedisStore | None = None,
    ) -> None:
        self.sentry = sentry or SentryClient()
        self.repro_mode = os.getenv("REPRO_MODE", "mock").lower()
        self.verification_source = self.repro_mode
        if repro_runner is not None:
            self.repro_runner = repro_runner
        else:
            try:
                self.repro_runner = get_repro_runner(self.repro_mode)
            except (ImportError, AttributeError):
                if (
                    self.repro_mode != "browserbase"
                    or os.getenv("REPRO_FALLBACK_TO_MOCK", "true").lower() != "true"
                ):
                    raise
                self.repro_runner = run_repro_plan
                self.verification_source = "mock fallback"
        self.store = store or RedisStore()

    def diagnose(self, chat_session_id: str) -> str:
        plan = self.sentry.fetch_repro_plan()
        history = self.store.seed_history(plan.issue_id)
        plan_data: dict[str, Any] = plan.model_dump(mode="json", exclude_none=True)
        try:
            result_data = self.repro_runner(plan_data)
            verification_source = self.verification_source
        except Exception:
            if (
                self.repro_mode != "browserbase"
                or os.getenv("REPRO_FALLBACK_TO_MOCK", "true").lower() != "true"
            ):
                raise
            result_data = run_repro_plan(plan_data)
            verification_source = "mock fallback"
        result = ReproResult.model_validate(result_data)
        self.store.record_result(plan.issue_id, result.reproduced)
        updated_history = self.store.get_history(plan.issue_id)
        self.store.save_session_context(
            chat_session_id,
            {
                "issue_id": plan.issue_id,
                "test_name": plan.test_name,
                "last_reproduced": result.reproduced,
                "repro_mode": verification_source,
            },
        )
        return format_diagnosis(
            plan,
            result,
            updated_history,
            verification_source=verification_source,
        )
