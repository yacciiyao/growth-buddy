# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

"""S3 存储（AWS / MinIO）

注意：
- 为了让项目在 "只配置数据库" 的情况下也能跑起来，这里做了延迟初始化。
- 如果未配置 S3 相关参数，调用 upload/build_url 时会抛出明确错误。
"""

import os
from typing import Optional

import boto3
from botocore.client import Config

from app.common.errors import BadRequestError
from app.infra.config import settings
from app.infra.ylogger import ylogger


_s3_client: Optional[object] = None


def _use_s3() -> bool:
    return bool(
        settings.AWS_ACCESS_KEY_ID
        and settings.AWS_SECRET_ACCESS_KEY
        and settings.AWS_S3_BUCKET
        and settings.AWS_S3_BASE_URL
    )


def _get_s3():
    global _s3_client
    if _s3_client is not None:
        return _s3_client

    if not _use_s3():
        raise BadRequestError(
            code="S3_NOT_CONFIGURED",
            message="S3 storage not configured",
            detail="please set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY/AWS_S3_BUCKET/AWS_S3_BASE_URL",
        )

    _session = boto3.session.Session(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION or None,
    )
    _s3_client = _session.client(
        "s3",
        endpoint_url=settings.AWS_S3_ENDPOINT_URL or None,
        config=Config(s3={"addressing_style": "virtual"}),
    )
    return _s3_client


def upload_bytes(key: str, data: bytes, content_type: str = "audio/wav") -> None:
    key = key.lstrip("/")

    if _use_s3():
        s3 = _get_s3()
        ylogger.info("Upload to S3: bucket=%s, key=%s, size=%s", settings.AWS_S3_BUCKET, key, len(data))
        s3.put_object(
            Bucket=settings.AWS_S3_BUCKET,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return

    # fallback: local file
    base = settings.FILE_BASE_PATH or "./data"
    dst = os.path.join(base, key)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(data)
    ylogger.info("Upload to Local: path=%s size=%s", dst, len(data))


def build_url(key: str) -> str:
    key = key.lstrip("/")
    if _use_s3():
        base = settings.AWS_S3_BASE_URL.rstrip("/")
        return f"{base}/{key}"

    # local file served by FastAPI StaticFiles
    return f"/files/{key}"
