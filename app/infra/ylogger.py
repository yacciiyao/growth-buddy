# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

import logging


"""统一日志出口

日志初始化由 app.common.logging.setup_logging() 负责。
这里仅返回一个命名 logger，避免重复添加 handler。
"""


ylogger = logging.getLogger("yoo")
