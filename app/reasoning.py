from __future__ import annotations

from typing import Any

from app.contracts import ReproPlan, ReproResult


def is_flaky(history: list[dict[str, Any]]) -> bool:
    outcomes = {bool(item["reproduced"]) for item in history}
    return outcomes == {False, True}


def format_diagnosis(
    plan: ReproPlan,
    result: ReproResult,
    history: list[dict[str, Any]],
) -> str:
    action_labels = {
        "goto": "goto checkout page",
        "fill": "fill email",
        "click": "click submit payment",
        "wait_for_selector": "wait for order confirmation",
    }
    steps = "\n".join(
        f"{index}. {action_labels.get(step.action, step.action)}"
        for index, step in enumerate(plan.steps, start=1)
    )
    history_note = (
        "The history has both pass and fail outcomes, so this looks flaky."
        if is_flaky(history)
        else "The current history does not yet show mixed pass and fail outcomes."
    )
    repro_note = (
        "The mocked browser run reproduced the expected failure."
        if result.reproduced
        else "The mocked browser run did not reproduce the expected failure."
    )
    return (
        f"I found the Sentry issue for {plan.test_name}.\n\n"
        f"Failure:\n{plan.expected_failure}\n\n"
        f"Recent failures:\n{plan.run_count_recent}\n\n"
        f"I created a browser reproduction plan with {len(plan.steps)} steps:\n"
        f"{steps}\n\n"
        f"{history_note}\n{repro_note}\n\n"
        "Next step: send this plan to Browserbase for live verification."
    )
