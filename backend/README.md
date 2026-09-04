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

For free A-share intraday quotes and public-news aggregation, install the
`free-data` extra (included in `--all-extras`). Tencent's public page feed is an
experimental quote source; AKShare aggregates public news pages. Both are research/display
sources only and are never execution prices.
