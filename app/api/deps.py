# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from typing import Generator

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.application.auth.otp_service import OtpService
from app.application.auth.token_service import TokenService
from app.application.auth.usecase import AuthUsecase
from app.application.history.usecase import HistoryUsecase
from app.application.profile.usecase import ProfileUsecase
from app.application.ws.voice_ws_handler import VoiceWsHandler
from app.common.errors import UnauthorizedError
from app.domain import models
from app.infra.db import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

_otp_singleton = OtpService()
_token_singleton = TokenService()
_auth_uc_singleton = AuthUsecase(_otp_singleton, _token_singleton)
_profile_uc_singleton = ProfileUsecase()
_history_uc_singleton = HistoryUsecase()
_voice_ws_handler_singleton = VoiceWsHandler()


def get_auth_usecase() -> AuthUsecase:
    return _auth_uc_singleton


def get_profile_usecase() -> ProfileUsecase:
    return _profile_uc_singleton


def get_history_usecase() -> HistoryUsecase:
    return _history_uc_singleton


def get_voice_ws_handler() -> VoiceWsHandler:
    return _voice_ws_handler_singleton

_bearer = HTTPBearer(auto_error=False)


def get_current_parent(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> models.Parent:
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError(code="TOKEN_MISSING", message="missing access token")

    payload = _token_singleton.decode_access_token(credentials.credentials)
    try:
        parent_id = int(payload.get("sub"))
    except Exception as e:  # noqa: BLE001
        raise UnauthorizedError(code="TOKEN_INVALID", message="invalid access token") from e

    parent = db.get(models.Parent, parent_id)
    if parent is None:
        raise UnauthorizedError(code="TOKEN_USER_NOT_FOUND", message="parent not found")
    return parent
