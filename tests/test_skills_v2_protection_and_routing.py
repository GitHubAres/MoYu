# -*- coding: utf-8 -*-
import pytest
from app.db import get_db, BUILTIN_SKILLS
from app.features import resolve_skill
from app.services.output_normalizer import SKILL_ASSET_CONTRACTS, ASSET_CONTRACT_KEYS, extract_assets_block

def test_user_modified_skill_protection(client):
    """验证当用户微调过某个内置技能后，系统重启/重新初始化种子不会覆盖用户修改。"""
    db = get_db()
    # 模拟用户微调了 default-continue
    skill = db.execute("SELECT id, body_md FROM skills WHERE name = 'default-continue'").fetchone()
    assert skill is not None
    skill_id = skill[0]
    
    custom_body = skill[1] + "\n\n【用户私人自定义笔记】严禁覆盖！"
    res = client.patch(f"/api/skills/{skill_id}", json={"body_md": custom_body})
    assert res.status_code == 200
    
    # 验证 user_modified 变为 1
    updated = db.execute("SELECT user_modified, body_md FROM skills WHERE id = ?", (skill_id,)).fetchone()
    assert updated[0] == 1
    assert "【用户私人自定义笔记】严禁覆盖！" in updated[1]
    
    # 执行种子初始化 migrate_and_seed_skills
    from app.db import migrate_and_seed_skills
    migrate_and_seed_skills(db)
    
    # 再次读取，确认用户的修改依然被完好保留
    after_seed = db.execute("SELECT user_modified, body_md FROM skills WHERE id = ?", (skill_id,)).fetchone()
    assert after_seed[0] == 1
    assert "【用户私人自定义笔记】严禁覆盖！" in after_seed[1]

def test_alias_and_task_routing(client):
    """验证所有新老别名及 task 路由均能命中对应的技能，杜绝 None。"""
    test_cases = [
        ("continue", "default-continue"),
        ("expand", "default-expand"),
        ("polish", "default-rewrite"),
        ("rewrite", "default-rewrite"),
        ("condense", "default-shorten"),
        ("shorten", "default-shorten"),
        ("outline", "default-outline"),
        ("check", "default-audit"),
        ("audit", "default-audit"),
        ("analyze", "default-analysis"),
        ("analysis", "default-analysis"),
        ("prose-continue", "default-continue"),
        ("prose-expand", "default-expand"),
        ("prose-polish", "default-rewrite"),
        ("audit-synopsis-distill", "default-shorten"),
        ("novel-outline-macro", "default-outline"),
        ("audit-consistency", "default-audit"),
        ("audit-pacing-rhythm", "default-analysis"),
        ("audit-de-aitone", "default-rewrite"),
    ]
    for task_name, expected_skill_name in test_cases:
        resolved = resolve_skill(None, task_name)
        assert resolved is not None, f"任务 {task_name} 解析失败"
        assert resolved["name"] == expected_skill_name, f"任务 {task_name} 期望命中 {expected_skill_name}，实际命中 {resolved['name']}"

def test_extract_assets_block_last_block_and_tail_recovery():
    """验证提取器取最后一个契约块，并具备尾部容错补齐能力。"""
    text_multiple = """
    前文示例：
    <!-- MOYU:ASSETS
    {"notes": [{"title": "示例干扰"}]}
    MOYU:ASSETS -->
    正文推进...
    <!-- MOYU:ASSETS
    {"timeline_events": [{"time_label": "天授三年", "event": "折剑伏诛", "characters": "陆沉"}]}
    MOYU:ASSETS -->
    """
    res = extract_assets_block(text_multiple)
    assert res is not None
    assert len(res.get("timeline_events", [])) == 1
    assert res["timeline_events"][0]["time_label"] == "天授三年"
    assert len(res.get("notes", [])) == 0

    # 尾部截断宽容测试
    truncated_text = """
    正文打斗完毕。
    <!-- MOYU:ASSETS
    {"notes": [{"title": "打斗略平"}]
    """
    res_trunc = extract_assets_block(truncated_text)
    assert res_trunc is not None
    assert len(res_trunc.get("notes", [])) == 1
    assert res_trunc["notes"][0]["title"] == "打斗略平"
