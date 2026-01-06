# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict

import jwt

from app.common.errors import UnauthorizedError
from app.infra.config import settings


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_expires_in: int


class TokenService:
    def __init__(self) -> None:
        self._jwt_secret = settings.JWT_SECRET_KEY
        self._jwt_alg = "HS256"

    def make_access_token(self, *, parent_id: int, phone: str) -> TokenPair:
        now = int(time.time())
        access_exp = now + int(settings.ACCESS_TOKEN_EXPIRE_MINUTES) * 60
        refresh_exp = now + int(settings.REFRESH_TOKEN_EXPIRE_DAYS) * 86400

        payload: Dict[str, Any] = {
            "sub": str(parent_id),
            "phone": phone,
            "type": "access",
            "iat": now,
            "exp": access_exp,
        }
        access = jwt.encode(payload, self._jwt_secret, algorithm=self._jwt_alg)

        refresh = self._new_refresh_token()
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            expires_in=max(access_exp - now, 0),
            refresh_expires_in=max(refresh_exp - now, 0),
        )

    def decode_access_token(self, token: str) -> Dict[str, Any]:
        try:
            payload = jwt.decode(token, self._jwt_secret, algorithms=[self._jwt_alg])
        except Exception as e:  # noqa: BLE001
            raise UnauthorizedError(code="TOKEN_INVALID", message="invalid access token") from e

        if payload.get("type") != "access":
            raise UnauthorizedError(code="TOKEN_INVALID", message="invalid access token")
        return payload

    def hash_refresh_token(self, refresh_token: str) -> str:
        return hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()

    def refresh_expire_at(self) -> int:
        return int(time.time()) + int(settings.REFRESH_TOKEN_EXPIRE_DAYS) * 86400

    def _new_refresh_token(self) -> str:
        return secrets.token_urlsafe(48)
