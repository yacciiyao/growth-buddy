# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ParentSetupRequest(BaseModel):
    child_name: str = Field(..., description="儿童姓名或昵称")
    child_age: int = Field(..., ge=0, le=18, description="儿童年龄")
    child_gender: str = Field(..., description="儿童性别：boy / girl / other")

    child_interests: List[str] = Field(
        default_factory=list,
        description="儿童兴趣列表，例如 ['恐龙','画画']",
    )
    child_forbidden_topics: List[str] = Field(
        default_factory=list,
        description="禁止谈论的话题，例如 ['暴力','恐怖']",
    )

    device_sn: str = Field(..., description="玩具设备唯一序列号")

    toy_name: Optional[str] = Field(
        None,
        description="玩具名称（默认小悠）",
    )
    toy_age: Optional[str] = Field(
        None,
        description="玩具虚拟年龄（默认 8）",
    )
    toy_gender: Optional[str] = Field(
        None,
        description="玩具虚拟性别，如 girl / boy / other / unknown",
    )
    toy_persona: Optional[str] = Field(
        None,
        description="玩具人设文案，例如“温柔可爱的小伙伴，小悠...”",
    )


class ParentSetupResponse(BaseModel):
    parent_id: int
    child_id: int
    device_id: int


class ChildProfile(BaseModel):
    parent_id: int
    parent_phone: str
    parent_email: Optional[str] = None

    child_id: int
    child_name: str
    child_age: int
    child_gender: str
    child_interests: List[str]
    child_forbidden_topics: List[str]

    device_id: int
    device_sn: str
    toy_name: str
    toy_age: Optional[str]
    toy_gender: Optional[str]
    toy_persona: Optional[str]


class ChildProfileUpdateRequest(BaseModel):
    # 儿童信息
    child_name: Optional[str] = None
    child_age: Optional[int] = Field(None, ge=0, le=12)
    child_gender: Optional[str] = None
    child_interests: Optional[List[str]] = None
    child_forbidden_topics: Optional[List[str]] = None

    # 玩具人设
    toy_name: Optional[str] = None
    toy_age: Optional[str] = None
    toy_gender: Optional[str] = None
    toy_persona: Optional[str] = None


class SessionSummary(BaseModel):
    session_id: int
    title: Optional[str] = None
    started_at: int
    ended_at: Optional[int] = None
    turn_count: int
    has_risk: bool = Field(
        False,
        description="该会话是否包含风险轮次（任意一轮 risk_flag=True）",
    )


class SessionTurn(BaseModel):
    turn_id: int
    seq: int
    created_at: int
    user_text: str
    reply_text: str
    user_audio_url: Optional[str]
    reply_audio_url: Optional[str]
    risk_flag: int
    risk_source: Optional[str] = None
    risk_reason: Optional[str] = None


class SessionDetail(BaseModel):
    session_id: int
    child_id: int
    device_sn: str
    start_time: Optional[int]
    end_time: Optional[int]
    turns: List[SessionTurn]


class ChildSessionsResponse(BaseModel):
    child_id: int
    sessions: List[SessionSummary]


class TurnDetail(BaseModel):
    turn_id: int
    seq: int
    user_text: Optional[str]
    reply_text: Optional[str]
    user_audio_url: Optional[str]
    reply_audio_url: Optional[str]
    created_at: int

    risk_flag: bool = Field(
        False,
        description="该轮是否存在风险（通常是儿童输入触发安全规则）",
    )
    risk_source: Optional[str] = Field(
        None,
        description="风险来源：input / output / both",
    )
    risk_reason: Optional[str] = Field(
        None,
        description="风险原因简要说明，用于家长端提示",
    )


class SessionTurnsResponse(BaseModel):
    session_id: int
    child_id: int
    device_sn: str
    turns: List[TurnDetail]


# Auth


class SendCodeRequest(BaseModel):
    phone: str = Field(..., pattern=r"^1\d{10}$", description="手机号（中国大陆 11 位）")
    scene: str = Field("login", description="场景：login / register")


class SendCodeResponse(BaseModel):
    sent: bool = True
    ttl: int = Field(..., description="验证码有效期（秒）")


class PhoneCodeRequest(BaseModel):
    phone: str = Field(..., pattern=r"^1\d{10}$", description="手机号")
    code: str = Field(..., min_length=4, max_length=10, description="短信验证码")


class TokenPairResponse(BaseModel):
    token_type: str = "bearer"
    access_token: str
    refresh_token: str
    expires_in: int = Field(..., description="access_token 剩余有效期（秒）")
    refresh_expires_in: int = Field(..., description="refresh_token 剩余有效期（秒）")
    parent_id: int
    phone: str


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="refresh_token")


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., description="refresh_token")
