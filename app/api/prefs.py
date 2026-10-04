# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""应用设置 API。"""
import json
import os
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import DB_PATH, get_db
from ..paths import CONFIG_PATH, DATA_DIR, EXE_DIR

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
def _read_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


@router.get("/data-dir")
def get_data_dir():
    cfg = _read_config()
    return {
        "current": str(DATA_DIR),
        "default": str(EXE_DIR / "data"),
        "custom": cfg.get("data_dir") or None,
        "env_override": bool(os.environ.get("MOYU_DATA_DIR")),
        "db_path": str(DB_PATH),
    }


class DataDirBody(BaseModel):
    path: str
    migrate: bool = False


@router.post("/data-dir")
def set_data_dir(body: DataDirBody):
    if os.environ.get("MOYU_DATA_DIR"):
        raise HTTPException(400, "当前数据目录由环境变量 MOYU_DATA_DIR 指定，自定义路径不会生效，请先移除该环境变量")
    raw = (body.path or "").strip()
    if not raw:
        raise HTTPException(400, "路径不能为空")
    target = Path(raw).expanduser()
    if not target.is_absolute():
        raise HTTPException(400, "请输入绝对路径，例如 D:\\moyu-data")
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise HTTPException(400, f"无法创建目录：{e}")
    migrated, skipped = [], []
    if body.migrate and target.resolve() != DATA_DIR.resolve():
        for src in [DB_PATH, DATA_DIR / "exports", DATA_DIR / "imports"]:
            if not src.exists():
                continue
            dst = target / src.name
            if dst.exists():
                skipped.append(src.name)
                continue
            try:
                if src.is_dir():
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
                migrated.append(src.name)
            except OSError as e:
                raise HTTPException(500, f"迁移 {src.name} 失败：{e}")
    cfg = _read_config()
    cfg["data_dir"] = str(target)
    try:
        _write_config(cfg)
    except OSError as e:
        raise HTTPException(500, f"写入配置失败：{e}")
    return {"ok": True, "data_dir": str(target), "migrated": migrated, "skipped": skipped, "need_restart": True}


@router.delete("/data-dir")
def reset_data_dir():
    cfg = _read_config()
    cfg.pop("data_dir", None)
    try:
        if cfg:
            _write_config(cfg)
        elif CONFIG_PATH.exists():
            CONFIG_PATH.unlink()
    except OSError as e:
        raise HTTPException(500, f"更新配置失败：{e}")
    return {"ok": True, "data_dir": str(EXE_DIR / "data"), "need_restart": True}
