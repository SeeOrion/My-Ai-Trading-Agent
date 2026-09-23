from pathlib import Path

import pytest

from ai_trading_agent.infrastructure.config.providers import (
    AiSimulationSchedulerSettings,
    AShareQuoteFailoverSettings,
    ClosingPlanSchedulerSettings,
    FutuSettings,
    HithinkFinanceSettings,
    ProviderConfigurationError,
    TushareSettings,
)


def test_tushare_settings_reject_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)

    with pytest.raises(ProviderConfigurationError, match="TUSHARE_TOKEN"):
        TushareSettings.from_environment()


def test_futu_settings_read_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FUTU_OPEND_HOST", "opend.local")
    monkeypatch.setenv("FUTU_OPEND_PORT", "22222")

    assert FutuSettings.from_environment() == FutuSettings(host="opend.local", port=22222)


def test_hithink_settings_read_explicit_private_credential_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    credential = tmp_path / "credentials.env"
    credential.write_text("HITHINK_FINANCE_API_KEY=test-private-key\n", encoding="utf-8")
    monkeypatch.delenv("HITHINK_FINANCE_API_KEY", raising=False)
    monkeypatch.setenv("HITHINK_FINANCE_CREDENTIALS_FILE", str(credential))

    settings = HithinkFinanceSettings.from_environment()

    assert settings.api_key == "test-private-key"


def test_a_share_failover_settings_read_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("A_SHARE_FUTU_TIMEOUT_SECONDS", "3.5")
    monkeypatch.setenv("A_SHARE_FUTU_COOLDOWN_SECONDS", "90")

    assert AShareQuoteFailoverSettings.from_environment() == AShareQuoteFailoverSettings(
        futu_timeout_seconds=3.5,
        futu_cooldown_seconds=90,
    )


def test_ai_simulation_scheduler_reads_bounded_run_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_SIMULATION_RUN_TIMEOUT_SECONDS", "420")

    assert AiSimulationSchedulerSettings.from_environment().run_timeout_seconds == 420


def test_closing_plan_scheduler_reads_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLOSING_PLAN_INTERVAL_SECONDS", "600")

    assert ClosingPlanSchedulerSettings.from_environment().interval_seconds == 600
