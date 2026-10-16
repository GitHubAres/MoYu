# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""商业网文主角状态与金手指看板 API：提供主角数值、外挂进度、核心悬念跟踪与上下文装配。"""
import json
from typing import Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_db

router = APIRouter(tags=["protagonist"])


class ProtagonistStateIn(BaseModel):
    entity_id: Optional[int] = None
    name: str
    cultivation_level: str = ""       # 修为境界 / 等级（如：筑基中期、三级序列）
    cheat_name: str = ""              # 金手指/外挂名称（如：镇魔熔炉、熟练度面板）
    cheat_progress: str = ""          # 外挂进度/数值（如：魔纹点亮 3/9、吞噬道果熟练度 85%）
    current_resources: str = ""       # 当前资源/寿元/战力数值（如：剩余寿元 34年、精血储备 120卡）
    core_goals: str = ""              # 当前阶段核心目标与卡点（如：暗中诛杀赵老三、压制心魔反噬）
    key_items: list[str] = []         # 随身关键法宝/道具
    notes: str = ""                   # 补充备忘


def _get_protagonist_entity(db, work_id: int, entity_id: Optional[int] = None):
    """查找作品主角实体。"""
    if entity_id:
        row = db.execute(
            "SELECT * FROM entities WHERE id = ? AND work_id = ?",
            (entity_id, work_id)
        ).fetchone()
        if row:
            return dict(row)

    # 优先根据 tags 或 fields 查找标记为主角的角色
    rows = db.execute(
        "SELECT * FROM entities WHERE work_id = ? AND category = 'character' AND archived = 0 ORDER BY id ASC",
        (work_id,)
    ).fetchall()

    for r in rows:
        r_dict = dict(r)
        tags = r_dict.get("tags") or ""
        f_json = r_dict.get("fields_json") or "{}"
        if "主角" in tags or "男主" in tags or "女主" in tags or "主角" in f_json:
            return r_dict

    # 若未明确标记，但有角色，返回第一个角色
    if rows:
        return dict(rows[0])
    return None


@router.get("/works/{work_id}/protagonist")
def get_protagonist_state(work_id: int):
    """获取作品的主角金手指状态看板。"""
    db = get_db()
    ent = _get_protagonist_entity(db, work_id)
    if not ent:
        return {
            "work_id": work_id,
            "has_protagonist": False,
            "entity_id": None,
            "name": "",
            "cultivation_level": "",
            "cheat_name": "",
            "cheat_progress": "",
            "current_resources": "",
            "core_goals": "",
            "key_items": [],
            "notes": "",
        }

    f_dict = {}
    try:
        f_dict = json.loads(ent.get("fields_json") or "{}")
    except Exception:
        pass

    key_items = f_dict.get("key_items") or []
    if isinstance(key_items, str):
        key_items = [k.strip() for k in key_items.split(",") if k.strip()]

    return {
        "work_id": work_id,
        "has_protagonist": True,
        "entity_id": ent["id"],
        "name": ent["name"],
        "cultivation_level": f_dict.get("cultivation_level") or f_dict.get("境界") or f_dict.get("修为") or "",
        "cheat_name": f_dict.get("cheat_name") or f_dict.get("金手指") or f_dict.get("外挂") or "",
        "cheat_progress": f_dict.get("cheat_progress") or f_dict.get("金手指进度") or f_dict.get("外挂进度") or "",
        "current_resources": f_dict.get("current_resources") or f_dict.get("当前资源") or f_dict.get("数值状态") or "",
        "core_goals": f_dict.get("core_goals") or f_dict.get("当前目标") or f_dict.get("卡点") or "",
        "key_items": key_items,
        "notes": ent.get("content") or "",
    }


@router.put("/works/{work_id}/protagonist")
def update_protagonist_state(work_id: int, body: ProtagonistStateIn):
    """创建或更新作品的主角状态看板。"""
    db = get_db()
    ent = _get_protagonist_entity(db, work_id, body.entity_id)

    fields_update = {
        "身份": "主角",
        "cultivation_level": body.cultivation_level,
        "cheat_name": body.cheat_name,
        "cheat_progress": body.cheat_progress,
        "current_resources": body.current_resources,
        "core_goals": body.core_goals,
        "key_items": body.key_items,
    }

    if ent:
        eid = ent["id"]
        # 合并已有 fields
        old_fields = {}
        try:
            old_fields = json.loads(ent.get("fields_json") or "{}")
        except Exception:
            pass
        old_fields.update(fields_update)
        tags = ent.get("tags") or ""
        if "主角" not in tags:
            tags = (tags + ",主角").strip(",")

        content = body.notes if body.notes else ent.get("content", "")
        db.execute(
            """UPDATE entities 
               SET name = ?, content = ?, fields_json = ?, tags = ?, updated_at = datetime('now','localtime')
               WHERE id = ?""",
            (body.name or ent["name"], content, json.dumps(old_fields, ensure_ascii=False), tags, eid)
        )
        db.commit()
        return {"ok": True, "entity_id": eid, "action": "updated"}
    else:
        # 新建主角实体
        tags = "主角"
        cur = db.execute(
            """INSERT INTO entities (work_id, category, name, content, fields_json, tags)
               VALUES (?, 'character', ?, ?, ?, ?)""",
            (work_id, body.name, body.notes, json.dumps(fields_update, ensure_ascii=False), tags)
        )
        db.commit()
        return {"ok": True, "entity_id": cur.lastrowid, "action": "created"}
