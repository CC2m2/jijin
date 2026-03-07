from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class PositionBase(BaseModel):
    fund_code: str = Field(min_length=4, max_length=32)
    position_date: date
    shares: float = Field(gt=0)
    avg_cost: float = Field(gt=0)

    @field_validator("fund_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("基金代码不能为空")
        return value


class PositionCreate(PositionBase):
    pass


class PositionUpdate(BaseModel):
    fund_code: str | None = Field(default=None, min_length=4, max_length=32)
    position_date: date | None = None
    shares: float | None = Field(default=None, gt=0)
    avg_cost: float | None = Field(default=None, gt=0)

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
    id: int
    fund_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
