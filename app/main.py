# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import auth as auth_api, history as history_api, parents as parents_api, voice_ws as voice_ws_api
from app.common.exception_handlers import app_error_handler, unhandled_error_handler, validation_error_handler
from app.common.logging import setup_logging
from app.common.middlewares import TraceIdMiddleware
from app.common.errors import AppError
from fastapi.exceptions import RequestValidationError
from app.infra.config import settings
import os

setup_logging()

app = FastAPI(
    title="yoo-growth-buddy",
    version="1.0.0",
)


# 本地文件服务（当 S3 未配置时，audio 会落本地）
if settings.FILE_BASE_PATH:
    os.makedirs(settings.FILE_BASE_PATH, exist_ok=True)
    app.mount("/files", StaticFiles(directory=settings.FILE_BASE_PATH), name="files")


# ---------- middlewares / handlers ----------

app.add_middleware(TraceIdMiddleware)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


# Auth
app.include_router(auth_api.router)

# 家长相关接口
app.include_router(parents_api.router)
app.include_router(history_api.router)

# 语音 WebSocket
app.include_router(voice_ws_api.router)
