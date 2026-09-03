import pytest

from ai_trading_agent.infrastructure.config.providers import (
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
