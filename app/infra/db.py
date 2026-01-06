# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.infra.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy ORM 基类"""


engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    future=True,
    echo=False,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    future=True,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：yield 一个 Session，请求结束自动关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session() -> Session:
    """脚本/工具使用：手动获取一个 Session"""
    return SessionLocal()
