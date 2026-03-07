from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.position import PositionRepository
from app.schemas.valuation import FundValuationItem, FundValuationRequest, PortfolioValuationResponse
from app.services.fund_data import FundDataService
from app.services.valuation import ValuationService

router = APIRouter()
valuation_service = ValuationService(FundDataService())


@router.post("/fund", response_model=FundValuationItem)
def valuate_fund(payload: FundValuationRequest, db: Session = Depends(get_db)) -> FundValuationItem:
    return valuation_service.valuate_fund(payload, db=db)


@router.get("/portfolio", response_model=PortfolioValuationResponse)
def valuate_portfolio(refresh: bool = Query(default=False), db: Session = Depends(get_db)) -> PortfolioValuationResponse:
    repo = PositionRepository(db)
    return valuation_service.valuate_portfolio(repo.list_all(), db=db, refresh=refresh)
