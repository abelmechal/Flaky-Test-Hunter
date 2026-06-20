import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.repro_client import run_repro_plan


def main() -> None:
    fixture_path = Path("contracts/repro_plan.example.json")
    if not fixture_path.exists():
        raise FileNotFoundError(f"Missing fixture: {fixture_path}")

    plan = json.loads(fixture_path.read_text(encoding="utf-8"))
    print(f"REPRO_MODE={os.getenv('REPRO_MODE', 'mock')}")
    print(f"Running repro plan for issue: {plan.get('issue_id')}")
    print(f"Test: {plan.get('test_name')}")
    print()

    result = run_repro_plan(plan)
    print("Repro Result:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
