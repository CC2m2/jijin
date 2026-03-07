from pydantic import BaseModel


class FundValuationRequest(BaseModel):
    fund_code: str
    position_date: str | None = None
    shares: float
    avg_cost: float
    refresh: bool = False


class FundValuationItem(BaseModel):
    fund_code: str
    fund_name: str | None = None
    position_date: str | None = None
    shares: float
    avg_cost: float
    estimated_nav: float | None = None
    unit_nav: float | None = None
    market_value: float | None = None
    cost_value: float
    profit: float | None = None
    profit_rate: float | None = None
    change_rate: float | None = None
    nav_date: str | None = None
    source: str | None = None
    status: str = "success"
    error: str | None = None


class PortfolioValuationResponse(BaseModel):
    total_cost: float
    total_market_value: float
    total_profit: float
    total_profit_rate: float | None
    success_count: int
    failed_count: int
    items: list[FundValuationItem]
