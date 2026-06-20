# Flaky-Test Hunter

Flaky-Test Hunter is a hackathon ASI:One agent that triages flaky CI test failures.

MVP capability:

- Responds through ASI:One / Agentverse chat
- Later: pulls Sentry test failures
- Later: reruns browser repro steps through Browserbase
- Later: stores retry and history state in Redis

Current milestone:

- Hardcoded platform proof response
