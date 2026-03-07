from app.services.valuation import ValuationService


def test_calculate_metrics() -> None:
    metrics = ValuationService.calculate_metrics(shares=1000, avg_cost=1.2356, current_price=0.9231)

    assert metrics.cost_value == 1235.6
    assert metrics.market_value == 923.1
    assert metrics.profit == -312.5
    assert metrics.profit_rate == -0.252914
