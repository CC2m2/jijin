from fastapi import APIRouter, Depends, Query

from app.schemas.fund import FundHistoryResponse, FundInfoResponse
from app.services.fund_data import FundDataService

router = APIRouter()
fund_data_service = FundDataService()


@router.get("/{fund_code}", response_model=FundInfoResponse)
def get_fund_info(fund_code: str, refresh: bool = Query(default=False)) -> FundInfoResponse:
    data = fund_data_service.get_fund_info(fund_code=fund_code, refresh=refresh)
    return FundInfoResponse(**data)


@router.get("/{fund_code}/history", response_model=FundHistoryResponse)
def get_fund_history(fund_code: str, refresh: bool = Query(default=False)) -> FundHistoryResponse:
    data = fund_data_service.get_fund_history(fund_code=fund_code, refresh=refresh)
    return FundHistoryResponse(**data)
