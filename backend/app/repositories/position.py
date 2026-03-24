from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.position import Position
from app.schemas.position import PositionCreate, PositionUpdate


class PositionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[Position]:
        return list(self.db.scalars(select(Position).order_by(Position.position_date.desc(), Position.created_at.desc())))

    def get(self, position_id: int) -> Position:
        position = self.db.get(Position, position_id)
        if not position:
            raise NotFoundError("持仓不存在")
        return position

    def create(
        self,
        payload: PositionCreate,
        shares: float,
        avg_cost: float,
        pending_amount: float,
        fund_name: str | None = None,
    ) -> Position:
        position = Position(
            fund_code=payload.fund_code,
            fund_name=fund_name,
            position_date=payload.position_date,
            shares=shares,
            avg_cost=avg_cost,
            pending_amount=pending_amount,
        )
        self.db.add(position)
        self.db.commit()
        self.db.refresh(position)
        return position

    def update(
        self,
        position_id: int,
        payload: PositionUpdate,
        shares: float | None = None,
        avg_cost: float | None = None,
        pending_amount: float | None = None,
        fund_name: str | None = None,
    ) -> Position:
        position = self.get(position_id)
        updates = payload.model_dump(exclude={"amount", "trade_type"}, exclude_unset=True)
        for key, value in updates.items():
            setattr(position, key, value)
        if shares is not None:
            position.shares = shares
        if avg_cost is not None:
            position.avg_cost = avg_cost
        if pending_amount is not None:
            position.pending_amount = pending_amount
        if fund_name is not None:
            position.fund_name = fund_name
        self.db.commit()
        self.db.refresh(position)
        return position

    def delete(self, position_id: int) -> None:
        position = self.get(position_id)
        self.db.delete(position)
        self.db.commit()
