# Flaky-Test Hunter

Flaky-Test Hunter is a hackathon ASI:One agent that triages flaky CI test failures.

MVP capability:

- Responds through ASI:One / Agentverse chat
- Later: pulls Sentry test failures
- Later: reruns browser repro steps through Browserbase
- Later: stores retry and history state in Redis

Current milestone:

- Parses a seeded Sentry issue into the frozen Repro Plan contract
- Calls a mocked Browserbase-compatible reproducer
- Stores seeded flaky-test history using Redis when configured
- Falls back to an in-memory store for local development

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m unittest discover -s tests -v
python agent.py
```

Copy `.env.example` to `.env` and replace `AGENT_SEED` before a public demo.
Keep `REPRO_MODE=mock` for local development. Set it to `browserbase` when
`app/browserbase_runner.py` is available. `REPRO_FALLBACK_TO_MOCK=true` keeps
the demo operational if the Browserbase runner fails.

Install the browser runtime once:

```powershell
pip install -r requirements.txt
playwright install chromium
```

Then run the deterministic fixture:

```powershell
$env:REPRO_MODE = "mock"
python scripts/run_browserbase_fixture.py

$env:REPRO_MODE = "browserbase"
$env:BROWSERBASE_API_KEY = "your-key"
python scripts/run_browserbase_fixture.py
```

## Integration contracts

- Input: `contracts/repro_plan.example.json`
- Output: `contracts/repro_result.example.json`

The Browserbase runner should accept the input contract and return the output
contract. Its initial supported actions are `goto`, `fill`, `click`, and
`wait_for_selector`.

Both implementations expose the same interface:

```python
def run_repro_plan(plan: dict) -> dict:
    ...
```

## Redis keys

- `issue:{issue_id}:history`
- `issue:{issue_id}:status`
- `session:{chat_session_id}:context`
