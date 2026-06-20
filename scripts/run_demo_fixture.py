import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.redis_store import RedisStore
from app.workflow import FlakyTestWorkflow


def main() -> None:
    workflow = FlakyTestWorkflow(store=RedisStore())
    print(workflow.diagnose(chat_session_id="demo-fixture"))


if __name__ == "__main__":
    main()
