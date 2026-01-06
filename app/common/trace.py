# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import uuid
from contextvars import ContextVar


_trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="-")


def new_trace_id() -> str:
    return uuid.uuid4().hex


def set_trace_id(trace_id: str) -> None:
    _trace_id_ctx.set(trace_id or "-")


def get_trace_id() -> str:
    return _trace_id_ctx.get() or "-"
