# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_parent, get_db, get_history_usecase
from app.application.history.usecase import HistoryUsecase
from app.domain import models, schemas


router = APIRouter(prefix="/history", tags=["history"])


@router.get("/children/{child_id}/sessions", response_model=schemas.ChildSessionsResponse)
def list_child_sessions(
    child_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
    parent: models.Parent = Depends(get_current_parent),
    uc: HistoryUsecase = Depends(get_history_usecase),
):
    sessions = uc.list_sessions_for_child(db, parent=parent, child_id=child_id, limit=limit)
    return schemas.ChildSessionsResponse(child_id=child_id, sessions=sessions)


@router.get("/sessions/{session_id}", response_model=schemas.SessionDetail)
def get_session_detail(
    session_id: int,
    db: Session = Depends(get_db),
    parent: models.Parent = Depends(get_current_parent),
    uc: HistoryUsecase = Depends(get_history_usecase),
):
    return uc.get_session_detail(db, parent=parent, session_id=session_id)
