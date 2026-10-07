# -*- coding: utf-8 -*-
from conftest import make_work, make_wvc
from app.db import get_db


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

    # 步骤 1 输出：包含已有势力 '太玄门' 与 新人物 '林渊'、新道具 '太虚残剑'
    step1_output = """
## 势力谱系
| 势力 | 定位 | 宗旨与核心 |
| 太玄门 | 正道魁首 | 表面统御南疆 |

### 林渊（主角）
- **身份**：无极剑圣转世
- **核心动机**：探寻天道真相

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

    # 验证伏笔比对
    fs_map = {f["title"]: f for f in assets["foreshadows"]}
    assert "掌门身世之谜" in fs_map
    assert fs_map["掌门身世之谜"]["is_new"] is False  # 库内已有
    assert "剑圣遗蜕藏所" in fs_map
    assert fs_map["剑圣遗蜕藏所"]["is_new"] is True   # 新伏笔

    # 4. 执行一键全流程资产规范同步反哺 (seq = 0)
    sync_res = client.post(f"/api/workflows/runs/{run_id}/steps/0/sync-assets", json={
        "entities": [
            {"name": "林渊", "category": "character", "content": "无极剑圣转世", "tags": "主角"},
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
        "notes": []
    })
    assert sync_res.status_code == 200
    summary = sync_res.json()["summary"]
    assert summary["entities_added"] >= 3
    assert summary["outlines_added"] >= 1
    assert summary["timeline_events_added"] >= 1
    assert summary["foreshadows_added"] >= 1

    # 5. 验证新增实体已自动与当前章节 chapter_id 绑定
    ch_ents = client.get(f"/api/chapters/{chapter_id}/entities").json()
    ch_ent_names = [e["name"] for e in ch_ents]
    assert "林渊" in ch_ent_names
    assert "太虚残剑" in ch_ent_names

    # 6. 再次拉取汇总资产，此时所有条目应当均被识别为已存在 (is_new: False)
    again_res = client.get(f"/api/workflows/runs/{run_id}/summary-assets").json()
    again_ents = {e["name"]: e for e in again_res["assets"]["entities"]}
    assert again_ents["林渊"]["is_new"] is False
    assert again_ents["太虚残剑"]["is_new"] is False
    again_fs = {f["title"]: f for f in again_res["assets"]["foreshadows"]}
    assert again_fs["剑圣遗蜕藏所"]["is_new"] is False
