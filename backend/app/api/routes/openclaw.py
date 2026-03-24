from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import verify_openclaw_token
from app.core.exceptions import AppError, ExternalDataError
from app.db.session import get_db
from app.repositories.position import PositionRepository
from app.schemas.fund import FundHistoryResponse, FundInfoResponse
from app.schemas.openclaw import (
    OpenClawFundBriefRequest,
    OpenClawFundHistoryRequest,
    OpenClawPortfolioRequest,
    OpenClawToolError,
    OpenClawToolMeta,
    OpenClawToolResponse,
)
from app.schemas.valuation import PortfolioValuationResponse
from app.services.fund_data import FundDataService
from app.services.valuation import ValuationService

router = APIRouter()
logger = logging.getLogger("app.openclaw")

fund_data_service = FundDataService()
valuation_service = ValuationService(FundDataService())


def _request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    return request_id if isinstance(request_id, str) and request_id else "unknown"


def _elapsed_ms(start_time: float) -> int:
    return max(0, int((time.perf_counter() - start_time) * 1000))


def _map_error(exc: AppError) -> tuple[str, str]:
    message = exc.message
    if isinstance(exc, ExternalDataError):
        lowered = message.lower()
        if "超时" in message or "timed out" in lowered or "timeout" in lowered:
            return "UPSTREAM_TIMEOUT", message
        return "EXTERNAL_DATA_ERROR", message
    return exc.code, message


def _error_response(
    *,
    tool: str,
    request: Request,
    start_time: float,
    status_code: int,
    error_code: str,
    message: str,
) -> JSONResponse:
    request_id = _request_id(request)
    cost_ms = _elapsed_ms(start_time)
    logger.warning(
        "openclaw tool=%s request_id=%s status_code=%s cost_ms=%s error_code=%s",
        tool,
        request_id,
        status_code,
        cost_ms,
        error_code,
    )
    payload = OpenClawToolResponse(
        ok=False,
        request_id=request_id,
        tool=tool,
        data=None,
        error=OpenClawToolError(code=error_code, message=message),
        meta=OpenClawToolMeta(cost_ms=cost_ms),
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


@router.get("/health", response_model=OpenClawToolResponse)
def openclaw_health(request: Request) -> OpenClawToolResponse:
    start_time = time.perf_counter()
    request_id = _request_id(request)
    payload = OpenClawToolResponse(
        ok=True,
        request_id=request_id,
        tool="health",
        data={"status": "ok"},
        error=None,
        meta=OpenClawToolMeta(cost_ms=_elapsed_ms(start_time)),
    )
    logger.info("openclaw tool=health request_id=%s status_code=200 cost_ms=%s", request_id, payload.meta.cost_ms)
    return payload


@router.post("/tools/portfolio_valuation", response_model=OpenClawToolResponse, dependencies=[Depends(verify_openclaw_token)])
def openclaw_portfolio_valuation(
    body: OpenClawPortfolioRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> OpenClawToolResponse | JSONResponse:
    start_time = time.perf_counter()
    tool = "portfolio_valuation"
    try:
        repo = PositionRepository(db)
        result: PortfolioValuationResponse = valuation_service.valuate_portfolio(repo.list_all(), db=db, refresh=body.refresh)
        request_id = _request_id(request)
        cost_ms = _elapsed_ms(start_time)
        logger.info("openclaw tool=%s request_id=%s status_code=200 cost_ms=%s", tool, request_id, cost_ms)
        return OpenClawToolResponse(
            ok=True,
            request_id=request_id,
            tool=tool,
            data=result.model_dump(),
            error=None,
            meta=OpenClawToolMeta(cost_ms=cost_ms),
        )
    except AppError as exc:
        error_code, message = _map_error(exc)
        return _error_response(
            tool=tool,
            request=request,
            start_time=start_time,
            status_code=exc.status_code,
            error_code=error_code,
            message=message,
        )
    except Exception as exc:
        return _error_response(
            tool=tool,
            request=request,
            start_time=start_time,
            status_code=500,
            error_code="INTERNAL_ERROR",
            message=str(exc),
        )


@router.post("/tools/fund_brief", response_model=OpenClawToolResponse, dependencies=[Depends(verify_openclaw_token)])
def openclaw_fund_brief(body: OpenClawFundBriefRequest, request: Request) -> OpenClawToolResponse | JSONResponse:
    start_time = time.perf_counter()
    tool = "fund_brief"
    try:
        result = FundInfoResponse(**fund_data_service.get_fund_info(fund_code=body.fund_code, refresh=body.refresh))
        request_id = _request_id(request)
        cost_ms = _elapsed_ms(start_time)
        logger.info("openclaw tool=%s request_id=%s status_code=200 cost_ms=%s", tool, request_id, cost_ms)
        return OpenClawToolResponse(
            ok=True,
            request_id=request_id,
            tool=tool,
            data=result.model_dump(),
            error=None,
            meta=OpenClawToolMeta(cost_ms=cost_ms),
        )
    except AppError as exc:
        error_code, message = _map_error(exc)
        return _error_response(
            tool=tool,
            request=request,
            start_time=start_time,
            status_code=exc.status_code,
            error_code=error_code,
            message=message,
        )
    except Exception as exc:
        return _error_response(
            tool=tool,
            request=request,
            start_time=start_time,
            status_code=500,
            error_code="INTERNAL_ERROR",
            message=str(exc),
        )


@router.post("/tools/fund_history", response_model=OpenClawToolResponse, dependencies=[Depends(verify_openclaw_token)])
def openclaw_fund_history(body: OpenClawFundHistoryRequest, request: Request) -> OpenClawToolResponse | JSONResponse:
    start_time = time.perf_counter()
    tool = "fund_history"
    try:
        history_payload = fund_data_service.get_fund_history(fund_code=body.fund_code, refresh=body.refresh)
        if body.max_points > 0:
            points = history_payload.get("points") or []
            history_payload["points"] = points[: body.max_points]
        result = FundHistoryResponse(**history_payload)
        request_id = _request_id(request)
        cost_ms = _elapsed_ms(start_time)
        logger.info("openclaw tool=%s request_id=%s status_code=200 cost_ms=%s", tool, request_id, cost_ms)
        return OpenClawToolResponse(
            ok=True,
            request_id=request_id,
            tool=tool,
            data=result.model_dump(),
            error=None,
            meta=OpenClawToolMeta(cost_ms=cost_ms),
        )
    except AppError as exc:
        error_code, message = _map_error(exc)
        return _error_response(
            tool=tool,
            request=request,
            start_time=start_time,
            status_code=exc.status_code,
            error_code=error_code,
            message=message,
        )
    except Exception as exc:
        return _error_response(
            tool=tool,
            request=request,
            start_time=start_time,
            status_code=500,
            error_code="INTERNAL_ERROR",
            message=str(exc),
        )
