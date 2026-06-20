from __future__ import annotations

from typing import Any

from app.contracts import ReproPlan, ReproResult


def is_flaky(history: list[dict[str, Any]]) -> bool:
    outcomes = {bool(item["reproduced"]) for item in history}
    return outcomes == {False, True}


def classify_failure(history: list[dict[str, Any]]) -> str:
    if is_flaky(history):
        return "Likely flaky"
    if history and all(bool(item["reproduced"]) for item in history):
        return "Likely regression"
    return "Inconclusive"


def format_diagnosis(
    plan: ReproPlan,
    result: ReproResult,
    history: list[dict[str, Any]],
    verification_source: str,
) -> str:
    classification = classify_failure(history)
    browser_outcome = "failed" if result.reproduced else "passed"
    source_label = (
        "Browserbase"
        if verification_source == "browserbase"
        else verification_source.capitalize()
    )
    history_summary = (
        "Recent runs show mixed pass/fail behavior."
        if is_flaky(history)
        else "Recent runs do not yet show mixed pass/fail behavior."
    )
    conclusion = (
        "This is likely flaky, not a deterministic regression."
        if classification == "Likely flaky"
        else "The available evidence does not yet prove intermittent behavior."
    )
    return (
        f"Diagnosis: {classification}\n\n"
        f"Sentry issue:\n{plan.test_name}\n\n"
        f"Observed failure:\n{plan.expected_failure}\n\n"
        f"Browser verification:\nLatest run {browser_outcome} in {source_label}.\n\n"
        f"History:\n{history_summary}\n\n"
        f"Conclusion:\n{conclusion}\n\n"
        "Recommendation:\nTemporarily quarantine the test and investigate "
        "async timing around #order-confirmation."
    )
