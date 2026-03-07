from pydantic import BaseModel


class FundInfoResponse(BaseModel):
    fund_code: str
    fund_name: str
    fund_type: str | None = None
    estimated_nav: float | None = None
    unit_nav: float | None = None
    change_rate: float | None = None
    nav_date: str | None = None
    source: str


class FundHistoryPoint(BaseModel):
    nav_date: str
    unit_nav: float
    change_rate: float | None = None


class FundHistoryResponse(BaseModel):
    fund_code: str
    fund_name: str
    source: str
    points: list[FundHistoryPoint]
