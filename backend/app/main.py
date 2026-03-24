import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import AppError
from app.db.base import Base
from app.db.session import engine
from app.models import fund_snapshot, position  # noqa: F401

logger = logging.getLogger("app.request")


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
        if "pending_amount" not in columns:
            connection.exec_driver_sql("ALTER TABLE positions ADD COLUMN pending_amount FLOAT DEFAULT 0")
            connection.exec_driver_sql("UPDATE positions SET pending_amount = 0 WHERE pending_amount IS NULL")


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


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    start_time = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        cost_ms = int((time.perf_counter() - start_time) * 1000)
        logger.exception(
            "request failed method=%s path=%s request_id=%s cost_ms=%s",
            request.method,
            request.url.path,
            request_id,
            cost_ms,
        )
        raise

    response.headers["X-Request-ID"] = request_id
    cost_ms = int((time.perf_counter() - start_time) * 1000)
    logger.info(
        "request method=%s path=%s status_code=%s request_id=%s cost_ms=%s",
        request.method,
        request.url.path,
        response.status_code,
        request_id,
        cost_ms,
    )
    return response


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "message": exc.message})


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"code": "INTERNAL_ERROR", "message": str(exc)})


app.include_router(api_router, prefix=settings.api_v1_prefix)
