
# -*- coding: utf-8 -*-
from conftest import make_work, make_wvc
from app.workflow_assets import extract_structured_assets_from_text
import app.db as db


def test_builtin_skill_delivery_specs_compatible_with_extractor():
    skills = {s["name"]: s["body_md"] for s in db.BUILTIN_SKILLS}

    # 1. novel-cast
    assert "novel-cast" in skills
    cast_sample = """
### 宁恪（主角）
- **身份**：问剑宗弃徒
- **表面欲望**：查清宗门灭门真相

### 角色关系网
| 关系对 | 表面关系 | 核心冲突 |
| 宁恪 与 孤云子 | 师徒 | 理念分歧与叛逃追杀 |
"""
    assets = extract_structured_assets_from_text(cast_sample)
    ent_names = [e["name"] for e in assets["entities"]]
    assert "宁恪" in ent_names
    assert len(assets["relations"]) >= 1
    assert assets["relations"][0]["from_name"] == "宁恪"
    assert assets["relations"][0]["to_name"] == "孤云子"

    # 2. novel-world
    assert "novel-world" in skills
    world_sample = """
## 势力格局
| 势力 | 定位 | 宗旨与领袖 |
| 问剑宗 | 正道魁首 | 剑道正统，孤云子 |

## 地理场景
| 地点 | 归属 | 特征与危险 |
| 沧澜古城 | 中州皇朝 | 千年古阵残缺 |

## 道具神兵
| 道具 | 品阶 | 功能与代价 |
| 太虚残剑 | 地阶绝品 | 撕裂禁制消耗寿元 |
"""
    assets_w = extract_structured_assets_from_text(world_sample)
    w_ents = {e["name"]: e["category"] for e in assets_w["entities"]}
    assert "问剑宗" in w_ents and w_ents["问剑宗"] == "faction"
    assert "沧澜古城" in w_ents and w_ents["沧澜古城"] == "location"
    assert "太虚残剑" in w_ents and w_ents["太虚残剑"] == "item"


def test_detect_unregistered_and_batch_intake_flow(client):
    w, v, c = make_wvc(client, "探测测试作品")
    work_id = w["id"]
    chapter_id = c["id"]

    # 1. 预先录入一个已知角色 '林渊'
    r_known = client.post(f"/api/works/{work_id}/entities", json={
        "category": "character",
        "name": "林渊",
        "fields_json": {"aliases": ["渊哥", "无极道人"]},
        "tags": "主角"
    })
    assert r_known.status_code == 201

    # 2. 正文出现已知角色与未入库新实体
    chapter_content = """
林渊握紧了手中的【道具】太虚残剑，遥望前方的【地点】青云古殿。
【势力】天衍阁的斥候早已埋伏在此。
【法则】灵气守恒在此地并不生效。
而在暗处，渊哥隐匿了气息。
"""

    detect_res = client.post(f"/api/works/{work_id}/entities/detect-unregistered", json={
        "content": chapter_content,
        "chapter_id": chapter_id
    })
    assert detect_res.status_code == 200
    unregistered = detect_res.json()["unregistered"]

    unreg_names = [item["name"] for item in unregistered]
    # 已知角色'林渊'及其别名'渊哥'绝对不能出现在未入库列表中
    assert "林渊" not in unreg_names
    assert "渊哥" not in unreg_names

    # 新实体应该被全部精准探测到
    assert "太虚残剑" in unreg_names
    assert "青云古殿" in unreg_names
    assert "天衍阁" in unreg_names
    assert "灵气守恒" in unreg_names

    # 类别映射正确
    by_name = {item["name"]: item for item in unregistered}
    assert by_name["太虚残剑"]["category"] == "item"
    assert by_name["青云古殿"]["category"] == "place"
    assert by_name["天衍阁"]["category"] == "faction"
    assert by_name["灵气守恒"]["category"] == "term"

    # 3. 模拟用户勾选并确认入库 '太虚残剑' 与 '天衍阁'
    intake_res = client.post(f"/api/works/{work_id}/entities/batch-intake", json={
        "entities": [
            {
                "name": "太虚残剑",
                "category": "item",
                "content": by_name["太虚残剑"]["snippet"],
                "tags": by_name["太虚残剑"]["suggested_tags"]
            },
            {
                "name": "天衍阁",
                "category": "faction",
                "content": by_name["天衍阁"]["snippet"],
                "tags": by_name["太虚残剑"]["suggested_tags"]
            }
        ],
        "chapter_id": chapter_id
    })
    assert intake_res.status_code == 201
    intake_data = intake_res.json()
    assert intake_data["added_count"] == 2

    # 4. 验证实体已入库，并且自动关联了当前章节
    ch_ents = client.get(f"/api/chapters/{chapter_id}/entities").json()
    ch_ent_names = [e["name"] for e in ch_ents]
    assert "太虚残剑" in ch_ent_names
    assert "天衍阁" in ch_ent_names

    # 5. 再次探测，已入库的 '太虚残剑' 和 '天衍阁' 应当不再出现
    detect_again = client.post(f"/api/works/{work_id}/entities/detect-unregistered", json={
        "content": chapter_content,
        "chapter_id": chapter_id
    }).json()
    again_names = [item["name"] for item in detect_again["unregistered"]]
    assert "太虚残剑" not in again_names
    assert "天衍阁" not in again_names
    assert "青云古殿" in again_names
