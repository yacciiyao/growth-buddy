# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class AppError(Exception):
    """异常统一"""
    code: str
    message: str
    status_code: int = 400
    detail: Optional[Any] = None


class BadRequestError(AppError):
    def __init__(self, code: str = "BAD_REQUEST", message: str = "bad request", detail: Any = None) -> None:
        super().__init__(code=code, message=message, status_code=400, detail=detail)


class NotFoundError(AppError):
    def __init__(self, code: str = "NOT_FOUND", message: str = "not found", detail: Any = None) -> None:
        super().__init__(code=code, message=message, status_code=404, detail=detail)


class UnauthorizedError(AppError):
    def __init__(self, code: str = "UNAUTHORIZED", message: str = "unauthorized", detail: Any = None) -> None:
        super().__init__(code=code, message=message, status_code=401, detail=detail)


class ForbiddenError(AppError):
    def __init__(self, code: str = "FORBIDDEN", message: str = "forbidden", detail: Any = None) -> None:
        super().__init__(code=code, message=message, status_code=403, detail=detail)


class TooManyRequestsError(AppError):
    def __init__(self, code: str = "TOO_MANY_REQUESTS", message: str = "too many requests", detail: Any = None) -> None:
        super().__init__(code=code, message=message, status_code=429, detail=detail)
