# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.errors import ForbiddenError, NotFoundError
from app.domain import models, schemas
from app.infra import storage_s3


class HistoryUsecase:
    def list_sessions_for_child(
        self,
        db: Session,
        *,
        parent: models.Parent,
        child_id: int,
        limit: int = 20,
    ) -> List[schemas.SessionSummary]:
        child = db.get(models.Child, child_id)
        if child is None:
            raise NotFoundError(code="CHILD_NOT_FOUND", message="child not found")
        if child.parent_id != parent.id:
            raise ForbiddenError(code="CHILD_FORBIDDEN", message="child not belongs to current parent")

        stmt = (
            select(models.ChatSession)
            .where(models.ChatSession.child_id == child_id)
            .order_by(models.ChatSession.id.desc())
            .limit(limit)
        )
        sessions = list(db.scalars(stmt).all())
        items: List[schemas.SessionSummary] = []
        for s in sessions:
            turns = list(getattr(s, "turns", []) or [])
            items.append(
                schemas.SessionSummary(
                    session_id=s.id,
                    title=s.title,
                    started_at=s.started_at,
                    ended_at=s.ended_at,
                    turn_count=len(turns),
                    has_risk=any(bool(getattr(t, "risk_flag", False)) for t in turns),
                )
            )
        return items

    def get_session_detail(
        self,
        db: Session,
        *,
        parent: models.Parent,
        session_id: int,
    ) -> schemas.SessionDetail:
        session = db.get(models.ChatSession, session_id)
        if session is None:
            raise NotFoundError(code="SESSION_NOT_FOUND", message="session not found")

        child = db.get(models.Child, session.child_id)
        if child is None:
            raise NotFoundError(code="CHILD_NOT_FOUND", message="child not found")
        if child.parent_id != parent.id:
            raise ForbiddenError(code="SESSION_FORBIDDEN", message="session not belongs to current parent")

        turn_stmt = (
            select(models.Turn)
            .where(models.Turn.session_id == session_id)
            .order_by(models.Turn.seq.asc())
        )
        turns = list(db.scalars(turn_stmt).all())

        device_sn = ""
        if turns:
            try:
                device_sn = turns[0].device.device_sn
            except Exception:  # noqa: BLE001
                device_sn = ""

        items: List[schemas.SessionTurn] = []
        for t in turns:
            user_audio_url = storage_s3.build_url(t.user_audio_path) if t.user_audio_path else None
            reply_audio_url = storage_s3.build_url(t.reply_audio_path) if t.reply_audio_path else None
            items.append(
                schemas.SessionTurn(
                    turn_id=t.id,
                    seq=t.seq,
                    created_at=t.created_at,
                    user_text=t.user_text or "",
                    reply_text=t.reply_text or "",
                    user_audio_url=user_audio_url,
                    reply_audio_url=reply_audio_url,
                    risk_flag=int(bool(getattr(t, "risk_flag", False))),
                    risk_source=getattr(t, "risk_source", None),
                    risk_reason=getattr(t, "risk_reason", None),
                )
            )

        return schemas.SessionDetail(
            session_id=session.id,
            child_id=session.child_id,
            device_sn=device_sn,
            start_time=session.started_at,
            end_time=session.ended_at,
            turns=items,
        )
