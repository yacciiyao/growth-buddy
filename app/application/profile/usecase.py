# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from app.common.errors import BadRequestError, ForbiddenError, NotFoundError
from app.domain import models, schemas


def _join_list(items: List[str]) -> str:
    """把字符串列表压成逗号分隔字符串存库"""
    cleaned = [x.strip() for x in items if x and x.strip()]
    return ",".join(cleaned)


def _split_str(s: str | None) -> List[str]:
    """把逗号分隔字符串拆回列表，用于接口返回"""
    if not s:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]


class ProfileUsecase:
    """家长档案域（家长-孩子-设备）"""

    def setup_parent_child_device(
        self,
        db: Session,
        *,
        parent: models.Parent,
        req: schemas.ParentSetupRequest,
    ) -> schemas.ParentSetupResponse:
        # 1) 创建 child
        child = models.Child(
            parent_id=parent.id,
            name=req.child_name,
            age=req.child_age,
            gender=req.child_gender,
            interests=_join_list(req.child_interests),
            forbidden_topics=_join_list(req.child_forbidden_topics),
        )
        db.add(child)
        db.flush()

        # 2) 设备绑定（限制：若设备已绑定到其他家长的孩子，则拒绝）
        device = (
            db.query(models.Device)
            .filter(models.Device.device_sn == req.device_sn)
            .first()
        )
        if device is None:
            device = models.Device(
                device_sn=req.device_sn,
                bound_child_id=child.id,
                toy_name=req.toy_name or "小悠",
                toy_age=req.toy_age or "8",
                toy_gender=req.toy_gender or "girl",
                toy_persona=(
                    req.toy_persona
                    or "一个叫小悠的温柔可爱小伙伴，会认真听小朋友说话，轻声细语，喜欢鼓励和安慰小朋友。"
                ),
            )
            db.add(device)
        else:
            if device.bound_child_id is not None:
                bound_child = db.get(models.Child, device.bound_child_id)
                if bound_child is not None and bound_child.parent_id != parent.id:
                    raise ForbiddenError(
                        code="DEVICE_OWNED_BY_OTHER",
                        message="device already bound to another parent",
                    )
            device.bound_child_id = child.id
            if req.toy_name is not None:
                device.toy_name = req.toy_name
            if req.toy_age is not None:
                device.toy_age = req.toy_age
            if req.toy_gender is not None:
                device.toy_gender = req.toy_gender
            if req.toy_persona is not None:
                device.toy_persona = req.toy_persona

        db.commit()
        db.refresh(child)
        db.refresh(device)

        return schemas.ParentSetupResponse(parent_id=parent.id, child_id=child.id, device_id=device.id)

    def get_child_profile(self, db: Session, *, parent: models.Parent, child_id: int) -> schemas.ChildProfile:
        child = db.get(models.Child, child_id)
        if child is None:
            raise NotFoundError(code="CHILD_NOT_FOUND", message="child not found")
        if child.parent_id != parent.id:
            raise ForbiddenError(code="CHILD_FORBIDDEN", message="child not belongs to current parent")

        device = (
            db.query(models.Device)
            .filter(models.Device.bound_child_id == child.id)
            .first()
        )
        if device is None:
            raise NotFoundError(code="DEVICE_NOT_FOUND", message="device not found for child")

        return schemas.ChildProfile(
            parent_id=parent.id,
            parent_phone=parent.phone,
            parent_email=parent.email,
            child_id=child.id,
            child_name=child.name,
            child_age=child.age,
            child_gender=child.gender or "",
            child_interests=_split_str(child.interests),
            child_forbidden_topics=_split_str(child.forbidden_topics),
            device_id=device.id,
            device_sn=device.device_sn,
            toy_name=device.toy_name or "小悠",
            toy_age=device.toy_age,
            toy_gender=device.toy_gender,
            toy_persona=device.toy_persona,
        )

    def update_child_profile(
        self,
        db: Session,
        *,
        parent: models.Parent,
        child_id: int,
        req: schemas.ChildProfileUpdateRequest,
    ) -> schemas.ChildProfile:
        child = db.get(models.Child, child_id)
        if child is None:
            raise NotFoundError(code="CHILD_NOT_FOUND", message="child not found")
        if child.parent_id != parent.id:
            raise ForbiddenError(code="CHILD_FORBIDDEN", message="child not belongs to current parent")

        device = (
            db.query(models.Device)
            .filter(models.Device.bound_child_id == child.id)
            .first()
        )

        if req.child_name is not None:
            child.name = req.child_name
        if req.child_age is not None:
            child.age = req.child_age
        if req.child_gender is not None:
            child.gender = req.child_gender
        if req.child_interests is not None:
            child.interests = _join_list(req.child_interests)
        if req.child_forbidden_topics is not None:
            child.forbidden_topics = _join_list(req.child_forbidden_topics)

        if device is not None:
            if req.toy_name is not None:
                device.toy_name = req.toy_name
            if req.toy_age is not None:
                device.toy_age = req.toy_age
            if req.toy_gender is not None:
                device.toy_gender = req.toy_gender
            if req.toy_persona is not None:
                device.toy_persona = req.toy_persona

        db.commit()

        if device is None:
            raise BadRequestError(code="DEVICE_NOT_BOUND", message="device not bound to child")

        return self.get_child_profile(db, parent=parent, child_id=child_id)
