# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict

from app.common.errors import BadRequestError, TooManyRequestsError, UnauthorizedError
from app.infra.config import settings
from app.infra.ylogger import ylogger


@dataclass
class OtpRecord:
    phone: str
    code: str
    expires_at: int
    last_sent_at: int
    fail_count: int = 0
    locked_until: int = 0


class OtpService:
    """ 短信验证码(测试用) 生产环境建议 Redis """

    def __init__(self) -> None:
        self._store: Dict[str, OtpRecord] = {}

    def send_code(self, phone: str, scene: str = "login") -> int:
        now = int(time.time())
        ttl = int(settings.OTP_TTL_SECONDS)

        rec = self._store.get(phone)
        if rec is not None:
            # 锁定期内直接拒绝
            if rec.locked_until and now < rec.locked_until:
                raise TooManyRequestsError(
                    code="OTP_LOCKED",
                    message="too many failed attempts",
                    detail={"retry_after": rec.locked_until - now},
                )

            # 发送频控
            if now - rec.last_sent_at < int(settings.OTP_SEND_INTERVAL_SECONDS):
                raise TooManyRequestsError(
                    code="OTP_TOO_FREQUENT",
                    message="otp send too frequent",
                    detail={"retry_after": int(settings.OTP_SEND_INTERVAL_SECONDS) - (now - rec.last_sent_at)},
                )

        code = str(settings.SMS_FIXED_CODE)
        expires_at = now + ttl
        self._store[phone] = OtpRecord(
            phone=phone,
            code=code,
            expires_at=expires_at,
            last_sent_at=now,
            fail_count=0,
            locked_until=0,
        )

        # 不真正触发
        ylogger.info("[SMS] send otp: phone=%s scene=%s code=%s ttl=%ss", phone, scene, code, ttl)
        return ttl

    def verify_code(self, phone: str, code: str) -> None:
        now = int(time.time())
        rec = self._store.get(phone)
        if rec is None:
            raise BadRequestError(code="OTP_NOT_SENT", message="otp not sent")

        if rec.locked_until and now < rec.locked_until:
            raise TooManyRequestsError(
                code="OTP_LOCKED",
                message="too many failed attempts",
                detail={"retry_after": rec.locked_until - now},
            )

        if now > rec.expires_at:
            raise UnauthorizedError(code="OTP_EXPIRED", message="otp expired")

        if str(code) != str(rec.code):
            rec.fail_count += 1

            if rec.fail_count >= int(settings.OTP_MAX_VERIFY_FAILS):
                rec.locked_until = now + 300
            self._store[phone] = rec
            raise UnauthorizedError(
                code="OTP_INVALID",
                message="invalid otp",
                detail={"remain": max(int(settings.OTP_MAX_VERIFY_FAILS) - rec.fail_count, 0)},
            )

        # 验证成功, 清理 record，避免复用
        self._store.pop(phone, None)
