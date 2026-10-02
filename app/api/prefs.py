# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""应用设置 API。"""
from fastapi import APIRouter
from pydantic import BaseModel

from ..db import get_db

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_settings():
    rows = get_db().execute("SELECT key, value FROM app_settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


class SettingsPatch(BaseModel):
    values: dict[str, str]


@router.patch("")
def patch_settings(body: SettingsPatch):
    db = get_db()
    for k, v in body.values.items():
        db.execute(
            "INSERT INTO app_settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (k, str(v)),
        )
    db.commit()
    return get_settings()
