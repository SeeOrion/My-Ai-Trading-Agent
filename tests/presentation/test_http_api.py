from fastapi.testclient import TestClient

from ai_trading_agent.presentation.http.app import create_app


def test_health_endpoint_is_available() -> None:
    response = TestClient(create_app()).get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_factor_library_exposes_declarative_factor_contract() -> None:
    response = TestClient(create_app()).get("/api/v1/factors/earnings_yield")

    assert response.status_code == 200
    assert response.json()["columns_required"] == ["fund:pe_ttm"]


def test_missing_factor_returns_not_found() -> None:
    response = TestClient(create_app()).get("/api/v1/factors/does_not_exist")

    assert response.status_code == 404
