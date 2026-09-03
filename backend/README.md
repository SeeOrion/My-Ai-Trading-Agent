# My AI Trading Agent Backend

This directory is the complete Python backend workspace: DDD source, tests, Alembic migrations,
`uv` dependency definition and Docker image.

Run local development commands from here:

```bash
uv sync --all-extras
uv run uvicorn ai_trading_agent.presentation.http.app:app --app-dir src --reload --port 8000
```

The API is served under `/api/v1`. Migrations are in `migrations/` and must receive a PostgreSQL
URL at deployment time. No credentials are committed in this repository.
