from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OpenClawToolMeta(BaseModel):
    cost_ms: int
    source: str = "jijin-backend"


class OpenClawToolError(BaseModel):
    code: str
    message: str


class OpenClawToolResponse(BaseModel):
    ok: bool
    request_id: str
    tool: str
    data: Any = None
    error: OpenClawToolError | None = None
    meta: OpenClawToolMeta


class OpenClawPortfolioRequest(BaseModel):
    refresh: bool = False


class OpenClawFundBriefRequest(BaseModel):
    fund_code: str
    refresh: bool = False


class OpenClawFundHistoryRequest(BaseModel):
    fund_code: str
    refresh: bool = False
    max_points: int = 60


class OpenClawMarketOverviewRequest(BaseModel):
    refresh: bool = False
    board_limit: int = Field(default=5, ge=1, le=20)


class OpenClawMarketAnalysisRequest(BaseModel):
    refresh: bool = False
    board_limit: int = Field(default=5, ge=1, le=20)
    max_positions: int = Field(default=8, ge=1, le=20)
