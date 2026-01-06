# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from openai import OpenAI

from app.infra.config import settings
from app.llm.base import ChatMessage, LlmProvider


class DeepSeekProvider(LlmProvider):
    """基于 DeepSeek OpenAI-兼容接口的实现"""

    name = "deepseek"

    def __init__(self) -> None:
        if not settings.DEEPSEEK_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY 未配置，无法使用 DeepSeekProvider")

        base_url = settings.DEEPSEEK_BASE_URL or "https://api.deepseek.com"
        self._client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=base_url,
        )

    def _chat_sync(
        self,
        messages: List[ChatMessage],
        model: str,
        max_tokens: int,
        temperature: float,
        extra_params: Optional[Dict[str, Any]],
    ) -> str:
        params: Dict[str, Any] = {
            "model": model,
            "messages": list(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if extra_params:
            params.update(extra_params)

        resp = self._client.chat.completions.create(**params)
        content = resp.choices[0].message.content
        return (content or "").strip()

    async def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        *,
        max_tokens: int = 256,
        temperature: float = 0.8,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> str:
        return await asyncio.to_thread(
            self._chat_sync,
            messages,
            model,
            max_tokens,
            temperature,
            extra_params,
        )
