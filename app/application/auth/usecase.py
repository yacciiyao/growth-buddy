# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.application.auth.otp_service import OtpService
from app.application.auth.token_service import TokenService
from app.common.errors import BadRequestError, NotFoundError, UnauthorizedError
from app.domain import models


class AuthUsecase:
    def __init__(self, otp: OtpService, tokens: TokenService) -> None:
        self._otp = otp
        self._tokens = tokens

    def send_code(self, phone: str, scene: str = "login") -> int:
        return self._otp.send_code(phone, scene=scene)

    def register(self, db: Session, *, phone: str, code: str, email: Optional[str] = None) -> "IssuedTokenPair":
        self._otp.verify_code(phone, code)

        existed = db.query(models.Parent).filter(models.Parent.phone == phone).first()
        if existed is not None:
            raise BadRequestError(code="PHONE_ALREADY_REGISTERED", message="phone already registered")

        parent = models.Parent(phone=phone, email=email)
        db.add(parent)
        db.commit()
        db.refresh(parent)

        return self._issue_tokens(db, parent)

    def login(self, db: Session, *, phone: str, code: str) -> "IssuedTokenPair":
        self._otp.verify_code(phone, code)

        parent = db.query(models.Parent).filter(models.Parent.phone == phone).first()
        if parent is None:
            raise NotFoundError(code="PHONE_NOT_REGISTERED", message="phone not registered")

        return self._issue_tokens(db, parent)

    def refresh(self, db: Session, *, refresh_token: str) -> "IssuedTokenPair":
        now = int(time.time())
        token_hash = self._tokens.hash_refresh_token(refresh_token)

        sess = (
            db.query(models.AuthSession)
            .filter(models.AuthSession.token_hash == token_hash)
            .first()
        )
        if sess is None or sess.revoked_at is not None:
            raise UnauthorizedError(code="REFRESH_INVALID", message="invalid refresh token")
        if now > int(sess.expires_at):
            raise UnauthorizedError(code="REFRESH_EXPIRED", message="refresh token expired")

        parent = db.get(models.Parent, sess.parent_id)
        if parent is None:
            raise UnauthorizedError(code="REFRESH_INVALID", message="invalid refresh token")

        sess.revoked_at = now
        sess.last_seen_at = now
        db.add(sess)

        pair = self._issue_tokens(db, parent)
        db.commit()
        return pair

    def logout(self, db: Session, *, refresh_token: str) -> None:
        now = int(time.time())
        token_hash = self._tokens.hash_refresh_token(refresh_token)
        sess = (
            db.query(models.AuthSession)
            .filter(models.AuthSession.token_hash == token_hash)
            .first()
        )
        if sess is None:
            return
        sess.revoked_at = now
        sess.last_seen_at = now
        db.add(sess)
        db.commit()

    def _issue_tokens(self, db: Session, parent: models.Parent) -> "IssuedTokenPair":
        now = int(time.time())
        pair = self._tokens.make_access_token(parent_id=parent.id, phone=parent.phone)

        token_hash = self._tokens.hash_refresh_token(pair.refresh_token)
        expires_at = self._tokens.refresh_expire_at()
        sess = models.AuthSession(
            parent_id=parent.id,
            token_hash=token_hash,
            created_at=now,
            expires_at=expires_at,
            revoked_at=None,
            last_seen_at=now,
        )
        db.add(sess)
        db.commit()
        return IssuedTokenPair(
            parent_id=parent.id,
            phone=parent.phone,
            access_token=pair.access_token,
            refresh_token=pair.refresh_token,
            expires_in=pair.expires_in,
            refresh_expires_in=max(expires_at - now, 0),
        )


@dataclass
class IssuedTokenPair:
    parent_id: int
    phone: str
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_expires_in: int
