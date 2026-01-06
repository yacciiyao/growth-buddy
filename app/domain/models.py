# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import time
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.db import Base


def _ts() -> int:
    return int(time.time())


class Parent(Base):
    __tablename__ = "parents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=_ts)
    updated_at: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        default=None,
        onupdate=_ts,
    )

    children: Mapped[List["Child"]] = relationship(
        "Child",
        back_populates="parent",
        cascade="all, delete-orphan",
    )

    auth_sessions: Mapped[List["AuthSession"]] = relationship(
        "AuthSession",
        back_populates="parent",
        cascade="all, delete-orphan",
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("parents.id"),
        nullable=False,
        index=True,
    )

    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=_ts)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    revoked_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, default=None)
    last_seen_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, default=None)

    ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    parent: Mapped["Parent"] = relationship("Parent", back_populates="auth_sessions")


class Child(Base):
    __tablename__ = "children"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("parents.id"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    interests: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        doc="兴趣列表，逗号分隔存储",
    )
    forbidden_topics: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        doc="禁止话题列表，逗号分隔存储",
    )

    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=_ts)
    updated_at: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        default=None,
        onupdate=_ts,
    )

    parent: Mapped["Parent"] = relationship("Parent", back_populates="children")
    sessions: Mapped[List["ChatSession"]] = relationship(
        "ChatSession",
        back_populates="child",
        cascade="all, delete-orphan",
    )

    device: Mapped[Optional["Device"]] = relationship(
        "Device",
        uselist=False,
        primaryjoin="Child.id==Device.bound_child_id",
        viewonly=True,
    )


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_sn: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    bound_child_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("children.id"),
        nullable=True,
        index=True,
    )

    toy_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    toy_age: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    toy_gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    toy_persona: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=_ts)
    updated_at: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        default=None,
        onupdate=_ts,
    )
    last_seen_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, default=None)

    child: Mapped[Optional["Child"]] = relationship(
        "Child",
        primaryjoin="Device.bound_child_id==Child.id",
        viewonly=True,
    )
    turns: Mapped[List["Turn"]] = relationship("Turn", back_populates="device")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    child_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("children.id"),
        nullable=False,
        index=True,
    )

    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, doc="会话标题")

    started_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=_ts)
    ended_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, default=None)

    child: Mapped["Child"] = relationship("Child", back_populates="sessions")
    turns: Mapped[List["Turn"]] = relationship(
        "Turn",
        back_populates="session",
        order_by="Turn.seq",
        cascade="all, delete-orphan",
    )


class Turn(Base):
    __tablename__ = "turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chat_sessions.id"),
        nullable=False,
        index=True,
    )
    device_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("devices.id"),
        nullable=False,
        index=True,
    )

    seq: Mapped[int] = mapped_column(Integer, nullable=False)

    user_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reply_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user_audio_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    reply_audio_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=_ts)
    updated_at: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        default=None,
        onupdate=_ts,
    )

    playback_status: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        default="completed",
        doc="pending/speaking/interrupted/completed/error",
    )
    resume_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    policy_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    audit_action: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    metrics_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    risk_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    risk_source: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    risk_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="turns")
    device: Mapped["Device"] = relationship("Device", back_populates="turns")
