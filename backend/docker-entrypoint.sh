#!/bin/sh
set -eu

if [ -n "${DATABASE_PASSWORD_FILE:-}" ]; then
  database_password="$(tr -d '\r\n' < "${DATABASE_PASSWORD_FILE}")"
  if [ -z "${database_password}" ]; then
    echo "database password file is empty" >&2
    exit 1
  fi
  database_host="${DATABASE_HOST:-postgres}"
  database_port="${DATABASE_PORT:-5432}"
  database_name="${DATABASE_NAME:-trading_agent}"
  database_user="${DATABASE_USER:-trading_agent}"
  export DATABASE_URL="postgresql+asyncpg://${database_user}:${database_password}@${database_host}:${database_port}/${database_name}"
fi

exec "$@"
