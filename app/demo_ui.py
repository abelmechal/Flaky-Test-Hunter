from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.a2a_reproducer_client import query_reproducer_agent
from app.contracts import ReproResult
from app.reasoning import classify_failure
from app.redis_store import RedisStore


ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_PATH = ROOT / "fixtures" / "demo_scenarios.json"


def load_demo_scenarios() -> list[dict[str, Any]]:
    return json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))


def get_demo_scenario(scenario_id: str | None = None) -> dict[str, Any]:
    scenarios = load_demo_scenarios()
    selected_id = scenario_id or scenarios[0]["id"]
    for scenario in scenarios:
        if scenario["id"] == selected_id:
            return scenario
    raise ValueError(f"Unknown demo scenario: {selected_id}")


def load_demo_plan(scenario_id: str | None = None) -> dict[str, Any]:
    return get_demo_scenario(scenario_id)["plan"]


def fixture_payload() -> dict[str, Any]:
    scenarios = load_demo_scenarios()
    scenario = scenarios[0]
    plan = scenario["plan"]
    return {
        "selected_id": scenario["id"],
        "scenarios": [
            {
                "id": item["id"],
                "label": item["label"],
                "suite": item["suite"],
                "severity": item["severity"],
                "issue": item["plan"],
            }
            for item in scenarios
        ],
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


async def run_demo_diagnosis(scenario_id: str | None = None) -> dict[str, Any]:
    scenario = get_demo_scenario(scenario_id)
    plan = scenario["plan"]
    started_at = datetime.now(timezone.utc)
    result_data = await query_reproducer_agent(
        plan,
        conversation_id=f"ui-demo-{started_at.strftime('%Y%m%d%H%M%S')}",
    )
    if result_data.get("_a2a_fallback") and not result_data.get(
        "browserbase_session_url"
    ):
        result_data["reproduced"] = bool(scenario["mock_reproduced"])
        result_data["error_observed"] = (
            f"TimeoutError: {scenario['expected_element']} not found"
            if scenario["mock_reproduced"]
            else None
        )
        result_data["notes"] = (
            f"Failed while waiting for {scenario['expected_element']}"
            if scenario["mock_reproduced"]
            else "Verification completed without reproducing the reported failure."
        )
    result = ReproResult.model_validate(result_data)

    store = RedisStore()
    if not store.get_history(plan["issue_id"]):
        store.save_history(plan["issue_id"], scenario["history"])
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
        "scenario_id": scenario["id"],
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
            "expected_element": scenario["expected_element"],
            "browser_title": scenario["browser_title"],
            "browser_detail": scenario["browser_detail"],
        },
        "history": {
            "items": history,
            "pass_count": pass_count,
            "fail_count": fail_count,
        },
        "diagnosis": {
            "classification": classification,
            "confidence": scenario["confidence"],
            "conclusion": _conclusion_for(classification, result.reproduced),
            "recommendation": scenario["recommendation"],
        },
    }


def _conclusion_for(classification: str, reproduced: bool) -> str:
    if classification == "Likely flaky":
        return (
            "The same test has both passing and failing outcomes across recent "
            "runs, so this is intermittent rather than deterministic."
        )
    if classification == "Likely regression":
        return (
            "The failure reproduced consistently across every recent run, "
            "which strongly indicates a deterministic regression."
        )
    if not reproduced:
        return (
            "Browser verification passed and recent runs are stable. There is "
            "not enough evidence to classify the original report as flaky."
        )
    return "The available evidence is insufficient for a confident classification."
