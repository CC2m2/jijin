from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.position import PositionRepository
from app.schemas.position import PositionCreate, PositionResponse, PositionUpdate
from app.services.fund_data import FundDataService

router = APIRouter()
fund_data_service = FundDataService()


@router.get("", response_model=list[PositionResponse])
def list_positions(db: Session = Depends(get_db)) -> list[PositionResponse]:
    repo = PositionRepository(db)
    return [PositionResponse.model_validate(item) for item in repo.list_all()]


@router.post("", response_model=PositionResponse, status_code=status.HTTP_201_CREATED)
def create_position(payload: PositionCreate, db: Session = Depends(get_db)) -> PositionResponse:
    repo = PositionRepository(db)
    fund_name = None
    try:
        fund_name = fund_data_service.get_fund_info(payload.fund_code).get("fund_name")
    except Exception:
        fund_name = None
    position = repo.create(payload, fund_name=fund_name)
    return PositionResponse.model_validate(position)


@router.put("/{position_id}", response_model=PositionResponse)
def update_position(position_id: int, payload: PositionUpdate, db: Session = Depends(get_db)) -> PositionResponse:
    repo = PositionRepository(db)
    fund_name = None
    if payload.fund_code:
        try:
            fund_name = fund_data_service.get_fund_info(payload.fund_code).get("fund_name")
        except Exception:
            fund_name = None
    position = repo.update(position_id, payload, fund_name=fund_name)
    return PositionResponse.model_validate(position)


@router.delete("/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_position(position_id: int, db: Session = Depends(get_db)) -> Response:
    repo = PositionRepository(db)
    repo.delete(position_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
