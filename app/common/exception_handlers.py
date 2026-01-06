# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.common.errors import AppError
from app.common.trace import get_trace_id

logger = logging.getLogger(__name__)


def _err_payload(code: str, message: str, detail: Any = None) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "code": code,
        "message": message,
        "trace_id": get_trace_id(),
    }
    if detail is not None:
        data["detail"] = detail
    return data


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:  # noqa: ARG001
    return JSONResponse(
        status_code=exc.status_code,
        content=_err_payload(exc.code, exc.message, exc.detail),
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:  # noqa: ARG001
    return JSONResponse(
        status_code=422,
        content=_err_payload(
            "VALIDATION_ERROR",
            "invalid request",
            detail=exc.errors(),
        ),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:  # noqa: ARG001
    logger.exception("Unhandled error")
    return JSONResponse(
        status_code=500,
        content=_err_payload("INTERNAL_ERROR", "internal server error"),
    )
