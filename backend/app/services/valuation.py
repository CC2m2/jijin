from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.fund_snapshot import FundSnapshot
from app.models.position import Position
from app.schemas.valuation import FundValuationItem, FundValuationRequest, PortfolioValuationResponse
from app.services.fund_data import FundDataService


@dataclass
class ValuationMetrics:
    market_value: float
    cost_value: float
    profit: float
    profit_rate: float | None


class ValuationService:
    def __init__(self, fund_data_service: FundDataService) -> None:
        self.fund_data_service = fund_data_service

    @staticmethod
    def calculate_metrics(shares: float, avg_cost: float, current_price: float) -> ValuationMetrics:
        cost_value = round(shares * avg_cost, 4)
        market_value = round(shares * current_price, 4)
        profit = round(market_value - cost_value, 4)
        profit_rate = round(profit / cost_value, 6) if cost_value else None
        return ValuationMetrics(
            market_value=market_value,
            cost_value=cost_value,
            profit=profit,
            profit_rate=profit_rate,
        )

    def valuate_fund(self, payload: FundValuationRequest, db: Session | None = None) -> FundValuationItem:
        fund_info = self.fund_data_service.get_fund_info(payload.fund_code, refresh=payload.refresh)
        price = fund_info.get("estimated_nav") or fund_info.get("unit_nav")
        if price is None:
            raise ValueError(f"基金 {payload.fund_code} 缺少估值和净值数据")
        metrics = self.calculate_metrics(payload.shares, payload.avg_cost, price)

        if db is not None:
            snapshot = FundSnapshot(
                fund_code=payload.fund_code,
                nav_date=None,
                unit_nav=fund_info.get("unit_nav"),
                estimated_nav=fund_info.get("estimated_nav"),
                change_rate=fund_info.get("change_rate"),
                source=fund_info.get("source") or "akshare",
            )
            db.add(snapshot)
            db.commit()

        return FundValuationItem(
            fund_code=payload.fund_code,
            fund_name=fund_info.get("fund_name"),
            position_date=payload.position_date,
            shares=payload.shares,
            avg_cost=payload.avg_cost,
            estimated_nav=fund_info.get("estimated_nav"),
            unit_nav=fund_info.get("unit_nav"),
            market_value=metrics.market_value,
            cost_value=metrics.cost_value,
            profit=metrics.profit,
            profit_rate=metrics.profit_rate,
            change_rate=fund_info.get("change_rate"),
            nav_date=fund_info.get("nav_date"),
            source=fund_info.get("source"),
        )

    def valuate_portfolio(self, positions: list[Position], db: Session | None = None, refresh: bool = False) -> PortfolioValuationResponse:
        items: list[FundValuationItem] = []
        total_cost = 0.0
        total_market_value = 0.0
        failed_count = 0

        for position in positions:
            try:
                item = self.valuate_fund(
                    FundValuationRequest(
                        fund_code=position.fund_code,
                        position_date=position.position_date.isoformat() if position.position_date else None,
                        shares=position.shares,
                        avg_cost=position.avg_cost,
                        refresh=refresh,
                    ),
                    db=db,
                )
                items.append(item)
                total_cost += item.cost_value
                total_market_value += item.market_value or 0.0
            except Exception as exc:
                failed_count += 1
                cost_value = round(position.shares * position.avg_cost, 4)
                total_cost += cost_value
                items.append(
                    FundValuationItem(
                        fund_code=position.fund_code,
                        fund_name=position.fund_name,
                        position_date=position.position_date.isoformat() if position.position_date else None,
                        shares=position.shares,
                        avg_cost=position.avg_cost,
                        cost_value=cost_value,
                        status="failed",
                        error=str(exc),
                    )
                )

        total_profit = round(total_market_value - total_cost, 4)
        total_profit_rate = round(total_profit / total_cost, 6) if total_cost else None
        return PortfolioValuationResponse(
            total_cost=round(total_cost, 4),
            total_market_value=round(total_market_value, 4),
            total_profit=total_profit,
            total_profit_rate=total_profit_rate,
            success_count=len(items) - failed_count,
            failed_count=failed_count,
            items=items,
        )
