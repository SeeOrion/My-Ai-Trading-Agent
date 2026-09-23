import pytest

from ai_trading_agent.infrastructure.config.providers import (
    AShareQuoteFailoverSettings,
    AiSimulationSchedulerSettings,
    FutuSettings,
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
