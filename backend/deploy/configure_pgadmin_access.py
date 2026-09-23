#!/usr/bin/env python3
"""Expose Docker PostgreSQL locally and create a private read-only pgAdmin login."""

from __future__ import annotations

import os
import secrets
import stat
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOT = ROOT / ".runtime"
CREDENTIAL_FILE = PRIVATE_ROOT / "pgadmin.env"
ROLE = "trading_agent_pgadmin"
PORT = os.environ.get("POSTGRES_HOST_PORT", "55433")


def _run(command: list[str], *, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        input=stdin,
        capture_output=True,
        text=True,
        check=True,
    )


def _password() -> str:
    if CREDENTIAL_FILE.is_file():
        for line in CREDENTIAL_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("PGADMIN_PASSWORD="):
                value = line.partition("=")[2].strip()
                if value:
                    return value
    return secrets.token_hex(24)


def main() -> int:
    PRIVATE_ROOT.mkdir(parents=True, exist_ok=True)
    PRIVATE_ROOT.chmod(stat.S_IRWXU)
    password = _password()
    CREDENTIAL_FILE.write_text(
        "\n".join(
            (
                "PGADMIN_HOST=127.0.0.1",
                f"PGADMIN_PORT={PORT}",
                "PGADMIN_MAINTENANCE_DB=trading_agent",
                f"PGADMIN_USERNAME={ROLE}",
                f"PGADMIN_PASSWORD={password}",
                "PGADMIN_SSLMODE=prefer",
                "",
            )
        ),
        encoding="utf-8",
    )
    CREDENTIAL_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)

    _run(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.yml",
            "-f",
            "docker-compose.pgadmin.yml",
            "up",
            "-d",
            "--no-deps",
            "postgres",
        ]
    )
    for attempt in range(30):
        try:
            _run(
                [
                    "docker",
                    "compose",
                    "exec",
                    "-T",
                    "postgres",
                    "pg_isready",
                    "--username",
                    "trading_agent",
                    "--dbname",
                    "trading_agent",
                ]
            )
            break
        except subprocess.CalledProcessError:
            if attempt == 29:
                raise
            time.sleep(1)

    sql = f"""
DO $role$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN
        CREATE ROLE {ROLE} LOGIN PASSWORD '{password}';
    END IF;
END
$role$;
ALTER ROLE {ROLE} LOGIN PASSWORD '{password}';
GRANT CONNECT ON DATABASE trading_agent TO {ROLE};
GRANT USAGE ON SCHEMA trading_agent TO {ROLE};
GRANT SELECT ON ALL TABLES IN SCHEMA trading_agent TO {ROLE};
GRANT SELECT ON ALL SEQUENCES IN SCHEMA trading_agent TO {ROLE};
ALTER DEFAULT PRIVILEGES FOR ROLE trading_agent IN SCHEMA trading_agent
GRANT SELECT ON TABLES TO {ROLE};
ALTER DEFAULT PRIVILEGES FOR ROLE trading_agent IN SCHEMA trading_agent
GRANT SELECT ON SEQUENCES TO {ROLE};
"""
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
        stdin=sql,
    )

    verify_env = os.environ.copy()
    verify_env.update(
        {
            "PGHOST": "127.0.0.1",
            "PGPORT": PORT,
            "PGDATABASE": "trading_agent",
            "PGUSER": ROLE,
            "PGPASSWORD": password,
        }
    )
    verification = subprocess.run(
        [
            "psql",
            "--no-psqlrc",
            "--tuples-only",
            "--no-align",
            "--command",
            "SELECT has_schema_privilege(current_user, 'trading_agent', 'USAGE') "
            "AND NOT has_schema_privilege(current_user, 'trading_agent', 'CREATE') "
            "AND has_table_privilege("
            "current_user, 'trading_agent.factor_definitions', 'SELECT') "
            "AND NOT has_table_privilege("
            "current_user, 'trading_agent.factor_definitions', 'INSERT')",
        ],
        cwd=ROOT,
        env=verify_env,
        capture_output=True,
        text=True,
        check=True,
    )
    if verification.stdout.strip() != "t":
        raise RuntimeError("pgAdmin role permissions did not pass read-only verification")
    print("pgAdmin access is ready on 127.0.0.1 using the configured local port.")
    print(f"Private connection details were saved to: {CREDENTIAL_FILE}")
    print("The pgAdmin role is read-only and the credential file is excluded from Git.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or "database command failed").strip().splitlines()[-1]
        print(f"pgAdmin setup failed safely: {message}", file=sys.stderr)
        raise SystemExit(1) from None
