# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_auth_usecase, get_db
from app.application.auth.usecase import AuthUsecase
from app.domain import schemas


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/send_code", response_model=schemas.SendCodeResponse)
def send_code(
    req: schemas.SendCodeRequest,
    uc: AuthUsecase = Depends(get_auth_usecase),
):
    ttl = uc.send_code(req.phone, scene=req.scene)
    return schemas.SendCodeResponse(ttl=ttl)


@router.post("/register", response_model=schemas.TokenPairResponse)
def register(
    req: schemas.PhoneCodeRequest,
    db: Session = Depends(get_db),
    uc: AuthUsecase = Depends(get_auth_usecase),
):
    issued = uc.register(db, phone=req.phone, code=req.code)
    return schemas.TokenPairResponse(
        access_token=issued.access_token,
        refresh_token=issued.refresh_token,
        expires_in=issued.expires_in,
        refresh_expires_in=issued.refresh_expires_in,
        parent_id=issued.parent_id,
        phone=issued.phone,
    )


@router.post("/login", response_model=schemas.TokenPairResponse)
def login(
    req: schemas.PhoneCodeRequest,
    db: Session = Depends(get_db),
    uc: AuthUsecase = Depends(get_auth_usecase),
):
    issued = uc.login(db, phone=req.phone, code=req.code)
    return schemas.TokenPairResponse(
        access_token=issued.access_token,
        refresh_token=issued.refresh_token,
        expires_in=issued.expires_in,
        refresh_expires_in=issued.refresh_expires_in,
        parent_id=issued.parent_id,
        phone=issued.phone,
    )


@router.post("/refresh", response_model=schemas.TokenPairResponse)
def refresh(
    req: schemas.RefreshRequest,
    db: Session = Depends(get_db),
    uc: AuthUsecase = Depends(get_auth_usecase),
):
    issued = uc.refresh(db, refresh_token=req.refresh_token)
    return schemas.TokenPairResponse(
        access_token=issued.access_token,
        refresh_token=issued.refresh_token,
        expires_in=issued.expires_in,
        refresh_expires_in=issued.refresh_expires_in,
        parent_id=issued.parent_id,
        phone=issued.phone,
    )


@router.post("/logout")
def logout(
    req: schemas.LogoutRequest,
    db: Session = Depends(get_db),
    uc: AuthUsecase = Depends(get_auth_usecase),
):
    uc.logout(db, refresh_token=req.refresh_token)
    return {"ok": True}
