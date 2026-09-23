FROM python:3.13-slim AS runtime

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.9.15 /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
COPY docker-entrypoint.sh ./docker-entrypoint.sh
RUN uv sync --frozen --no-dev \
    --extra api \
    --extra database \
    --extra futu \
    --extra tushare \
    --extra free-data \
    --extra news \
    && chmod 755 ./docker-entrypoint.sh
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "ai_trading_agent.interfaces.api.app:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
