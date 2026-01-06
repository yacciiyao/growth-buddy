# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Set


@dataclass
class SafetyViolation(Exception):
    """
    文本安全检查不通过时抛出的异常

    type: "input"  表示儿童输入不合规
          "output" 表示模型回复不合规
    reason: 具体原因描述（日志监控）
    """

    type: str
    reason: str

    def __str__(self) -> str:  # pragma: no cover - 简单拼接
        return f"[{self.type}] {self.reason}"


# 基础敏感词
_BASE_CHILD_INPUT_FORBIDDEN: Set[str] = {
    "暴力",
    "打人",
    "杀人",
    "自杀",
    "自残",
    "恐怖",
    "鬼怪",
    "黄色",
    "色情",
    "毒品",
}

_BASE_MODEL_REPLY_FORBIDDEN: Set[str] = {
    "自杀",
    "自残",
    "杀死",
    "仇恨",
    "色情",
    "暴力",
    "伤害",
}


def _normalize(text: str) -> str:
    return text.strip()


def _merge_forbidden(base: Set[str], extra: Optional[Iterable[str]]) -> Set[str]:
    """
    合并基础敏感词 + 家长自定义禁止话题
    extra 可以为 None
    """
    if not extra:
        return base
    merged = set(base)
    for w in extra:
        w = (w or "").strip()
        if w:
            merged.add(w)
    return merged


def _find_forbidden(text: str, words: Iterable[str]) -> List[str]:
    hits: List[str] = []
    for w in words:
        if w and w in text:
            hits.append(w)
    return hits


def check_child_input(
    text: str,
    *,
    extra_forbidden_topics: Optional[Iterable[str]] = None,
    max_length: int = 200,
) -> None:
    """
    儿童输入文本安全检查

    - 空字符串：直接通过（由上层决定是否提示“再说一遍”）
    - 长度过长：抛 SafetyViolation(type="input", ...)
    - 命中基础敏感词 或 家长配置的禁止话题：抛 SafetyViolation(type="input", ...)
    """
    normalized = _normalize(text)
    if not normalized:
        return

    if len(normalized) > max_length:
        raise SafetyViolation(
            type="input",
            reason=f"儿童输入过长（len={len(normalized)}，限制={max_length}）",
        )

    forbidden_set = _merge_forbidden(_BASE_CHILD_INPUT_FORBIDDEN, extra_forbidden_topics)
    hits = _find_forbidden(normalized, forbidden_set)
    if hits:
        raise SafetyViolation(
            type="input",
            reason=f"儿童输入包含不适宜内容: {','.join(hits)}",
        )


def check_reply_output(
    text: str,
    *,
    extra_forbidden_topics: Optional[Iterable[str]] = None,
    max_length: int = 400,
) -> None:
    """
    模型回复文本安全检查

    - 空字符串：视为异常（抛 SafetyViolation(type="output"...）方便上层走兜底话术）
    - 长度过长：抛 SafetyViolation(type="output"...）
    - 命中基础敏感词或家长禁止话题：抛 SafetyViolation(type="output"...)
    """
    normalized = _normalize(text)

    if not normalized:
        raise SafetyViolation(
            type="output",
            reason="模型回复为空",
        )

    if len(normalized) > max_length:
        raise SafetyViolation(
            type="output",
            reason=f"模型回复过长（len={len(normalized)}，限制={max_length}）",
        )

    forbidden_set = _merge_forbidden(_BASE_MODEL_REPLY_FORBIDDEN, extra_forbidden_topics)
    hits = _find_forbidden(normalized, forbidden_set)
    if hits:
        raise SafetyViolation(
            type="output",
            reason=f"模型回复包含不适宜内容: {','.join(hits)}",
        )
