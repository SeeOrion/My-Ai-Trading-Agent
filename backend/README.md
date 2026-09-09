# My AI Trading Agent Backend

This directory is the complete Python backend workspace: DDD source, tests, Alembic migrations,
`uv` dependency definition and Docker image.

Run local development commands from here:

```bash
uv sync --all-extras
uv run uvicorn ai_trading_agent.interfaces.api.app:app --app-dir src --reload --port 8000
```

The API is served under `/api/v1`. Migrations are in `migrations/` and must receive a PostgreSQL
URL at deployment time. No credentials are committed in this repository.

For A-share intraday quotes, the runtime prefers Futu OpenD and automatically
degrades to the Hithink Finance private REST credential configured by its skill,
then Tencent's experimental public page feed and Tushare daily data. The Hithink
key is kept in its user-level private credential store outside this repository;
never add it to this project `.env` or a deployment manifest. Tencent and
AKShare are research/display sources only and are never execution prices.

`HITHINK_FINANCE_TIMEOUT_SECONDS` is the only Hithink setting shown in
`.env.example`. Configure the API Key through the `hithink-finance` Skill's
system-level private credential flow, not through a project file or Git.

Hithink Finance also powers the selected-fund workspace: exchange-traded ETFs
receive true snapshots and daily OHLCV, while OTC funds receive their published
NAV, returns, disclosed holdings, allocation, drawdowns, diagnostics and fund
news metadata. OTC NAV is never presented as real-time traded volume.
