from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import AppError
from app.db.base import Base
from app.db.session import engine
from app.models import fund_snapshot, position  # noqa: F401


def ensure_sqlite_schema() -> None:
    with engine.begin() as connection:
        columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(positions)").fetchall()
        }
        if "position_date" not in columns:
            connection.exec_driver_sql("ALTER TABLE positions ADD COLUMN position_date DATE")
            connection.exec_driver_sql(
                "UPDATE positions SET position_date = COALESCE(date(created_at), date('now')) WHERE position_date IS NULL"
            )


Base.metadata.create_all(bind=engine)
ensure_sqlite_schema()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "message": exc.message})


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"code": "INTERNAL_ERROR", "message": str(exc)})


app.include_router(api_router, prefix=settings.api_v1_prefix)
