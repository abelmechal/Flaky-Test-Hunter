import json
import unittest
from pathlib import Path

from app.contracts import ReproPlan, ReproResult
from app.redis_store import RedisStore
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
    def test_diagnosis_uses_seeded_issue_and_flaky_history(self):
        message = FlakyTestWorkflow(store=RedisStore()).diagnose("test-session")
        self.assertIn("checkout_flow.spec.ts > completes purchase", message)
        self.assertIn("4 steps", message)
        self.assertIn("this looks flaky", message)
        self.assertIn("mocked browser run reproduced", message)


if __name__ == "__main__":
    unittest.main()
