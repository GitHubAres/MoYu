# -*- coding: utf-8 -*-
from conftest import make_work, make_wvc
from app.db import get_db
from app.workflow_assets import extract_structured_assets_from_text
import json


def test_character_card_fields_json_extraction():
    """验证角色卡提取是否完整解析了 identity, personality, background, goal 结构化档案"""
    raw_cast_md = """
### 宁恪（主角）
- **身份**：问剑宗弃徒，天生无垢剑体
- **性格**：沉稳隐忍，杀伐果断，重情重义
- **背景**：原为宗门首席天骄，因撞破禁地阴谋被师门构陷废去气海
- **核心动机**：探寻师门灭门惨案真相，重铸剑魄

### 顾青蝉（白月光）
- **定位**：素问阁圣女
- **特质**：外冷内热，医剑双绝
- **身世**：上古医圣血脉后裔
- **目标与变化**：寻找续命神药，摆脱宿命桎梏
"""
    assets = extract_structured_assets_from_text(raw_cast_md)
    ents = {e["name"]: e for e in assets["entities"]}
    assert "宁恪" in ents
    assert "顾青蝉" in ents

    # 验证 宁恪 的 fields_json
    nk_fields = ents["宁恪"]["fields_json"]
    assert "问剑宗弃徒" in nk_fields.get("identity", "")
    assert "沉稳隐忍" in nk_fields.get("personality", "")
    assert "构陷废去气海" in nk_fields.get("background", "")
    assert "重铸剑魄" in nk_fields.get("goal", "")

    # 验证 顾青蝉 的 fields_json (多别名同义词映射)
    gqc_fields = ents["顾青蝉"]["fields_json"]
    assert "素问阁圣女" in gqc_fields.get("identity", "")
    assert "外冷内热" in gqc_fields.get("personality", "")
    assert "医圣血脉" in gqc_fields.get("background", "")
    assert "摆脱宿命桎梏" in gqc_fields.get("goal", "")


def test_workflow_summary_assets_and_auto_intake_flow(client):
    w, v, c = make_wvc(client, "全流程反哺作品")
    work_id = w["id"]
    chapter_id = c["id"]

    db = get_db()
    # 1. 预先录入一个已有实体 '太玄门' 与已有伏笔
    client.post(f"/api/works/{work_id}/entities", json={
        "category": "faction",
        "name": "太玄门",
        "fields_json": {},
        "tags": "宗门"
    })
    client.post(f"/api/works/{work_id}/foreshadows", json={
        "title": "掌门身世之谜",
        "content": "当年被收养的孤儿",
        "status": "planted"
    })

    # 2. 模拟创建工作流运行实例
    cur = db.execute(
        """INSERT INTO workflow_runs (workflow_id, work_id, chapter_id, status, current_step)
           VALUES (1, ?, ?, 'running', 0)""",
        (work_id, chapter_id)
    )
    run_id = cur.lastrowid

    # 步骤 1 输出：包含已有势力 '太玄门' 与 新角色 '林渊'（带完整角色档案）、新道具 '太虚残剑'
    step1_output = """
## 势力谱系
| 势力 | 定位 | 宗旨与核心 |
| 太玄门 | 正道魁首 | 表面统御南疆 |

### 林渊（主角）
- **身份**：无极剑圣转世，散修剑客
- **性格**：孤傲冷静，不滞于物
- **背景**：千年前独断万古，今朝涅槃重修
- **目标与变化**：重聚散落的诛仙四剑，勘破轮回

## 核心物品
| 道具 | 品阶 | 核心法则/代价 |
| 太虚残剑 | 地阶绝品 | 撕裂虚空 |
"""
    db.execute(
        """INSERT INTO workflow_run_steps (run_id, step_seq, title, status, output, token_used)
           VALUES (?, 0, '世界观推演', 'approved', ?, 120)""",
        (run_id, step1_output)
    )

    # 步骤 2 输出：包含 新地点 '青云古殿'、已有伏笔 '掌门身世之谜'、新大纲与时间线
    step2_output = """
## 空间与地理
| 地点 | 归属 | 核心冲突/危险 |
| 青云古殿 | 禁地深处 | 封印松动大妖将出 |

### 伏笔计划表
| 伏笔标题 | 埋设内容 | 预定回收位置 |
| 掌门身世之谜 | 当年被收养的孤儿 | 第十章揭秘 |
| 剑圣遗蜕藏所 | 暗藏于青云古殿地下 | 第十五章揭秘 |

### 剧情时间线
- [开篇清晨] 林渊持太虚残剑前往青云古殿（涉及人物：林渊）

### 故事大纲
- 序章：古殿惊变
"""
    db.execute(
        """INSERT INTO workflow_run_steps (run_id, step_seq, title, status, output, token_used)
           VALUES (?, 1, '剧情大纲推演', 'approved', ?, 150)""",
        (run_id, step2_output)
    )
    db.execute("UPDATE workflow_runs SET status='done' WHERE id=?", (run_id,))
    db.commit()

    # 3. 调用全流程汇总资产抽取接口
    res = client.get(f"/api/workflows/runs/{run_id}/summary-assets")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["run_meta"]["work_id"] == work_id
    assert data["run_meta"]["chapter_id"] == chapter_id

    assets = data["assets"]
    ents = {e["name"]: e for e in assets["entities"]}
    assert "林渊" in ents
    assert "太玄门" in ents
    assert "太虚残剑" in ents
    assert "青云古殿" in ents

    # 验证新旧状态比对
    assert ents["林渊"]["is_new"] is True
    assert ents["太虚残剑"]["is_new"] is True
    assert ents["青云古殿"]["is_new"] is True
    assert ents["太玄门"]["is_new"] is False  # 库内已有太玄门

    # 验证林渊提取出的 fields_json 档案结构
    ly_fields = ents["林渊"]["fields_json"]
    assert "无极剑圣转世" in ly_fields.get("identity", "")
    assert "孤傲冷静" in ly_fields.get("personality", "")
    assert "重聚散落的诛仙四剑" in ly_fields.get("goal", "")

    # 4. 执行一键全流程资产规范同步反哺 (seq = 0)，显式指定 chapter_id
    sync_res = client.post(f"/api/workflows/runs/{run_id}/steps/0/sync-assets", json={
        "entities": [
            {"name": "林渊", "category": "character", "content": "无极剑圣转世", "tags": "主角", "fields_json": ly_fields},
            {"name": "太虚残剑", "category": "item", "content": "撕裂虚空", "tags": "神兵"},
            {"name": "青云古殿", "category": "location", "content": "禁地深处", "tags": "地点"},
            {"name": "太玄门", "category": "faction", "content": "正道魁首", "tags": "宗门"}
        ],
        "relations": [],
        "outline_nodes": [
            {"title": "序章：古殿惊变", "synopsis": "林渊入殿探险", "is_volume": False}
        ],
        "timeline_events": [
            {"time_label": "开篇清晨", "event": "林渊持太虚残剑前往青云古殿", "characters": "林渊"}
        ],
        "foreshadows": [
            {"title": "剑圣遗蜕藏所", "content": "暗藏于青云古殿地下", "status": "planted"}
        ],
        "notes": [],
        "chapter_id": chapter_id
    })
    assert sync_res.status_code == 200
    res_data = sync_res.json()
    assert res_data["work_id"] == work_id  # 验证返回了 work_id (解决前端 run 变量未定义问题)
    summary = res_data["summary"]
    assert summary["entities_added"] >= 3
    assert summary["outlines_added"] >= 1
    assert summary["timeline_events_added"] >= 1
    assert summary["foreshadows_added"] >= 1

    # 5. 验证万相谱中林渊角色的 fields_json 是否已精准入库
    all_ents = client.get(f"/api/works/{work_id}/entities").json()
    ent_ly = next(e for e in all_ents if e["name"] == "林渊")
    fields_saved = ent_ly["fields"]
    assert fields_saved.get("identity") == "无极剑圣转世，散修剑客"
    assert fields_saved.get("personality") == "孤傲冷静，不滞于物"
    assert fields_saved.get("background") == "千年前独断万古，今朝涅槃重修"
    assert fields_saved.get("goal") == "重聚散落的诛仙四剑，勘破轮回"

    # 6. 验证万相谱“章节引用与登场记录”自动关联 (解决问题四)
    # 不仅新实体(林渊/太虚残剑)，已有实体(太玄门)也应当自动关联到了本章！
    ly_chapters = client.get(f"/api/entities/{ent_ly['id']}/chapters").json()
    assert any(c_item["id"] == chapter_id for c_item in ly_chapters)

    ent_txm = next(e for e in all_ents if e["name"] == "太玄门")
    txm_chapters = client.get(f"/api/entities/{ent_txm['id']}/chapters").json()
    assert any(c_item["id"] == chapter_id for c_item in txm_chapters)

    ch_ents = client.get(f"/api/chapters/{chapter_id}/entities").json()
    ch_ent_names = [e["name"] for e in ch_ents]
    assert "林渊" in ch_ent_names
    assert "太虚残剑" in ch_ent_names
    assert "太玄门" in ch_ent_names


def test_batch_sync_outline_synopsis_update_and_stats(client):
    from app.services.plot_service import batch_sync_triad_assets
    w, v, c = make_wvc(client, "大纲梗概同步测试")
    work_id = w["id"]
    db = get_db()

    # 用例 1：作品中已存在大纲节点（title="第一章 剑斩云霄"，synopsis="旧梗概"）
    # 调 batch_sync_triad_assets 传入同名节点 + 新 synopsis="新梗概"
    # 期望：节点 synopsis 变为"新梗概"，返回 stats 含 outline_synopsis_updated == 1
    cur = db.execute(
        "INSERT INTO outline_nodes (work_id, parent_id, title, synopsis, status, sort_order) VALUES (?, NULL, ?, ?, 'pending', 1)",
        (work_id, "第一章 剑斩云霄", "旧梗概"),
    )
    node1_id = cur.lastrowid
    db.commit()

    stats1 = batch_sync_triad_assets(
        db=db,
        work_id=work_id,
        timeline_events=[],
        foreshadows=[],
        outline_nodes=[{"title": "第一章 剑斩云霄", "synopsis": "新梗概"}],
    )
    db.commit()
    assert stats1.get("outline_synopsis_updated") == 1
    row1 = db.execute("SELECT synopsis FROM outline_nodes WHERE id = ?", (node1_id,)).fetchone()
    assert row1["synopsis"] == "新梗概"

    # 用例 2：同上但传入 synopsis=""
    # 期望：旧梗概原样保留（不被清空），outline_synopsis_updated == 0
    stats2 = batch_sync_triad_assets(
        db=db,
        work_id=work_id,
        timeline_events=[],
        foreshadows=[],
        outline_nodes=[{"title": "第一章 剑斩云霄", "synopsis": ""}],
    )
    db.commit()
    assert stats2.get("outline_synopsis_updated") == 0
    row2 = db.execute("SELECT synopsis FROM outline_nodes WHERE id = ?", (node1_id,)).fetchone()
    assert row2["synopsis"] == "新梗概"

    # 用例 3：节点不存在
    # 维持 INSERT 原行为，outline_nodes_added == 1 且 outline_synopsis_updated == 0
    stats3 = batch_sync_triad_assets(
        db=db,
        work_id=work_id,
        timeline_events=[],
        foreshadows=[],
        outline_nodes=[{"title": "第二章 踏雪无痕", "synopsis": "新章节梗概"}],
    )
    db.commit()
    assert stats3.get("outline_nodes_added") == 1
    assert stats3.get("outline_synopsis_updated") == 0
    row3 = db.execute("SELECT synopsis FROM outline_nodes WHERE work_id = ? AND title = ?", (work_id, "第二章 踏雪无痕")).fetchone()
    assert row3 is not None
    assert row3["synopsis"] == "新章节梗概"