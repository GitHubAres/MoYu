# -*- coding: utf-8 -*-
"""P2 上下文统一回归测试

验证划词 generate 与修撰使 chat 在同一章节下由后端组装上下文的一致性，
以及章节上下文预览端点 (/api/chapters/{chapter_id}/context/preview) 正确装配
正文、前情摘要、大纲三位一体卡片、万相谱实体档案与文风档案。
"""
from app.db import get_db
from app.services.context_service import assemble_writing_context
from tests.conftest import make_work, make_volume, make_chapter


def test_assemble_writing_context_components(client):
    """测试 assemble_writing_context 各组件的装配逻辑与内容完整性。"""
    # 1. 创建作品并设置文风档案
    w = make_work(client, "剑试天涯", intro="修仙长篇测试")
    work_id = w["id"]

    db = get_db()
    db.execute("UPDATE works SET style_profile = '语言苍凉凝练，多用白描短句' WHERE id = ?", (work_id,))
    db.commit()

    # 2. 创建卷和两章（前一章与当前章）
    v = make_volume(client, work_id, "第一卷 风起青萍")
    vol_id = v["id"]

    c1 = make_chapter(client, vol_id, "第一章 破庙避雨")
    c1_id = c1["id"]
    client.patch(f"/api/chapters/{c1_id}", json={
        "content": "大雨瓢泼，破庙残破不堪。少年萧云裹紧湿透的蓑衣，缩在篝火旁。"
    })

    c2 = make_chapter(client, vol_id, "第二章 夜半剑鸣")
    c2_id = c2["id"]
    client.patch(f"/api/chapters/{c2_id}", json={
        "content": "夜深人静，破庙外的风雨声愈发狂暴，腰间的断剑忽然发出龙吟之声。"
    })

    # 3. 创建大纲节点并绑定当前章
    node_res = client.post(f"/api/works/{work_id}/outline", json={
        "title": "第二章剧情节点",
        "synopsis": "断剑共鸣，揭开上古太虚宗秘辛",
    })
    assert node_res.status_code == 201
    node_id = node_res.json()["id"]
    link_res = client.post(f"/api/outline/{node_id}/link-chapter", json={"chapter_id": c2_id})
    assert link_res.status_code == 200

    # 为大纲节点挂接时间线事件与伏笔
    client.post(f"/api/works/{work_id}/timeline", json={
        "time_label": "建安三年·秋",
        "event": "太虚断剑首次震鸣",
        "characters": "萧云",
        "outline_node_id": node_id,
    })
    client.post(f"/api/works/{work_id}/foreshadows", json={
        "title": "断剑暗纹",
        "content": "剑鞘隐现北斗七星纹路",
        "status": "planted",
        "outline_node_id": node_id,
    })

    # 4. 创建万相谱实体设定条目 (合法 category 为 character)
    e_res = client.post(f"/api/works/{work_id}/entities", json={
        "name": "萧云",
        "category": "character",
        "fields_json": {"身份": "落魄少年", "修为": "练气三层"},
        "tags": "主角,少年,剑修",
    })
    assert e_res.status_code == 201
    entity_id = e_res.json()["id"]
    client.patch(f"/api/entities/{entity_id}", json={
        "content": "自幼孤苦无依，身负神秘玉佩。"
    })

    # 5. 调用 preview 接口验证装配结果
    prev_res = client.post(f"/api/chapters/{c2_id}/context/preview", json={
        "entity_ids": [entity_id],
        "include_current_chapter": True,
        "include_prev_chapter": True,
        "include_outline": True,
        "include_style": True,
    })
    assert prev_res.status_code == 200
    data = prev_res.json()
    ctx_text = data["context"]
    assert "【当前章节（前 3000 字）】" in ctx_text
    assert "腰间的断剑忽然发出龙吟之声" in ctx_text
    assert "【前情摘要（上一章末 500 字）】" in ctx_text
    assert "少年萧云裹紧湿透的蓑衣" in ctx_text
    assert "【目标大纲节点】" in ctx_text
    assert "第二章剧情节点" in ctx_text
    assert "断剑共鸣，揭开上古太虚宗秘辛" in ctx_text
    assert "【设定·character】萧云" in ctx_text
    assert "身份: 落魄少年" in ctx_text
    assert "【文风档案】" in ctx_text
    assert "语言苍凉凝练，多用白描短句" in ctx_text

    # 6. 直接验证 context_service.assemble_writing_context 返回内容一致性
    service_ctx = assemble_writing_context(
        db=get_db(),
        work_id=work_id,
        chapter_id=c2_id,
        entity_ids=[entity_id],
        include_current_chapter=True,
        include_prev_chapter=True,
        include_outline=True,
        include_style=True,
    )
    assert service_ctx == ctx_text


def test_chat_and_generate_context_consistency(client):
    """验证 chat 与 generate 链路接收相同实体勾选和开关时装配逻辑一致。"""
    w = make_work(client, "太虚行", intro="一致性验证作品")
    work_id = w["id"]

    v = make_volume(client, work_id, "卷一")
    vol_id = v["id"]

    c = make_chapter(client, vol_id, "序章")
    chap_id = c["id"]
    client.patch(f"/api/chapters/{chap_id}", json={
        "content": "青石板街上水洼倒映着月光。"
    })

    # 合法 category: character, place, faction, item, term, custom
    e_res = client.post(f"/api/works/{work_id}/entities", json={
        "name": "青石古道",
        "category": "place",
    })
    assert e_res.status_code == 201
    entity_id = e_res.json()["id"]
    client.patch(f"/api/entities/{entity_id}", json={
        "content": "贯穿全城的主干道，年久失修。"
    })

    # 预览装配
    prev_res = client.post(f"/api/chapters/{chap_id}/context/preview", json={
        "entity_ids": [entity_id],
        "include_current_chapter": True,
        "include_prev_chapter": False,
        "include_outline": False,
        "include_style": False,
    })
    assert prev_res.status_code == 200
    expected_ctx = prev_res.json()["context"]
    assert "【当前章节（前 3000 字）】" in expected_ctx
    assert "【设定·place】青石古道" in expected_ctx
