from __future__ import annotations

import secrets

from fastapi import Header

from app.core.config import settings
from app.core.exceptions import AppError


OPENCLAW_TOKEN_HEADER = "X-OpenClaw-Token"


def verify_openclaw_token(x_openclaw_token: str | None = Header(default=None)) -> None:
    configured_token = settings.openclaw_token
    if not configured_token:
        raise AppError("OPENCLAW_TOKEN is not configured", status_code=503, code="OPENCLAW_TOKEN_MISSING")

    if not x_openclaw_token or not secrets.compare_digest(x_openclaw_token, configured_token):
        raise AppError("Unauthorized", status_code=401, code="UNAUTHORIZED")
