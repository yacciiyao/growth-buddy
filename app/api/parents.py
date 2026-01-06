# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_parent, get_db, get_profile_usecase
from app.application.profile.usecase import ProfileUsecase
from app.domain import models, schemas


router = APIRouter(prefix="/parents", tags=["parents"])


@router.post("/setup", response_model=schemas.ParentSetupResponse)
def setup_parent_child_device(
    req: schemas.ParentSetupRequest,
    db: Session = Depends(get_db),
    parent: models.Parent = Depends(get_current_parent),
    uc: ProfileUsecase = Depends(get_profile_usecase),
):
    return uc.setup_parent_child_device(db, parent=parent, req=req)


@router.get("/children/{child_id}/profile", response_model=schemas.ChildProfile)
def get_child_profile(
    child_id: int,
    db: Session = Depends(get_db),
    parent: models.Parent = Depends(get_current_parent),
    uc: ProfileUsecase = Depends(get_profile_usecase),
):
    return uc.get_child_profile(db, parent=parent, child_id=child_id)


@router.put("/children/{child_id}/profile", response_model=schemas.ChildProfile)
def update_child_profile(
    child_id: int,
    req: schemas.ChildProfileUpdateRequest,
    db: Session = Depends(get_db),
    parent: models.Parent = Depends(get_current_parent),
    uc: ProfileUsecase = Depends(get_profile_usecase),
):
    return uc.update_child_profile(db, parent=parent, child_id=child_id, req=req)
