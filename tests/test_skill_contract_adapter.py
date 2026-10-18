# -*- coding: utf-8 -*-
# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
"""契约适配式重构回归：验证技能 → 墨语核心模块的契约装配。

覆盖：
1. 13 个内置技能全部挂载资产键声明（SKILL_ASSET_CONTRACTS）；
2. 直接调用路径 build_skill_system_prompt 注入 MOYU:ASSETS（强制）契约，
   不再使用旧的软提示文案；
3. 炼丹炉 import_lore 经 canonicalize_assets 归一（中文别名 category → 枚举，
   outline 父子关系解析），与技能体系落库口径一致（消除双轨）。
"""
import pytest

from app.db import BUILTIN_SKILLS, get_db
from app.features import build_skill_system_prompt, get_alchemy_engine, _ImportLoreIn
from app.services.output_normalizer import SKILL_ASSET_CONTRACTS, build_contract_clause

EXPECTED_NAMES = {
    "audit-consistency",
    "audit-de-aitone",
    "audit-foreshadow",
    "audit-pacing-rhythm",
    "audit-synopsis-distill",
    "audit-timeline",
    "novel-cast",
    "novel-faction-graph",
    "novel-foreshadow-matrix",
    "novel-forge",
    "novel-hook-engineer",
    "novel-lead-arc",
    "novel-magic-system",
    "novel-outline-macro",
    "novel-premise",
    "novel-scene",
    "novel-timeline",
    "novel-world",
    "prose-combat",
    "prose-continue",
    "prose-dialogue",
    "prose-expand",
    "prose-polish",
    "prose-sensory",
}

OLD_SOFT_CLAUSE = "请在回答末尾追加合法的"
FORCED_CLAUSE = "【结构化产物交付契约 MOYU:ASSETS（强制）"


def test_all_builtin_skills_have_contract_mapping(client):
    names = {s["name"] for s in BUILTIN_SKILLS}
    assert names == EXPECTED_NAMES
    for name in EXPECTED_NAMES:
        assert name in SKILL_ASSET_CONTRACTS, f"{name} 缺少资产键声明"
        assert SKILL_ASSET_CONTRACTS[name], f"{name} 资产键声明为空"
        # 声明键必须落在权威 8 键集合内
        for k in SKILL_ASSET_CONTRACTS[name]:
            assert k in {
                "work_info", "entities", "relations", "timeline_events",
                "foreshadows", "outline_nodes", "chapter_synopses", "notes",
            }, f"{name} 含非法资产键 {k}"


def test_direct_skill_prompt_injects_forced_contract(client):
    db = get_db()
    placeholders = ",".join("?" * len(EXPECTED_NAMES))
    rows = db.execute(
        f"SELECT id, name FROM skills WHERE name IN ({placeholders})", tuple(EXPECTED_NAMES)
    ).fetchall()
    name_to_id = {r["name"]: r["id"] for r in rows}
    assert len(name_to_id) == len(EXPECTED_NAMES), "部分内置技能未入库"

    for name in EXPECTED_NAMES:
        prompt, _ = build_skill_system_prompt(skill_id=name_to_id[name], task="continue")
        assert FORCED_CLAUSE in prompt, f"{name} 未注入强制契约"
        assert OLD_SOFT_CLAUSE not in prompt, f"{name} 仍残留旧软提示"
        for key in SKILL_ASSET_CONTRACTS[name]:
            assert key in prompt, f"{name} 契约未包含声明键 {key}"


def test_build_contract_clause_only_lists_required_keys():
    # 与既有 test_output_contract.test_l1a 对齐：仅列所需键、空数组占位
    partial = build_contract_clause(["outline_nodes", "chapter_synopses"])
    assert '"outline_nodes": []' in partial
    assert '"chapter_synopses": []' in partial
    assert '"entities": []' not in partial
    full = build_contract_clause(["entities", "notes"])
    assert '"entities": []' in full and '"notes": []' in full


def test_alchemy_import_lore_normalizes_and_links(client):
    """炼丹炉 import_lore 与技能体系共用 canonicalize_assets：中文别名归一 + 父子大纲。"""
    w = client.post("/api/works", json={"title": "炼丹炉归一测试"}).json()
    work_id = w["id"]
    engine = get_alchemy_engine()

    body = _ImportLoreIn(
        work_id=work_id,
        entities=[{"category": "人物", "name": "归一侠", "content": "测试人物", "tags": "x"}],
        outline=[
            {"title": "第一卷", "synopsis": "开篇卷", "parent": None},
            {"title": "第一章", "synopsis": "相遇", "parent": "第一卷"},
        ],
    )
    res = engine.import_lore(body)
    assert res["created"]["entities"] >= 1

    db = get_db()
    row = db.execute(
        "SELECT category, name FROM entities WHERE work_id=? AND name=?", (work_id, "归一侠")
    ).fetchone()
    assert row is not None, "实体未入库"
    assert row["category"] == "character", "中文别名 category 未归一为 character"

    vol = db.execute(
        "SELECT id FROM outline_nodes WHERE work_id=? AND title=?", (work_id, "第一卷")
    ).fetchone()
    chap = db.execute(
        "SELECT id, parent_id FROM outline_nodes WHERE work_id=? AND title=?", (work_id, "第一章")
    ).fetchone()
    assert vol is not None and chap is not None, "大纲节点未入库"
    assert chap["parent_id"] == vol["id"], "大纲父子关系未解析"


def test_work_info_ingested_from_contract_block(client):
    """验证 M1(P0): work_info 能被 extract_assets_block 正确提取并贯通到 canonicalize_assets 与落库。"""
    from app.services.output_normalizer import extract_assets_block, canonicalize_assets
    from app.workflow_assets import extract_structured_assets_from_text, sync_assets_to_database, SyncAssetsIn
    from app.db import get_db

    sample = (
        "正文内容简述...\n\n"
        "<!-- MOYU:ASSETS\n"
        "{\n"
        '  "work_info": {"title": "修仙长生录", "genre": "玄幻修真", "intro": "少年自微末崛起。"},\n'
        '  "entities": [{"name": "韩立", "category": "character", "content": "主角"}]\n'
        "}\n"
        "MOYU:ASSETS -->"
    )

    # 1. 契约块提取器不丢弃 work_info
    block = extract_assets_block(sample)
    assert block is not None
    assert block["work_info"] == {
        "title": "修仙长生录",
        "genre": "玄幻修真",
        "intro": "少年自微末崛起。",
    }
    assert len(block["entities"]) == 1

    # 2. canonicalize_assets 保持 work_info
    canon = canonicalize_assets(block)
    assert canon["work_info"] == {
        "title": "修仙长生录",
        "genre": "玄幻修真",
        "intro": "少年自微末崛起。",
    }

    # 3. extract_structured_assets_from_text 优先读取契约块的 work_info
    structured = extract_structured_assets_from_text(sample, source_kind="ai")
    assert structured["source"] == "contract"
    assert structured["work_info"]["title"] == "修仙长生录"
    assert structured["work_info"]["genre"] == "玄幻修真"
    assert structured["work_info"]["intro"] == "少年自微末崛起。"

    # 4. sync_assets_to_database 能够正确 UPDATE works 表
    db = get_db()
    cur = db.execute("INSERT INTO works (title, genre, intro) VALUES (?, ?, ?)", ("原书名", "原流派", "原简介"))
    work_id = cur.lastrowid

    sync_in = SyncAssetsIn(
        work_id=work_id,
        work_info=structured["work_info"],
        entities=structured["entities"],
    )
    res = sync_assets_to_database(db, work_id, sync_in)
    assert res["work_info_updated"] is True

    row = db.execute("SELECT title, genre, intro FROM works WHERE id=?", (work_id,)).fetchone()
    assert row["title"] == "修仙长生录"
    assert row["genre"] == "玄幻修真"
    assert row["intro"] == "少年自微末崛起。"


def test_outline_parent_title_resolved_and_relations_synced(client):
    """验证 Phase B (M2 + M4/M6): parent_title 准确挂载到父卷，relations 准确落库。"""
    from app.services.output_normalizer import extract_assets_block
    from app.workflow_assets import extract_structured_assets_from_text, sync_assets_to_database, SyncAssetsIn
    from app.db import get_db

    db = get_db()
    cur = db.execute("INSERT INTO works (title, genre, intro) VALUES (?, ?, ?)", ("测试大纲与关系作品", "奇幻", "测试"))
    work_id = cur.lastrowid

    sample = (
        "分析正文...\n\n"
        "<!-- MOYU:ASSETS\n"
        "{\n"
        '  "entities": [\n'
        '    {"name": "林动", "category": "character", "content": "少年主角", "fields_json": {"desire": "重振林家", "flaw": "冲动"}},\n'
        '    {"name": "绫清竹", "category": "character", "content": "九天太清宫天骄"}\n'
        '  ],\n'
        '  "relations": [\n'
        '    {"from_name": "林动", "to_name": "绫清竹", "label": "墓府之约"}\n'
        '  ],\n'
        '  "outline_nodes": [\n'
        '    {"title": "第一卷 大荒风云", "synopsis": "少年出青阳镇", "is_volume": true},\n'
        '    {"title": "第一章 淬体", "synopsis": "初得石符", "is_volume": false, "parent_title": "第一卷 大荒风云"},\n'
        '    {"title": "第二章 较量", "synopsis": "族比显威", "is_volume": false, "parent_title": "第一卷 大荒风云"}\n'
        '  ]\n'
        "}\n"
        "MOYU:ASSETS -->"
    )

    block = extract_assets_block(sample)
    assert block is not None
    assert len(block["outline_nodes"]) == 3
    assert len(block["relations"]) == 1
    assert len(block["entities"]) == 2

    structured = extract_structured_assets_from_text(sample)
    sync_in = SyncAssetsIn(
        work_id=work_id,
        entities=structured["entities"],
        relations=structured["relations"],
        outline_nodes=structured["outline_nodes"],
    )
    res = sync_assets_to_database(db, work_id, sync_in)
    assert res["relations_added"] == 1
    assert res["outlines_added"] == 3

    # 验证卷与章节的父子关系挂载
    vol = db.execute("SELECT id FROM outline_nodes WHERE work_id=? AND title=?", (work_id, "第一卷 大荒风云")).fetchone()
    assert vol is not None
    chap1 = db.execute("SELECT id, parent_id FROM outline_nodes WHERE work_id=? AND title=?", (work_id, "第一章 淬体")).fetchone()
    chap2 = db.execute("SELECT id, parent_id FROM outline_nodes WHERE work_id=? AND title=?", (work_id, "第二章 较量")).fetchone()
    assert chap1 is not None and chap1["parent_id"] == vol["id"], "第一章未正确挂载到第一卷"
    assert chap2 is not None and chap2["parent_id"] == vol["id"], "第二章未正确挂载到第一卷"

    # 验证 relations 落库与字段
    rel = db.execute(
        "SELECT r.label, f.name as from_n, t.name as to_n FROM entity_relations r "
        "JOIN entities f ON r.from_id = f.id "
        "JOIN entities t ON r.to_id = t.id "
        "WHERE r.work_id=?",
        (work_id,)
    ).fetchone()
    assert rel is not None
    assert rel["from_n"] == "林动"
    assert rel["to_n"] == "绫清竹"
    assert rel["label"] == "墓府之约"
