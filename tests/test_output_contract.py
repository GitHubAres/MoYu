# -*- coding: utf-8 -*-
# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
import pytest
from app.workflow_assets import extract_structured_assets_from_text
from app.services.output_normalizer import sanitize_asset_item


def test_a4_gate_sample():
    """1. A-4 门禁样例：entities 不含「伏笔暗线」、notes 不含「世界观 · 设定」、timeline_events 抽出事件、_rejected 非空"""
    sample = """好的，我已经根据你的要求完成创作。以下是修改后的内容：
### 世界观设定
- 灵根：天地灵气的载体
### 伏笔暗线
| 伏笔标题 | 回收条件 |
| --- | --- |
| 青玉佩的来历 | 第三卷揭示身世 |
### 时间线
- 开元三年 · 顾风下山，途经剑阁
希望以上内容对你有帮助，如需调整请告诉我。"""

    assets = extract_structured_assets_from_text(sample)

    # entities 不含「伏笔暗线」
    ent_names = [e.get("name") for e in assets.get("entities", [])]
    assert "伏笔暗线" not in ent_names

    # notes 不含「世界观 · 设定」
    note_titles = [n.get("title") for n in assets.get("notes", [])]
    assert "世界观 · 设定" not in note_titles
    assert "世界观设定" not in note_titles

    # timeline_events 抽出「开元三年 / 顾风下山，途经剑阁」
    tl_events = [t.get("event") for t in assets.get("timeline_events", [])]
    assert any("顾风下山" in ev for ev in tl_events)
    tl_times = [t.get("time_label") for t in assets.get("timeline_events", [])]
    assert any("开元三年" in tm for tm in tl_times)

    # _rejected 非空且记录了被拒标题
    rejected = assets.get("_rejected", [])
    assert len(rejected) > 0


def test_contract_block_priority():
    """2. 契约块优先：有契约块时 source == 'contract'，块内资产 100% 被抽出，正文中套话与 ### 标题不进入结果"""
    sample = """好的，以下是为您创作的内容：
### 杂乱标题
- 正文第一段...
<!-- MOYU:ASSETS
{
  "entities": [{"name": "顾风", "category": "character", "content": "主角"}],
  "relations": [{"from": "顾风", "to": "青云宗", "label": "弟子"}],
  "timeline_events": [{"time_label": "天宝初年", "event": "登太玄峰"}],
  "foreshadows": [{"title": "残剑来历", "content": "剑中有灵"}],
  "outline_nodes": [{"title": "第一卷 问道", "synopsis": "少年出山"}]
}
MOYU:ASSETS -->
希望对你有帮助，请随时告诉我。"""

    assets = extract_structured_assets_from_text(sample)
    assert assets.get("source") == "contract"

    ent_names = [e.get("name") for e in assets.get("entities", [])]
    assert "顾风" in ent_names
    assert "杂乱标题" not in ent_names
    assert "好的" not in ent_names

    assert len(assets.get("relations", [])) >= 1
    assert any("登太玄峰" in ev.get("event", "") for ev in assets.get("timeline_events", []))
    assert any("残剑来历" in f.get("title", "") for f in assets.get("foreshadows", []))
    assert any("第一卷 问道" in o.get("title", "") for o in assets.get("outline_nodes", []))


def test_chatter_only_produces_no_assets():
    """3. 套话不产生资产：无契约块且仅有套话的输入，所有资产列表为空"""
    chatter_sample = """好的，我已经根据您的要求完成创作。
以下是修改后的内容：
---
希望以上对你有帮助，如有任何问题请随时告诉我。"""

    assets = extract_structured_assets_from_text(chatter_sample)
    assert assets.get("source") == "heuristic"
    assert len(assets.get("entities", [])) == 0
    assert len(assets.get("relations", [])) == 0
    assert len(assets.get("timeline_events", [])) == 0
    assert len(assets.get("foreshadows", [])) == 0
    assert len(assets.get("outline_nodes", [])) == 0
    assert len(assets.get("notes", [])) == 0


def test_sanitize_rejects_dirty_data():
    """4. 资产校验拒绝脏数据（依赖阶段 C-1 前先断言 sanitize_asset_item 返回 False）"""
    # 套话标题
    ok, r = sanitize_asset_item({"title": "好的，这是修改后的内容"}, "foreshadow")
    assert not ok and "套话" in r

    # 空标题
    ok_empty, r_empty = sanitize_asset_item({"name": ""}, "entity")
    assert not ok_empty and "空" in r_empty

    # 超长标题
    ok_long, r_long = sanitize_asset_item({"name": "长" * 35}, "entity")
    assert not ok_long and "长" in r_long

    # 截断标记
    ok_trunc, r_trunc = sanitize_asset_item({"title": "正常标题", "content": "前文……[中段内容已截断]……后文"}, "foreshadow")
    assert not ok_trunc and "截断" in r_trunc

    # 纯标点
    ok_punc, r_punc = sanitize_asset_item({"name": "---***"}, "entity")
    assert not ok_punc and "有效" in r_punc
