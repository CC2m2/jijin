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
                source=fund_info.get("source") or "tiantian-fund",
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

    def _try_confirm_pending_position(self, position: Position, db: Session | None, refresh: bool = False) -> None:
        if db is None or abs(position.pending_amount) <= 1e-9:
            return

        unit_nav = self.fund_data_service.find_unit_nav_by_date(
            fund_code=position.fund_code,
            target_date=position.position_date,
            refresh=refresh,
        )
        if unit_nav is None or unit_nav <= 0:
            return

        if position.pending_amount > 0:
            added_shares = position.pending_amount / unit_nav
            if position.shares <= 0:
                position.shares = round(added_shares, 6)
                position.avg_cost = round(unit_nav, 4)
            else:
                current_cost = position.shares * position.avg_cost
                position.shares = round(position.shares + added_shares, 6)
                position.avg_cost = round((current_cost + position.pending_amount) / position.shares, 4)
        else:
            sold_shares = abs(position.pending_amount) / unit_nav
            remain_shares = max(position.shares - sold_shares, 0.0)
            position.shares = round(remain_shares, 6)
            if position.shares <= 1e-6:
                position.shares = 0.0
                position.avg_cost = 0.0

        position.pending_amount = 0.0
        db.commit()
        db.refresh(position)

    def valuate_portfolio(self, positions: list[Position], db: Session | None = None, refresh: bool = False) -> PortfolioValuationResponse:
        items: list[FundValuationItem] = []
        total_cost = 0.0
        total_market_value = 0.0
        failed_count = 0

        for position in positions:
            self._try_confirm_pending_position(position, db=db, refresh=refresh)

            if abs(position.pending_amount) > 1e-9:
                failed_count += 1
                cost_value = round(position.shares * position.avg_cost + position.pending_amount, 4)
                total_cost += cost_value

                pending_fund_info: dict[str, object] = {}
                try:
                    pending_fund_info = self.fund_data_service.get_fund_info(position.fund_code, refresh=refresh)
                except Exception:
                    pending_fund_info = {}

                pending_label = "待确认金额" if position.pending_amount > 0 else "待卖出金额"
                items.append(
                    FundValuationItem(
                        fund_code=position.fund_code,
                        fund_name=(pending_fund_info.get("fund_name") if pending_fund_info else None) or position.fund_name,
                        position_date=position.position_date.isoformat() if position.position_date else None,
                        shares=position.shares,
                        avg_cost=position.avg_cost,
                        estimated_nav=pending_fund_info.get("estimated_nav") if pending_fund_info else None,
                        unit_nav=pending_fund_info.get("unit_nav") if pending_fund_info else None,
                        change_rate=pending_fund_info.get("change_rate") if pending_fund_info else None,
                        nav_date=pending_fund_info.get("nav_date") if pending_fund_info else None,
                        source=pending_fund_info.get("source") if pending_fund_info else None,
                        cost_value=cost_value,
                        status="failed",
                        error=f"{abs(position.pending_amount):.2f} 元{pending_label}，净值更新后将自动确认份额",
                    )
                )
                continue

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
