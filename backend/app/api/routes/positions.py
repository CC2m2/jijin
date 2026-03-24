from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.db.session import get_db
from app.repositories.position import PositionRepository
from app.schemas.position import PositionCreate, PositionResponse, PositionUpdate
from app.services.fund_data import FundDataService

router = APIRouter()
fund_data_service = FundDataService()


def _calculate_position_values(fund_code: str, position_date, amount: float) -> tuple[float, float, float]:
    unit_nav = fund_data_service.find_unit_nav_by_date(fund_code=fund_code, target_date=position_date)
    if unit_nav is None or unit_nav <= 0:
        return 0.0, 0.0, round(amount, 2)
    shares = round(amount / unit_nav, 6)
    avg_cost = round(unit_nav, 4)
    return shares, avg_cost, 0.0


def _apply_buy_trade(current_shares: float, current_avg_cost: float, amount: float, unit_nav: float) -> tuple[float, float]:
    added_shares = amount / unit_nav
    if current_shares <= 0:
        return round(added_shares, 6), round(unit_nav, 4)

    current_cost = current_shares * current_avg_cost
    new_shares = current_shares + added_shares
    new_avg_cost = (current_cost + amount) / new_shares
    return round(new_shares, 6), round(new_avg_cost, 4)


def _apply_sell_trade(current_shares: float, current_avg_cost: float, amount: float, unit_nav: float) -> tuple[float, float]:
    sold_shares = amount / unit_nav
    if sold_shares > current_shares + 1e-6:
        raise AppError("卖出份额超过当前可用持仓")

    remain_shares = max(current_shares - sold_shares, 0.0)
    if remain_shares <= 1e-6:
        return 0.0, 0.0
    return round(remain_shares, 6), round(current_avg_cost, 4)


@router.get("", response_model=list[PositionResponse])
def list_positions(db: Session = Depends(get_db)) -> list[PositionResponse]:
    repo = PositionRepository(db)
    return [PositionResponse.model_validate(item) for item in repo.list_all()]


@router.post("", response_model=PositionResponse, status_code=status.HTTP_201_CREATED)
def create_position(payload: PositionCreate, db: Session = Depends(get_db)) -> PositionResponse:
    if payload.trade_type == "sell":
        raise AppError("首次录入持仓不支持卖出，请先买入后再卖出")

    repo = PositionRepository(db)
    shares, avg_cost, pending_amount = _calculate_position_values(
        fund_code=payload.fund_code,
        position_date=payload.position_date,
        amount=payload.amount,
    )
    fund_name = None
    try:
        fund_name = fund_data_service.get_fund_info(payload.fund_code).get("fund_name")
    except Exception:
        fund_name = None
    position = repo.create(payload, shares=shares, avg_cost=avg_cost, pending_amount=pending_amount, fund_name=fund_name)
    return PositionResponse.model_validate(position)


@router.put("/{position_id}", response_model=PositionResponse)
def update_position(position_id: int, payload: PositionUpdate, db: Session = Depends(get_db)) -> PositionResponse:
    repo = PositionRepository(db)
    existing = repo.get(position_id)

    effective_fund_code = payload.fund_code or existing.fund_code
    effective_position_date = payload.position_date or existing.position_date
    amount = payload.amount
    shares = None
    avg_cost = None
    pending_amount = None

    if amount is not None:
        unit_nav = fund_data_service.find_unit_nav_by_date(
            fund_code=effective_fund_code,
            target_date=effective_position_date,
        )
        if unit_nav is None or unit_nav <= 0:
            pending_delta = round(amount, 2) if payload.trade_type == "buy" else -round(amount, 2)
            pending_amount = round(existing.pending_amount + pending_delta, 2)
        else:
            pending_amount = round(existing.pending_amount, 2)
            if payload.trade_type == "buy":
                shares, avg_cost = _apply_buy_trade(
                    current_shares=existing.shares,
                    current_avg_cost=existing.avg_cost,
                    amount=amount,
                    unit_nav=unit_nav,
                )
            else:
                shares, avg_cost = _apply_sell_trade(
                    current_shares=existing.shares,
                    current_avg_cost=existing.avg_cost,
                    amount=amount,
                    unit_nav=unit_nav,
                )

    fund_name = None
    if payload.fund_code:
        try:
            fund_name = fund_data_service.get_fund_info(payload.fund_code).get("fund_name")
        except Exception:
            fund_name = None
    position = repo.update(
        position_id,
        payload,
        shares=shares,
        avg_cost=avg_cost,
        pending_amount=pending_amount,
        fund_name=fund_name,
    )
    return PositionResponse.model_validate(position)


@router.delete("/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_position(position_id: int, db: Session = Depends(get_db)) -> Response:
    repo = PositionRepository(db)
    repo.delete(position_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
