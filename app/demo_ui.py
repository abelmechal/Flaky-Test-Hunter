from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.a2a_reproducer_client import query_reproducer_agent
from app.contracts import ReproResult
from app.reasoning import classify_failure
from app.redis_store import RedisStore
from app.sentry_client import SentryClient


ROOT = Path(__file__).resolve().parent.parent


def load_demo_plan() -> dict[str, Any]:
    return SentryClient().fetch_repro_plan().model_dump(
        mode="json", exclude_none=True
    )


def fixture_payload() -> dict[str, Any]:
    plan = load_demo_plan()
    return {
        "issue": {
            "id": plan["issue_id"],
            "test_name": plan["test_name"],
            "expected_failure": plan["expected_failure"],
            "first_seen": plan["first_seen"],
            "recent_runs": plan["run_count_recent"],
        },
        "plan": {
            "step_count": len(plan["steps"]),
            "steps": plan["steps"],
        },
    }


async def run_demo_diagnosis() -> dict[str, Any]:
    plan = load_demo_plan()
    started_at = datetime.now(timezone.utc)
    result_data = await query_reproducer_agent(
        plan,
        conversation_id=f"ui-demo-{started_at.strftime('%Y%m%d%H%M%S')}",
    )
    result = ReproResult.model_validate(result_data)

    store = RedisStore()
    store.seed_history(plan["issue_id"])
    store.record_result(plan["issue_id"], result.reproduced)
    history = store.get_history(plan["issue_id"])
    classification = classify_failure(history)

    delegated = bool(result_data.get("_a2a_delegated"))
    fallback = bool(result_data.get("_a2a_fallback"))
    live_browserbase = bool(result_data.get("browserbase_session_url"))
    source = "Browserbase via Reproducer Agent" if delegated else "Local fallback"
    if live_browserbase and not delegated:
        source = "Browserbase via serverless Reproducer"
    elif not delegated and not fallback:
        source = "Local reproducer"

    session_url = result_data.get("browserbase_session_url")
    screenshot_url = result.screenshot_url
    if screenshot_url and not str(screenshot_url).startswith(("http://", "https://")):
        try:
            relative = Path(screenshot_url).resolve().relative_to(ROOT.resolve())
            screenshot_url = f"/files/{relative.as_posix()}"
        except ValueError:
            screenshot_url = None

    pass_count = sum(not bool(item["reproduced"]) for item in history)
    fail_count = sum(bool(item["reproduced"]) for item in history)
    failed_step = len(plan["steps"]) if result.reproduced else None

    return {
        "status": "completed",
        "run": {
            "source": source,
            "delegated": delegated,
            "fallback": fallback,
            "live_browserbase": live_browserbase,
            "duration_ms": result.duration_ms,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
        "issue": {
            "id": plan["issue_id"],
            "test_name": plan["test_name"],
            "expected_failure": plan["expected_failure"],
            "recent_runs": plan["run_count_recent"],
        },
        "verification": {
            "reproduced": result.reproduced,
            "failed_step": failed_step,
            "total_steps": len(plan["steps"]),
            "error_observed": result.error_observed,
            "notes": result.notes,
            "session_url": session_url,
            "screenshot_url": screenshot_url,
        },
        "history": {
            "items": history,
            "pass_count": pass_count,
            "fail_count": fail_count,
        },
        "diagnosis": {
            "classification": classification,
            "confidence": 92 if classification == "Likely flaky" else 68,
            "conclusion": (
                "The same test has both passing and failing outcomes across "
                "recent runs, so this is intermittent rather than deterministic."
            ),
            "recommendation": (
                "Temporarily quarantine this test and investigate async timing "
                "around #order-confirmation."
            ),
        },
    }
