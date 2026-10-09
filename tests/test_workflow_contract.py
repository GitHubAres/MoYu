# -*- coding: utf-8 -*-
# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
import pytest
from app.workflow_assets import extract_structured_assets_from_text, merge_assets


def test_h1_multi_block_merge():
    step1 = """正文内容一
<!-- MOYU:ASSETS
{
  "entities": [{"name": "宁恪", "category": "character", "content": "主角"}],
  "relations": [{"source": "宁恪", "target": "苏昀", "label": "同门"}],
  "foreshadows": [{"title": "铜钥匙", "content": "藏在旧宅门梁"}]
}
MOYU:ASSETS -->"""

    step2 = """正文内容二
<!-- MOYU:ASSETS
{
  "entities": [{"name": "苏昀", "category": "character", "content": "师兄"}],
  "timeline_events": [{"time_label": "开元三年", "event": "灵脉抽签", "characters": "宁恪, 苏昀"}]
}
MOYU:ASSETS -->"""

    step3 = """正文内容三
<!-- MOYU:ASSETS
{
  "foreshadows": [{"title": "断剑", "content": "埋在剑阁后山"}],
  "outline_nodes": [{"title": "第二章·旧宅", "summary": "探访旧宅秘密"}]
}
MOYU:ASSETS -->"""

    steps = [step1, step2, step3]
    extracted = [extract_structured_assets_from_text(s) for s in steps]
    merged = merge_assets(extracted)

    ent_names = [e["name"] for e in merged.get("entities", [])]
    assert "宁恪" in ent_names
    assert "苏昀" in ent_names

    tl_events = [t["event"] for t in merged.get("timeline_events", [])]
    assert "灵脉抽签" in tl_events

    fs_titles = [f["title"] for f in merged.get("foreshadows", [])]
    assert "铜钥匙" in fs_titles
    assert "断剑" in fs_titles

    ot_titles = [o["title"] for o in merged.get("outline_nodes", [])]
    assert "第二章·旧宅" in ot_titles

    assert merged.get("source") == "contract"


def test_h1_deduplication():
    step1 = """<!-- MOYU:ASSETS
{"entities": [{"name": "宁恪", "category": "character", "content": "初次登场"}]}
MOYU:ASSETS -->"""

    step2 = """<!-- MOYU:ASSETS
{"entities": [{"name": "宁恪", "category": "character", "content": "修为突破"}]}
MOYU:ASSETS -->"""

    extracted = [extract_structured_assets_from_text(s) for s in [step1, step2]]
    merged = merge_assets(extracted)
    names = [e["name"] for e in merged.get("entities", [])]
    assert names == ["宁恪"]
    assert merged["entities"][0]["content"] == "初次登场"


def test_h1_mixed_source():
    step1 = """<!-- MOYU:ASSETS
{"entities": [{"name": "宁恪", "category": "character", "content": "主角"}]}
MOYU:ASSETS -->"""

    step2 = """**主角**：顾风\n开元五年，顾风拜入青云宗。"""

    extracted = [extract_structured_assets_from_text(s) for s in [step1, step2]]
    merged = merge_assets(extracted)

    assert merged.get("source") == "mixed"
    ent_names = [e["name"] for e in merged.get("entities", [])]
    assert "宁恪" in ent_names
    assert any("顾风" in e["name"] for e in merged.get("entities", []))


def test_h1_rejected_merge():
    step1 = {"_rejected": [{"kind": "note", "title": "t1", "reason": "r1"}], "source": "heuristic"}
    step2 = {
        "_rejected": [
            {"kind": "note", "title": "t2", "reason": "r2"},
            {"kind": "note", "title": "t1", "reason": "r1"},
        ],
        "source": "heuristic",
    }
    merged = merge_assets([step1, step2])
    rejected = merged.get("_rejected", [])
    assert len(rejected) == 2
    keys = [(r.get("kind"), r.get("title"), r.get("reason")) for r in rejected]
    assert len(keys) == len(set(keys))


from app.services.output_normalizer import extract_assets_block


def test_h2a_single_marker_block():
    text = """前言
<!-- MOYU:ASSETS
{
  "entities": [{"name": "宁恪", "category": "character", "content": "主角"}]
}
-->
后记"""
    block = extract_assets_block(text)
    assert block is not None
    assert block.get("entities")[0]["name"] == "宁恪"

    assets = extract_structured_assets_from_text(text)
    assert assets.get("source") == "contract"
    assert any(e["name"] == "宁恪" for e in assets.get("entities", []))


def test_h2a_double_marker_preserved():
    text = """<!-- MOYU:ASSETS
{"entities": [{"name": "宁恪", "category": "character", "content": "主角"}]}
MOYU:ASSETS -->"""
    block = extract_assets_block(text)
    assert block is not None
    assets = extract_structured_assets_from_text(text)
    assert assets.get("source") == "contract"


def test_h2a_no_contract_block():
    text = "普通文本 <!-- 普通注释 --> 没有任何契约块"
    assert extract_assets_block(text) is None


from app.workflow_assets import SyncAssetsIn, AssetEntityIn, sync_assets_to_database, normalize_category


def test_h3a_category_normalization_in_db(client):
    from conftest import make_wvc
    import app.db as db_module

    w, v, c = make_wvc(client, "测试分类归一作品")
    work_id = w["id"]
    db = db_module.get_db()

    body = SyncAssetsIn(
        entities=[
            AssetEntityIn(name="宁恪", category="人物", content="主角"),
            AssetEntityIn(name="青云宗", category="门派", content="宗门"),
            AssetEntityIn(name="太玄峰", category="地点", content="山峰"),
            AssetEntityIn(name="斩雪剑", category="神兵", content="佩剑"),
            AssetEntityIn(name="灵气潮汐", category="世界观", content="法则"),
            AssetEntityIn(name="未知事物", category="乱写的分类", content="杂项"),
            AssetEntityIn(name="无分类人", content="普通人"),
            AssetEntityIn(name="空串分类人", category="", content="普通人"),
            AssetEntityIn(name="标准角色", category="character", content="合法角色"),
        ]
    )
    sync_assets_to_database(db, work_id, body)

    rows = {
        r["name"]: r["category"]
        for r in db.execute("SELECT name, category FROM entities WHERE work_id=?", (work_id,)).fetchall()
    }
    assert rows["宁恪"] == "character"
    assert rows["青云宗"] == "faction"
    assert rows["太玄峰"] == "place"
    assert rows["斩雪剑"] == "item"
    assert rows["灵气潮汐"] == "term"
    assert rows["未知事物"] == "term"
    assert rows["无分类人"] == "character"
    assert rows["空串分类人"] == "character"
    assert rows["标准角色"] == "character"


def test_h3a_normalize_category_unit():
    assert normalize_category("人物") == "character"
    assert normalize_category("主角") == "character"
    assert normalize_category("地点") == "place"
    assert normalize_category("门派") == "faction"
    assert normalize_category("神兵") == "item"
    assert normalize_category("世界观") == "term"
    assert normalize_category("乱写的分类") == "term"
    assert normalize_category(None) == "character"
    assert normalize_category("") == "character"
    assert normalize_category("character") == "character"
    assert normalize_category("place") == "place"
