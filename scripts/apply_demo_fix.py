from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.fix_workflow import execute_fix


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    args = parser.parse_args()
    result = execute_fix(args.scenario)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["verified"] else 1)


if __name__ == "__main__":
    main()
