# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from openai import OpenAI

from app.infra.config import settings
from app.llm.base import ChatMessage, LlmProvider


class OpenAIProvider(LlmProvider):
    name = "openai"

    def __init__(self) -> None:
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY 未配置，无法使用 OpenAIProvider")

        kwargs: Dict[str, Any] = {"api_key": settings.OPENAI_API_KEY}
        if settings.OPENAI_BASE_URL:
            kwargs["base_url"] = settings.OPENAI_BASE_URL
        self._client = OpenAI(**kwargs)

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
