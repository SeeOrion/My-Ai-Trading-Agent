FROM python:3.13-slim AS runtime

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.9.15 /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
RUN uv sync --frozen --no-dev --extra api --extra database
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
CMD ["uvicorn", "ai_trading_agent.presentation.http.app:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
