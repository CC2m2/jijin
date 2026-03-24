from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.exceptions import ExternalDataError
from app.main import app
from app.schemas.valuation import PortfolioValuationResponse


def test_openclaw_tools_require_token() -> None:
    settings.openclaw_token = "test-token"
    client = TestClient(app)

    response = client.post("/api/v1/openclaw/tools/portfolio_valuation", json={"refresh": False})

    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "UNAUTHORIZED"


def test_openclaw_portfolio_valuation_success(monkeypatch) -> None:
    from app.api.routes import openclaw

    settings.openclaw_token = "test-token"
    client = TestClient(app)

    expected = PortfolioValuationResponse(
        total_cost=1000.0,
        total_market_value=1080.0,
        total_profit=80.0,
        total_profit_rate=0.08,
        success_count=1,
        failed_count=0,
        items=[],
    )

    def fake_valuate_portfolio(*args, **kwargs):
        return expected

    monkeypatch.setattr(openclaw.valuation_service, "valuate_portfolio", fake_valuate_portfolio)

    response = client.post(
        "/api/v1/openclaw/tools/portfolio_valuation",
        json={"refresh": False},
        headers={"X-OpenClaw-Token": "test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["tool"] == "portfolio_valuation"
    assert body["data"]["total_market_value"] == 1080.0
    assert isinstance(body["meta"]["cost_ms"], int)


def test_openclaw_fund_brief_timeout_mapping(monkeypatch) -> None:
    from app.api.routes import openclaw

    settings.openclaw_token = "test-token"
    client = TestClient(app)

    def fake_get_fund_info(*args, **kwargs):
        raise ExternalDataError("外部数据源响应超时")

    monkeypatch.setattr(openclaw.fund_data_service, "get_fund_info", fake_get_fund_info)

    response = client.post(
        "/api/v1/openclaw/tools/fund_brief",
        json={"fund_code": "161725", "refresh": False},
        headers={"X-OpenClaw-Token": "test-token"},
    )

    assert response.status_code == 502
    body = response.json()
    assert body["ok"] is False
    assert body["tool"] == "fund_brief"
    assert body["error"]["code"] == "UPSTREAM_TIMEOUT"


def test_openclaw_market_overview_success(monkeypatch) -> None:
    from app.api.routes import openclaw

    settings.openclaw_token = "test-token"
    client = TestClient(app)

    def fake_market_overview(*args, **kwargs):
        return {
            "generated_at": "2026-03-24T22:30:00",
            "source": "eastmoney-push2",
            "indexes": [{"code": "000001", "name": "上证指数", "change_rate": 0.23}],
            "market_stats": {"average_index_change_rate": 0.2},
            "sector_rankings": {"leaders": [], "laggards": []},
        }

    monkeypatch.setattr(openclaw.market_analysis_service, "get_market_overview", fake_market_overview)

    response = client.post(
        "/api/v1/openclaw/tools/market_overview",
        json={"refresh": False, "board_limit": 5},
        headers={"X-OpenClaw-Token": "test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["tool"] == "market_overview"
    assert body["data"]["source"] == "eastmoney-push2"


def test_openclaw_market_analysis_timeout_mapping(monkeypatch) -> None:
    from app.api.routes import openclaw

    settings.openclaw_token = "test-token"
    client = TestClient(app)

    expected = PortfolioValuationResponse(
        total_cost=1000.0,
        total_market_value=980.0,
        total_profit=-20.0,
        total_profit_rate=-0.02,
        success_count=1,
        failed_count=0,
        items=[],
    )

    def fake_valuate_portfolio(*args, **kwargs):
        return expected

    def fake_market_overview(*args, **kwargs):
        raise ExternalDataError("东方财富超时")

    monkeypatch.setattr(openclaw.valuation_service, "valuate_portfolio", fake_valuate_portfolio)
    monkeypatch.setattr(openclaw.market_analysis_service, "get_market_overview", fake_market_overview)

    response = client.post(
        "/api/v1/openclaw/tools/market_analysis",
        json={"refresh": False, "board_limit": 5, "max_positions": 8},
        headers={"X-OpenClaw-Token": "test-token"},
    )

    assert response.status_code == 502
    body = response.json()
    assert body["ok"] is False
    assert body["tool"] == "market_analysis"
    assert body["error"]["code"] == "UPSTREAM_TIMEOUT"


def test_openclaw_market_analysis_no_suggestion_field(monkeypatch) -> None:
    from app.api.routes import openclaw

    settings.openclaw_token = "test-token"
    client = TestClient(app)

    expected = PortfolioValuationResponse(
        total_cost=1000.0,
        total_market_value=1020.0,
        total_profit=20.0,
        total_profit_rate=0.02,
        success_count=1,
        failed_count=0,
        items=[],
    )

    def fake_valuate_portfolio(*args, **kwargs):
        return expected

    def fake_market_overview(*args, **kwargs):
        return {
            "generated_at": "2026-03-24T23:00:00",
            "source": "eastmoney-push2",
            "indexes": [],
            "market_stats": {"average_index_change_rate": 0.12},
            "sector_rankings": {"leaders": [], "laggards": []},
        }

    monkeypatch.setattr(openclaw.valuation_service, "valuate_portfolio", fake_valuate_portfolio)
    monkeypatch.setattr(openclaw.market_analysis_service, "get_market_overview", fake_market_overview)

    response = client.post(
        "/api/v1/openclaw/tools/market_analysis",
        json={"refresh": False, "board_limit": 5, "max_positions": 8},
        headers={"X-OpenClaw-Token": "test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["tool"] == "market_analysis"
    assert "market_overview" in body["data"]
    assert "portfolio_performance" in body["data"]
    assert "position_distribution" in body["data"]
    assert "ai_suggestion" not in body["data"]
