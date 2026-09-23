#!/usr/bin/env python3
"""Back up and merge the private local PostgreSQL database into Docker.

Secrets are loaded from the repository root .env and are only passed to child
processes through their environment. They are never printed or written into a
command line, Git-tracked file, or backup filename.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from getpass import getuser
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import make_url

SCHEMA = "trading_agent"
ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
PRIVATE_ROOT = ROOT / ".runtime"
BACKUP_ROOT = PRIVATE_ROOT / "backups"
ENV_FILE = ROOT / ".env"


class MigrationError(RuntimeError):
    """Raised when a safe database migration precondition is not met."""


def _run(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: Path = ROOT,
    stdin: object | None = None,
    stdout: object | None = None,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        stdin=stdin,
        stdout=subprocess.PIPE if capture else stdout,
        stderr=subprocess.PIPE,
        text=stdout is None,
        check=True,
    )


def _discover_source_database(pg_env: dict[str, str]) -> str:
    discovery_env = pg_env.copy()
    discovery_env["PGDATABASE"] = "postgres"
    databases = _run(
        [
            "psql",
            "--no-psqlrc",
            "--tuples-only",
            "--no-align",
            "--command",
            "SELECT datname FROM pg_database "
            "WHERE datallowconn AND NOT datistemplate ORDER BY datname",
        ],
        env=discovery_env,
        capture=True,
    ).stdout.splitlines()
    matches: list[str] = []
    for database in databases:
        candidate = database.strip()
        if not candidate:
            continue
        candidate_env = pg_env.copy()
        candidate_env["PGDATABASE"] = candidate
        found = _run(
            [
                "psql",
                "--no-psqlrc",
                "--tuples-only",
                "--no-align",
                "--command",
                "SELECT count(*) FROM information_schema.tables "
                f"WHERE table_schema = '{SCHEMA}'",
            ],
            env=candidate_env,
            capture=True,
        ).stdout.strip()
        if int(found or 0) > 0:
            matches.append(candidate)
    if len(matches) != 1:
        raise MigrationError(
            "DATABASE_URL omits the database name and automatic discovery did not find "
            "exactly one project database"
        )
    return matches[0]


def _source_environment() -> tuple[dict[str, str], str]:
    if not ENV_FILE.is_file():
        raise MigrationError("repository root .env is missing")
    database_url = str(dotenv_values(ENV_FILE).get("DATABASE_URL") or "").strip()
    if not database_url:
        raise MigrationError("DATABASE_URL is missing from the private .env")

    parsed = make_url(database_url)
    if not parsed.drivername.startswith("postgresql"):
        raise MigrationError("DATABASE_URL is not a supported PostgreSQL URL")

    pg_env = os.environ.copy()
    for variable in ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD"):
        pg_env.pop(variable, None)
    pg_env.update(
        {
            "PGUSER": parsed.username or getuser(),
            "PGPASSWORD": parsed.password or "",
        }
    )
    if parsed.host:
        pg_env["PGHOST"] = parsed.host
    if parsed.port:
        pg_env["PGPORT"] = str(parsed.port)
    pg_env["PGDATABASE"] = parsed.database or _discover_source_database(pg_env)
    normalized_url = parsed.set(
        username=pg_env["PGUSER"],
        database=pg_env["PGDATABASE"],
    ).render_as_string(hide_password=False)
    return pg_env, normalized_url


def _private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(stat.S_IRWXU)


def _source_psql(pg_env: dict[str, str], query: str) -> str:
    result = _run(
        ["psql", "--no-psqlrc", "--tuples-only", "--no-align", "--command", query],
        env=pg_env,
        capture=True,
    )
    return result.stdout.strip()


def _target_psql(query: str) -> str:
    result = _run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "psql",
            "--no-psqlrc",
            "--tuples-only",
            "--no-align",
            "--username",
            "trading_agent",
            "--dbname",
            "trading_agent",
            "--command",
            query,
        ],
        capture=True,
    )
    return result.stdout.strip()


def _tables(psql: Callable[[str], str]) -> list[str]:
    rows = psql(
        "SELECT table_name FROM information_schema.tables "
        f"WHERE table_schema = '{SCHEMA}' AND table_type = 'BASE TABLE' "
        "ORDER BY table_name"
    )
    return [row for row in rows.splitlines() if row]


def _counts(psql: Callable[[str], str], tables: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in tables:
        safe_table = table.replace('"', '""')
        counts[table] = int(psql(f'SELECT count(*) FROM {SCHEMA}."{safe_table}"') or 0)
    return counts


def _summarize(label: str, counts: dict[str, int]) -> None:
    populated = sum(1 for count in counts.values() if count)
    print(f"{label}: {len(counts)} tables, {populated} populated, {sum(counts.values())} rows")


def main() -> int:
    for binary in ("psql", "pg_dump", "docker"):
        if shutil.which(binary) is None:
            raise MigrationError(f"required executable is unavailable: {binary}")

    pg_env, database_url = _source_environment()
    _source_psql(pg_env, "SELECT 1")
    _target_psql("SELECT 1")

    _private_directory(PRIVATE_ROOT)
    _private_directory(BACKUP_ROOT)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    source_backup = BACKUP_ROOT / f"native-before-{timestamp}.dump"
    target_backup = BACKUP_ROOT / f"docker-before-{timestamp}.dump"
    merge_sql = BACKUP_ROOT / f"native-data-{timestamp}.sql"

    print(
        "Stopping the backend briefly so scheduled jobs cannot change "
        "the target during migration."
    )
    _run(["docker", "compose", "stop", "backend"])
    try:
        with source_backup.open("wb") as output:
            _run(
                [
                    "pg_dump",
                    "--format=custom",
                    "--no-owner",
                    "--no-privileges",
                ],
                env=pg_env,
                stdout=output,
            )
        source_backup.chmod(stat.S_IRUSR | stat.S_IWUSR)

        with target_backup.open("wb") as output:
            _run(
                [
                    "docker",
                    "compose",
                    "exec",
                    "-T",
                    "postgres",
                    "pg_dump",
                    "--username",
                    "trading_agent",
                    "--dbname",
                    "trading_agent",
                    "--format=custom",
                    "--no-owner",
                    "--no-privileges",
                ],
                stdout=output,
            )
        target_backup.chmod(stat.S_IRUSR | stat.S_IWUSR)

        migration_env = os.environ.copy()
        migration_env["DATABASE_URL"] = database_url
        _run(
            [str(BACKEND / ".venv" / "bin" / "alembic"), "upgrade", "head"],
            env=migration_env,
            cwd=BACKEND,
        )

        source_tables = _tables(lambda query: _source_psql(pg_env, query))
        target_tables = _tables(_target_psql)
        if set(source_tables) - set(target_tables):
            raise MigrationError("Docker database is missing tables after migrations")

        source_counts = _counts(lambda query: _source_psql(pg_env, query), source_tables)
        target_before = _counts(_target_psql, target_tables)
        _summarize("Native source", source_counts)
        _summarize("Docker before", target_before)

        with merge_sql.open("w", encoding="utf-8") as output:
            _run(
                [
                    "pg_dump",
                    "--data-only",
                    "--inserts",
                    "--on-conflict-do-nothing",
                    "--no-owner",
                    "--no-privileges",
                    "--schema",
                    SCHEMA,
                ],
                env=pg_env,
                stdout=output,
            )
        merge_sql.chmod(stat.S_IRUSR | stat.S_IWUSR)

        with merge_sql.open("r", encoding="utf-8") as source:
            _run(
                [
                    "docker",
                    "compose",
                    "exec",
                    "-T",
                    "postgres",
                    "psql",
                    "--no-psqlrc",
                    "--set",
                    "ON_ERROR_STOP=1",
                    "--username",
                    "trading_agent",
                    "--dbname",
                    "trading_agent",
                ],
                stdin=source,
                stdout=subprocess.DEVNULL,
            )

        target_after = _counts(_target_psql, target_tables)
        for table, source_count in source_counts.items():
            if target_after.get(table, 0) < source_count:
                raise MigrationError(f"row verification failed for table: {table}")
        _summarize("Docker after", target_after)
        print(f"Private backups saved under: {BACKUP_ROOT}")
        print("Migration completed; existing Docker rows won on primary-key conflicts.")
    finally:
        _run(["docker", "compose", "start", "backend"])

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or "database command failed").strip().splitlines()[-1]
        print(f"Migration failed safely: {message}", file=sys.stderr)
        raise SystemExit(1) from None
    except MigrationError as exc:
        print(f"Migration stopped safely: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
