# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.common.trace import new_trace_id, set_trace_id


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        trace_id = request.headers.get("X-Request-Id") or new_trace_id()
        set_trace_id(trace_id)
        response: Response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response
