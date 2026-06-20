from __future__ import annotations

from app.reasoning import format_diagnosis
from app.redis_store import RedisStore
from app.repro_client import MockReproClient
from app.sentry_client import SentryClient


class FlakyTestWorkflow:
    def __init__(
        self,
        sentry: SentryClient | None = None,
        repro: MockReproClient | None = None,
        store: RedisStore | None = None,
    ) -> None:
        self.sentry = sentry or SentryClient()
        self.repro = repro or MockReproClient()
        self.store = store or RedisStore()

    def diagnose(self, chat_session_id: str) -> str:
        plan = self.sentry.fetch_repro_plan()
        history = self.store.seed_history(plan.issue_id)
        result = self.repro.run(plan)
        self.store.record_result(plan.issue_id, result.reproduced)
        self.store.save_session_context(
            chat_session_id,
            {
                "issue_id": plan.issue_id,
                "test_name": plan.test_name,
                "last_reproduced": result.reproduced,
            },
        )
        return format_diagnosis(plan, result, history)
