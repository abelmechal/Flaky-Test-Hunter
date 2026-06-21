# Flaky-Test Hunter

Flaky-Test Hunter is an ASI:One/uAgent prototype that turns a structured Sentry
test failure into a browser reproduction plan, executes it, checks recent
history, and classifies the failure as flaky or a likely regression.

## Demo Modes

- `mock`: deterministic local repro result; no cloud credentials required.
- `browserbase`: executes the frozen plan in a real Browserbase cloud session.
- Browserbase mode automatically uses the mock fallback when credentials are
  missing or Browserbase fails, provided `REPRO_FALLBACK_TO_MOCK=true`.

## Environment Variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `AGENT_SEED` | local demo seed | uAgent identity; replace before public demos |
| `AGENT_PORT` | `8001` | Local uAgent port |
| `REDIS_URL` | unset | Optional Redis connection; otherwise memory is used |
| `REPRO_MODE` | `mock` | Selects `mock` or `browserbase` |
| `REPRO_FALLBACK_TO_MOCK` | `true` | Preserves the demo if Browserbase fails |
| `BROWSERBASE_API_KEY` | unset | Required for live Browserbase execution |
| `BROWSERBASE_PROJECT_ID` | unset | Optional Browserbase project |
| `BROWSERBASE_STEP_TIMEOUT_MS` | `8000` | Default browser step timeout |
| `BROWSERBASE_SESSION_TIMEOUT_SECONDS` | `300` | Browserbase session timeout |
| `SCREENSHOT_DIR` | `artifacts/screenshots` | Local screenshot output |
| `MULTI_AGENT_MODE` | `false` | Delegates repro work to the Reproducer Agent |
| `REPRODUCER_AGENT_ADDRESS` | unset | Reproducer uAgent address |
| `REPRODUCER_AGENT_ENDPOINT` | local port 8002 | Optional direct endpoint for smoke tests |
| `A2A_REPRO_TIMEOUT_SECONDS` | `30` | Delegation timeout before local fallback |

Copy `.env.example` to `.env`. Never commit real credentials.

## How to Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
python -m unittest discover -s tests -v
python agent.py
```

## Demo Script

The full diagnosis is produced with one command.

### Visual Demo UI

For the judge-facing dashboard, keep the Reproducer Agent running and launch:

```powershell
$env:MULTI_AGENT_MODE = "true"
$env:REPRO_MODE = "browserbase"
$env:REPRODUCER_AGENT_ADDRESS = "agent1..."
$env:REPRODUCER_AGENT_ENDPOINT = "http://127.0.0.1:8002/submit"
python scripts/run_demo_ui.py
```

Open `http://127.0.0.1:8080` and click **Run live diagnosis**. The dashboard
shows the agent handoff, Browserbase failure evidence, mixed execution history,
and final recommendation in one view.

The test triage queue includes four distinct demo cases:

- Checkout confirmation: mixed outcomes, classified as likely flaky.
- Login redirect: repeated failures, classified as a likely regression.
- Search suggestions: verification passes, classified as inconclusive.
- Upload progress: intermittent completion state, classified as likely flaky.

### Deploy the Dashboard to Vercel

The repository includes Vercel Python function adapters for `/api/fixture` and
`/api/run`, plus static rewrites for the dashboard.

Set these Vercel environment variables:

```text
REPRO_MODE=browserbase
REPRO_FALLBACK_TO_MOCK=true
BROWSERBASE_API_KEY=<secret>
BROWSERBASE_PROJECT_ID=<optional>
MULTI_AGENT_MODE=true
REPRODUCER_AGENT_ADDRESS=<hosted agent address>
REPRODUCER_AGENT_ENDPOINT=<public https endpoint>
```

`REPRODUCER_AGENT_ENDPOINT` must be publicly reachable. A deployed Vercel
function cannot call an agent at `127.0.0.1`. If no hosted Reproducer endpoint
is configured, the Vercel function can execute Browserbase through the
serverless Reproducer fallback and labels that path explicitly in the UI.

PowerShell:

```powershell
$env:REPRO_MODE = "browserbase"
$env:BROWSERBASE_API_KEY = "your-key"
python scripts/run_demo_fixture.py
```

macOS/Linux:

```bash
REPRO_MODE=browserbase BROWSERBASE_API_KEY="your-key" \
  python scripts/run_demo_fixture.py
```

Safe credential-free demo:

```powershell
$env:REPRO_MODE = "mock"
python scripts/run_demo_fixture.py
```

Use `scripts/run_browserbase_fixture.py` when the raw Repro Result JSON is
needed instead of the final diagnosis.

## What Is Real vs Mocked

Real:

- ASI:One/uAgent chat integration
- Repro Plan and Repro Result contracts
- Browser step execution for `goto`, `fill`, `click`, and `wait_for_selector`
- Redis/local history storage logic
- Flaky-versus-regression classification
- Local Playwright/browser validation

Requires an API key:

- Live Browserbase cloud execution

Mock fallback:

- Used when Browserbase credentials are missing or Browserbase fails
- Implements the same `run_repro_plan(plan: dict) -> dict` interface

## Seeded Demo History

The local/Redis demo seed intentionally contains mixed outcomes:

```json
[
  {"reproduced": true, "timestamp": "2026-06-20T10:00:00Z"},
  {"reproduced": false, "timestamp": "2026-06-20T10:10:00Z"},
  {"reproduced": true, "timestamp": "2026-06-20T10:20:00Z"}
]
```

Redis keys:

- `issue:{issue_id}:history`
- `issue:{issue_id}:status`
- `session:{chat_session_id}:context`

## Integration Contracts

- Input: `contracts/repro_plan.example.json`
- Output: `contracts/repro_result.example.json`

Both repro implementations expose:

```python
def run_repro_plan(plan: dict) -> dict:
    ...
```

## Known Limitations

- Sentry is currently represented by one structured local fixture.
- The Browserbase runner supports only four frozen browser actions.
- Screenshots are stored as local artifacts rather than uploaded.
- In-memory history resets when the process exits unless Redis is configured.
- Classification uses deterministic rules, not LLM reasoning.

## Future Work

- Connect the live Sentry Issues API.
- Upload screenshots and attach durable artifact URLs.
- Add authenticated staging-app support and secret management.
- Expand browser actions only after the MVP contract is stable.
- Add richer retry statistics, confidence scoring, and CI-provider links.

## Multi-Agent Upgrade

The MVP can run in two modes:

Single-agent mode:

```text
ASI:One → Flaky-Test Hunter → Sentry/Redis/Browserbase
```

Multi-agent mode:

```text
ASI:One → Diagnostician Agent → Reproducer Agent → Browserbase
```

The Diagnostician Agent owns Sentry parsing, Redis history,
flaky-versus-regression reasoning, and the final explanation.

The Reproducer Agent owns live browser verification. It accepts a Repro Plan
JSON message over the Chat Protocol and returns a Repro Result JSON message.
Example envelopes are frozen in:

- `contracts/a2a_repro_request.example.json`
- `contracts/a2a_repro_response.example.json`

Enable the upgrade with:

```text
MULTI_AGENT_MODE=true
REPRODUCER_AGENT_ADDRESS=<agent address>
```

If the Reproducer Agent is missing, times out, or returns an invalid response,
the Diagnostician falls back to the existing local `run_repro_plan` path.

Run the two-agent demo:

Terminal 1:

```powershell
$env:BROWSERBASE_API_KEY = "your-key"
$env:REPRO_MODE = "browserbase"
python agents/reproducer_agent.py
```

Terminal 2:

```powershell
$env:MULTI_AGENT_MODE = "true"
$env:REPRO_MODE = "browserbase"
$env:REPRODUCER_AGENT_ADDRESS = "agent1..."
python agent.py
```

Standalone smoke request:

```powershell
$env:MULTI_AGENT_MODE = "true"
$env:REPRODUCER_AGENT_ADDRESS = "agent1..."
$env:REPRODUCER_AGENT_ENDPOINT = "http://127.0.0.1:8002/submit"
python scripts/run_multi_agent_demo_fixture.py
```
