# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import logging

from app.common.trace import get_trace_id


class TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        setattr(record, "trace_id", get_trace_id())
        return True


def setup_logging(level: int = logging.INFO) -> None:
    """初始化全局日志"""

    root = logging.getLogger()
    root.setLevel(level)

    if not root.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s - %(levelname)s - trace=%(trace_id)s - %(name)s - %(message)s]",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        root.addHandler(handler)

    # 给现有 handler 全部加 filter
    for h in root.handlers:
        has_filter = any(isinstance(f, TraceIdFilter) for f in getattr(h, "filters", []))
        if not has_filter:
            h.addFilter(TraceIdFilter())
