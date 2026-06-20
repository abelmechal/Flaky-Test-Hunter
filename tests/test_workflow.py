import json
import unittest
from pathlib import Path

from app.contracts import ReproPlan, ReproResult
from app.reasoning import classify_failure
from app.redis_store import RedisStore
from app.repro_client import get_repro_runner, run_repro_plan
from app.sentry_client import SentryClient
from app.workflow import FlakyTestWorkflow


ROOT = Path(__file__).resolve().parent.parent


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
            repro_runner=run_repro_plan,
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


if __name__ == "__main__":
    unittest.main()
