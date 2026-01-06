# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from typing import Any, Dict, Tuple

from app.domain.models import Child
from app.infra.config import settings
from app.llm.base import LlmProvider
from app.llm.registry import LlmProviderRegistry


class LlmModelSelector:
    """根据 child + 场景，从注册表里选择 provider + model + 生成参数"""

    def __init__(self, registry: LlmProviderRegistry) -> None:
        self._registry = registry

    def _choose_provider_name(self) -> str:
        default_name = (settings.LLM_DEFAULT_PROVIDER or "").strip().lower() or "dummy"
        available = set(self._registry.available_providers())

        if default_name in available:
            return default_name
        if "dummy" in available:
            return "dummy"
        if available:
            return sorted(available)[0]
        raise RuntimeError("没有可用的大模型 provider")

    def _default_model_for_provider(self, provider_name: str) -> str:
        if provider_name == "deepseek":
            return settings.DEEPSEEK_MODEL
        if provider_name == "openai":
            return settings.OPENAI_MODEL
        if provider_name == "ollama":
            return settings.OLLAMA_MODEL
        if provider_name == "dummy":
            return "dummy"
        return "default"

    def _default_gen_config(self, task: str) -> Dict[str, Any]:
        # 语音对话通常更短、更快；如需区分可基于 task 调整
        if task == "voice":
            return {"temperature": 0.7, "max_tokens": 256}
        return {"temperature": 0.8, "max_tokens": 256}

    def select_for_child(self, child: Child, task: str = "chat") -> Tuple[LlmProvider, str, Dict[str, Any]]:
        """返回 (provider, model_name, gen_cfg)"""
        provider_name = self._choose_provider_name()
        provider = self._registry.get(provider_name)
        model_name = self._default_model_for_provider(provider_name)
        gen_cfg = self._default_gen_config(task)
        return provider, model_name, gen_cfg
