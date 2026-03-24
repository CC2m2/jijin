from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class PositionBase(BaseModel):
    fund_code: str = Field(min_length=4, max_length=32)
    position_date: date


    @field_validator("fund_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("基金代码不能为空")
        return value


class PositionCreate(PositionBase):
    amount: float = Field(gt=0)
    trade_type: Literal["buy", "sell"] = "buy"


class PositionUpdate(BaseModel):
    fund_code: str | None = Field(default=None, min_length=4, max_length=32)
    position_date: date | None = None
    amount: float | None = Field(default=None, gt=0)
    trade_type: Literal["buy", "sell"] = "buy"

    @field_validator("fund_code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("基金代码不能为空")
        return value


class PositionResponse(PositionBase):
    shares: float = Field(ge=0)
    avg_cost: float = Field(ge=0)
    pending_amount: float
    id: int
    fund_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
