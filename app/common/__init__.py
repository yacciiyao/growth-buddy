# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

"""通用基础设施（错误/日志/trace 等）

约定：
- Router 不写业务逻辑：业务错误统一通过 AppError 抛出，由全局异常处理转为标准响应
- trace_id 通过 middleware 注入，并写入日志，便于线上排障
"""

from __future__ import annotations
