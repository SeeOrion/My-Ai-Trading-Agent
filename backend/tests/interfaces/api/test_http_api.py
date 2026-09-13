from fastapi.testclient import TestClient

from ai_trading_agent.interfaces.api.app import create_app


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


def test_personal_discipline_routes_are_part_of_the_http_contract() -> None:
    response = TestClient(create_app()).get("/openapi.json")

    assert "/api/v1/disciplines" in response.json()["paths"]


def test_dashboard_contract_exposes_market_brief_and_market_question() -> None:
    schema = TestClient(create_app()).get("/openapi.json").json()

    assert "/api/v1/assistant/market-question" in schema["paths"]
    assert "/api/v1/market/post-market-brief" in schema["paths"]
    response_schema = schema["components"]["schemas"]["PostMarketBriefResponse"]
    assert "leading_sectors" in response_schema["properties"]
    answer_schema = schema["components"]["schemas"]["MarketQuestionResponse"]
    assert "candidates" in answer_schema["properties"]


def test_watchlist_analysis_contract_exposes_saved_labels() -> None:
    schema = TestClient(create_app()).get("/openapi.json").json()

    assert "/api/v1/watchlist/analyses" in schema["paths"]
    assert "tags" in schema["components"]["schemas"]["WatchlistAnalysisResponse"]["properties"]


def test_watchlist_contract_exposes_single_instrument_financial_detail() -> None:
    schema = TestClient(create_app()).get("/openapi.json").json()

    assert "/api/v1/watchlist/{item_id}/deep-dive" in schema["paths"]
    response_schema = schema["components"]["schemas"]["WatchlistFinancialDetailResponse"]
    assert "valuation" in response_schema["properties"]


def test_paper_portfolio_contract_exposes_currency_safe_performance_summary() -> None:
    schema = TestClient(create_app()).get("/openapi.json").json()

    assert "/api/v1/paper-positions/overview" in schema["paths"]
    summary_schema = schema["components"]["schemas"]["PaperPortfolioCurrencySummaryResponse"]
    assert "month_to_date_pnl" in summary_schema["properties"]
    valuation_schema = schema["components"]["schemas"]["PaperPositionValuationResponse"]
    assert "daily_pnl" in valuation_schema["properties"]
    position_schema = schema["components"]["schemas"]["PaperPositionResponse"]
    assert "cost_amount" in position_schema["properties"]


def test_ai_simulation_contract_exposes_auditable_capital_and_positions() -> None:
    schema = TestClient(create_app()).get("/openapi.json").json()

    assert "/api/v1/ai-simulation/run" in schema["paths"]
    overview_schema = schema["components"]["schemas"]["AiSimulationOverviewResponse"]
    assert {"initial_capital", "cash_balance", "total_equity", "positions"} <= set(
        overview_schema["properties"]
    )
    position_schema = schema["components"]["schemas"]["AiSimulationPositionResponse"]
    assert {"cost_amount", "candidate_score", "factor_context", "rationale"} <= set(
        position_schema["properties"]
    )
