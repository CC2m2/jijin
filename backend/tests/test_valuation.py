import time
from datetime import date

from app.models.position import Position
from app.services.valuation import ValuationService


def test_calculate_metrics() -> None:
    metrics = ValuationService.calculate_metrics(shares=1000, avg_cost=1.2356, current_price=0.9231)

    assert metrics.cost_value == 1235.6
    assert metrics.market_value == 923.1
    assert metrics.profit == -312.5
    assert metrics.profit_rate == -0.252914


def test_valuate_portfolio_fetches_fund_info_in_parallel() -> None:
    class FakeFundDataService:
        def get_fund_info(self, fund_code: str, refresh: bool = False):
            time.sleep(0.15)
            return {
                "fund_code": fund_code,
                "fund_name": f"fund-{fund_code}",
                "estimated_nav": 1.1,
                "unit_nav": 1.0,
                "change_rate": 0.01,
                "nav_date": date.today().isoformat(),
                "source": "fake",
            }

        def find_unit_nav_by_date(self, fund_code: str, target_date: date, refresh: bool = False):
            return None

    service = ValuationService(FakeFundDataService())
    positions = [
        Position(
            fund_code=f"00{i}",
            fund_name=f"fund-{i}",
            position_date=date.today(),
            shares=100.0,
            avg_cost=1.0,
            pending_amount=0.0,
        )
        for i in range(6)
    ]

    start = time.perf_counter()
    result = service.valuate_portfolio(positions=positions, db=None, refresh=False)
    elapsed = time.perf_counter() - start

    assert result.success_count == 6
    assert result.failed_count == 0
    assert elapsed < 0.7
