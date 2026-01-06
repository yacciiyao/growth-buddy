# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

"""语音模块错误类型

作为一层轻量兼容封装，便于上层统一引用 `SpeechError` / `AudioFormatError`，
避免直接依赖某个具体供应商实现
"""

from __future__ import annotations

from app.speech.asr_xfyun import AudioFormatError, SpeechError

__all__ = ["SpeechError", "AudioFormatError"]
