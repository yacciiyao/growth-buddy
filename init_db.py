# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from app.infra.db import Base, engine
from app.domain import models  # noqa: F401


def init_db() -> None:
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Done.")


if __name__ == "__main__":
    init_db()
