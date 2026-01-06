# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from openai import OpenAI

from app.infra.config import settings
from app.llm.base import ChatMessage, LlmProvider


class OllamaProvider(LlmProvider):
    """本地 Ollama Provider（OpenAI 兼容接口 /v1）"""

    name = "ollama"

    def __init__(self) -> None:
        base_url = settings.OLLAMA_BASE_URL or "http://127.0.0.1:11434/v1"
        # OpenAI SDK 需要 api_key 字段；本地 Ollama 不校验，使用占位值即可
        self._client = OpenAI(api_key="ollama", base_url=base_url)

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
