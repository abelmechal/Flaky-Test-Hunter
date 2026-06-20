import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from app.browserbase_runner import _execute_step
from app.contracts import ReproPlan, ReproResult
from app.reasoning import classify_failure
from app.redis_store import SEEDED_HISTORY, RedisStore
from app.repro_client import (
    get_repro_runner,
    run_mock_repro_plan,
    run_repro_plan,
)
from app.sentry_client import SentryClient
from app.workflow import FlakyTestWorkflow


ROOT = Path(__file__).resolve().parent.parent


class FakeLocator:
    def __init__(self, calls, target):
        self.calls = calls
        self.target = target

    def fill(self, value, timeout):
        self.calls.append(("fill", self.target, value, timeout))

    def click(self, timeout):
        self.calls.append(("click", self.target, timeout))


class FakePage:
    def __init__(self):
        self.calls = []

    def goto(self, target, wait_until, timeout):
        self.calls.append(("goto", target, wait_until, timeout))

    def locator(self, target):
        return FakeLocator(self.calls, target)

    def wait_for_selector(self, target, state, timeout):
        self.calls.append(("wait_for_selector", target, state, timeout))


class ContractTests(unittest.TestCase):
    def test_example_contracts_validate(self):
        plan = ReproPlan.model_validate_json(
            (ROOT / "contracts" / "repro_plan.example.json").read_text(
                encoding="utf-8"
            )
        )
        result = ReproResult.model_validate_json(
            (ROOT / "contracts" / "repro_result.example.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(plan.issue_id, result.issue_id)

    def test_seeded_sentry_issue_matches_contract(self):
        expected = json.loads(
            (ROOT / "contracts" / "repro_plan.example.json").read_text(
                encoding="utf-8"
            )
        )
        actual = SentryClient().fetch_repro_plan().model_dump(
            mode="json", exclude_none=True
        )
        self.assertEqual(actual, expected)


class WorkflowTests(unittest.TestCase):
    def test_demo_history_is_seeded_with_mixed_outcomes(self):
        store = RedisStore()
        history = store.seed_history("sentry-checkout-001")
        self.assertEqual(history, SEEDED_HISTORY)
        self.assertEqual(
            [item["reproduced"] for item in history],
            [True, False, True],
        )

    def test_fixture_integration_flow(self):
        store = RedisStore()
        sentry = SentryClient()
        plan = sentry.fetch_repro_plan()
        plan_data = plan.model_dump(mode="json", exclude_none=True)

        result_data = run_repro_plan(plan_data)
        result = ReproResult.model_validate(result_data)
        store.seed_history(plan.issue_id)
        store.record_result(plan.issue_id, result.reproduced)

        history = store.get_history(plan.issue_id)
        self.assertEqual(classify_failure(history), "Likely flaky")
        self.assertEqual(store.get_status(plan.issue_id), "reproduced")

        message = FlakyTestWorkflow(
            sentry=sentry,
            repro_runner=run_mock_repro_plan,
            store=store,
        ).diagnose("test-session")
        context = store.get_session_context("test-session")

        self.assertIn("Diagnosis: Likely flaky", message)
        self.assertIn("Latest run failed in Mock.", message)
        self.assertIn("mixed pass/fail behavior", message)
        self.assertIn("not a deterministic regression", message)
        self.assertEqual(context["issue_id"], "sentry-checkout-001")
        self.assertEqual(context["repro_mode"], "mock")

    def test_mock_runner_uses_shared_dict_contract(self):
        plan = SentryClient().fetch_repro_plan().model_dump(
            mode="json", exclude_none=True
        )
        runner = get_repro_runner("mock")
        result = runner(plan)
        self.assertIsInstance(result, dict)
        self.assertTrue(result["reproduced"])

    def test_browserbase_mode_falls_back_without_api_key(self):
        plan = SentryClient().fetch_repro_plan().model_dump(
            mode="json", exclude_none=True
        )
        environment = {
            key: value
            for key, value in os.environ.items()
            if key != "BROWSERBASE_API_KEY"
        }
        environment["REPRO_MODE"] = "browserbase"
        with patch.dict(os.environ, environment, clear=True):
            result = run_repro_plan(plan)

        self.assertTrue(result["reproduced"])
        self.assertIn("mock fallback was used", result["notes"])
        self.assertTrue(
            result["browserbase_error"].startswith("BrowserbaseRunnerError")
        )

    def test_browserbase_step_executor_supports_frozen_actions(self):
        page = FakePage()
        _execute_step(
            page,
            {"action": "goto", "target": "data:text/html,<p>demo</p>"},
        )
        _execute_step(
            page,
            {"action": "fill", "target": "#email", "value": "test@example.com"},
        )
        _execute_step(page, {"action": "click", "target": "#submit-payment"})
        _execute_step(
            page,
            {
                "action": "wait_for_selector",
                "target": "#order-confirmation",
                "timeout_ms": 5000,
            },
        )

        self.assertEqual([call[0] for call in page.calls], [
            "goto",
            "fill",
            "click",
            "wait_for_selector",
        ])

    def test_live_browserbase_diagnosis_wording(self):
        plan = SentryClient().fetch_repro_plan()
        result = ReproResult(
            issue_id=plan.issue_id,
            reproduced=True,
            duration_ms=6200,
            screenshot_url="artifacts/screenshots/demo.png",
            error_observed="TimeoutError: timeout exceeded",
            notes="Browserbase reproduced a failure at step 4 of 4.",
        )
        from app.reasoning import format_diagnosis

        message = format_diagnosis(
            plan,
            result,
            SEEDED_HISTORY,
            verification_source="browserbase",
        )
        self.assertIn(
            "Browserbase reproduced a failure at step 4 of 4.",
            message,
        )
        self.assertIn("Temporarily quarantine this test", message)


if __name__ == "__main__":
    unittest.main()
