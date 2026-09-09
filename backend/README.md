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
