"""Runtime configuration adapter that never exposes credentials to callers."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_runtime_environment() -> None:
    root_env = Path(__file__).resolve().parents[5] / ".env"
    backend_env = Path.cwd() / ".env"
    load_dotenv(root_env, override=False)
    load_dotenv(backend_env, override=False)
