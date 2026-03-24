from fastapi import APIRouter

from app.api.routes import funds, health, openclaw, positions, valuation

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(positions.router, prefix="/positions", tags=["positions"])
api_router.include_router(funds.router, prefix="/funds", tags=["funds"])
api_router.include_router(valuation.router, prefix="/valuation", tags=["valuation"])
api_router.include_router(openclaw.router, prefix="/openclaw", tags=["openclaw"])
