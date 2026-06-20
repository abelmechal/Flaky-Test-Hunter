from __future__ import annotations

import os
from typing import Any

from uagents import Context

from app.a2a_reproducer_client import run_repro_plan_via_agent
from app.contracts import ReproResult
from app.reasoning import format_diagnosis
from app.redis_store import RedisStore
from app.repro_client import ReproRunner, run_repro_plan
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
        self.repro_runner = repro_runner or run_repro_plan
        self.store = store or RedisStore()

    def diagnose(self, chat_session_id: str) -> str:
        plan = self.sentry.fetch_repro_plan()
        plan_data: dict[str, Any] = plan.model_dump(mode="json", exclude_none=True)
        result_data = self.repro_runner(plan_data)
        return self._finish_diagnosis(
            plan=plan,
            result_data=result_data,
            chat_session_id=chat_session_id,
        )

    async def diagnose_async(self, ctx: Context, chat_session_id: str) -> str:
        plan = self.sentry.fetch_repro_plan()
        plan_data: dict[str, Any] = plan.model_dump(mode="json", exclude_none=True)
        if os.getenv("MULTI_AGENT_MODE", "false").lower() == "true":
            result_data = await run_repro_plan_via_agent(
                ctx,
                plan_data,
                conversation_id=f"{plan.issue_id}-{chat_session_id}",
            )
        else:
            result_data = self.repro_runner(plan_data)
        return self._finish_diagnosis(
            plan=plan,
            result_data=result_data,
            chat_session_id=chat_session_id,
        )

    def diagnose_from_result(
        self,
        *,
        chat_session_id: str,
        result_data: dict[str, Any],
    ) -> str:
        plan = self.sentry.fetch_repro_plan()
        return self._finish_diagnosis(
            plan=plan,
            result_data=result_data,
            chat_session_id=chat_session_id,
        )

    def _finish_diagnosis(
        self,
        *,
        plan: Any,
        result_data: dict[str, Any],
        chat_session_id: str,
    ) -> str:
        self.store.seed_history(plan.issue_id)
        verification_source = self.verification_source
        verification_path = None
        if result_data.get("_a2a_delegated"):
            verification_source = "browserbase"
            verification_path = (
                "Delegated browser reproduction to the Reproducer Agent."
            )
        elif result_data.get("_a2a_fallback"):
            verification_path = (
                "Reproducer Agent was unavailable; used the existing local "
                "reproducer fallback."
            )
        elif result_data.get("browserbase_error"):
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
                "multi_agent": bool(result_data.get("_a2a_delegated")),
            },
        )
        return format_diagnosis(
            plan,
            result,
            updated_history,
            verification_source=verification_source,
            verification_path=verification_path,
        )
