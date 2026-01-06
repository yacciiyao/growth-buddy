# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from typing import Dict, Tuple

from app.infra.config import settings
from app.llm.base import LlmProvider
from app.llm.deepseek_provider import DeepSeekProvider
from app.llm.dummy_provider import DummyProvider
from app.llm.ollama_provider import OllamaProvider
from app.llm.openai_provider import OpenAIProvider


class LlmProviderRegistry:
    def __init__(self, providers: Dict[str, LlmProvider]) -> None:
        self._providers = providers

    def get(self, name: str) -> LlmProvider:
        if name not in self._providers:
            raise KeyError(f"未注册的 LLM provider: {name}")
        return self._providers[name]

    def available_providers(self) -> Tuple[str, ...]:
        return tuple(self._providers.keys())


def build_default_registry() -> LlmProviderRegistry:
    providers: Dict[str, LlmProvider] = {"dummy": DummyProvider()}

    if settings.DEEPSEEK_API_KEY:
        providers["deepseek"] = DeepSeekProvider()

    if settings.OPENAI_API_KEY:
        providers["openai"] = OpenAIProvider()

    # 本地 Ollama 可选：不依赖 key，默认指向 http://127.0.0.1:11434/v1
    providers["ollama"] = OllamaProvider()

    return LlmProviderRegistry(providers)
