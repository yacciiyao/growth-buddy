# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.llm.base import ChatMessage, LlmProvider


class DummyProvider(LlmProvider):
    """本地调试用，不依赖任何外部服务"""

    name = "dummy"

    async def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        *,
        max_tokens: int = 256,
        temperature: float = 0.8,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> str:
        last_user: str = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user = msg.get("content", "")
                break

        if not last_user:
            return "小悠在这里，随时可以听你说话"

        return f"小悠听到了，你刚才说的是「{last_user}」。小悠觉得你很认真，也很愿意继续听你分享。"
