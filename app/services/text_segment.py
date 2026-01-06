# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

"""TTS 文本分段工具

目标：
- 确定性：同样输入输出同样分段
- 实用性：控制单段长度，降低尾延迟
- 稳健性：避免过度切分影响语音韵律

说明：本模块保持无第三方依赖，便于在设备/服务端复用
"""


from __future__ import annotations

import re
from typing import List


_PUNCT_SPLIT_RE = re.compile(r"([。！？!?\.\n]+)")


def segment_text_for_tts(text: str, *, max_chars: int = 80, min_chars: int = 10) -> List[str]:
    """将长文本切分为更适合 TTS 流式播报的分段"""
    s = (text or "").strip()
    if not s:
        return []

    # 归一化空白字符
    s = re.sub(r"\s+", " ", s)

    parts = []
    buf = []

    tokens = _PUNCT_SPLIT_RE.split(s)
    for t in tokens:
        if not t:
            continue
        if _PUNCT_SPLIT_RE.fullmatch(t):
            # 句读符
            buf.append(t)
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(t)
            # 软切分：过长且缺少句读时先截断
            if sum(len(x) for x in buf) >= max_chars:
                parts.append("".join(buf).strip())
                buf = []

    if buf:
        parts.append("".join(buf).strip())

    # 合并过短分段
    merged: List[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if merged and len(p) < min_chars:
            merged[-1] = (merged[-1] + " " + p).strip()
        else:
            merged.append(p)

    # 硬切分：兜底处理仍然过长的分段
    final: List[str] = []
    for seg in merged:
        if len(seg) <= max_chars:
            final.append(seg)
        else:
            # 硬切分
            for i in range(0, len(seg), max_chars):
                chunk = seg[i : i + max_chars].strip()
                if chunk:
                    final.append(chunk)

    return final
