import pytest
from app.db import get_db, init_db
from app.features import build_skill_system_prompt, get_top_hot_genres
from app.services.asset_hub import record_hot_topic_asset
from app.services.context_service import assemble_hotradar_summary_block, assemble_workflow_context
from app.api.workflows import StepIn, _validate_steps


def test_m5_to_outline_draft_preview_only(client):
    """验证 M5: /api/hotradar/to-outline 仅生成草稿预览供用户二次确认，绝不静默写入 works 表"""
    db = get_db()
    # 插入模拟热点
    cur = db.execute(
        "INSERT INTO hot_topics (platform, title, rank, genre_tags, heat, author) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("起点", "大奉打更人测试", 1, '["仙侠", "探案", "搞笑"]', 999999, "卖报小郎君")
    )
    topic_id = cur.lastrowid
    db.commit()

    works_before = db.execute("SELECT COUNT(*) FROM works").fetchone()[0]

    # 请求生成草稿
    resp = client.post("/api/hotradar/to-outline", json={"topic_id": topic_id}, )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "draft" in data
    draft = data["draft"]
    assert draft["topic_id"] == topic_id
    assert "仙侠" in draft["genre"]
    assert "大奉打更人测试" in draft["reference_work"]
    assert "suggested_title" in draft
    assert "one_sentence_story" in draft

    # 验证红线 R3：数据库中绝无静默新增的作品
    works_after = db.execute("SELECT COUNT(*) FROM works").fetchone()[0]
    assert works_before == works_after


def test_m6_prompt_injection_conditional_safety():
    """验证 M6: AI 提示词注入条件式追加 TOP10 热门题材，对续写/正文任务零副作用"""
    db = get_db()
    # 填充热点
    db.execute("DELETE FROM hot_topics")
    db.execute("INSERT INTO hot_topics (platform, title, rank, genre_tags) VALUES (?, ?, ?, ?)", ("起点", "修真测试", 1, '["修真", "凡人流"]'))
    db.execute("INSERT INTO hot_topics (platform, title, rank, genre_tags) VALUES (?, ?, ?, ?)", ("番茄", "开局测试", 1, '["都市", "系统", "神豪"]'))
    db.commit()

    # 1. 验证 get_top_hot_genres 能提取出热门题材
    top_genres = get_top_hot_genres(5)
    assert len(top_genres) > 0
    assert any(g in ["修真", "凡人流", "都市", "系统", "神豪"] for g in top_genres)

    # 2. 纯续写任务（continue）：绝不包含热门题材注入，保证零副作用
    prompt_continue, _ = build_skill_system_prompt(
        skill_id=None,
        task="continue",
        context="天色渐晚，主角走入山林。",
        instruction="",
    )
    assert "当前全网热门题材 TOP10" not in prompt_continue

    # 3. 扩写/润色等正文任务：同样不包含
    prompt_expand, _ = build_skill_system_prompt(
        skill_id=None,
        task="expand",
        context="正文段落",
        instruction="扩写打斗场面",
    )
    assert "当前全网热门题材 TOP10" not in prompt_expand

    # 4. 涉及灵感/选题/立项/开坑/大纲/题材的任务：条件式追加
    prompt_ideation, _ = build_skill_system_prompt(
        skill_id=None,
        task="continue",
        context="新书构思",
        instruction="请帮我想几个热门题材的开坑立项灵感",
    )
    assert "当前全网热门题材 TOP10" in prompt_ideation


def test_m7_workflow_inspiration_collection_node(client):
    """验证 M7: 工作流「灵感采集」节点契约与运行时热点摘要装配"""
    db = get_db()
    # 1. 验证 StepIn 验证器支持 hotradar input_mode
    step = StepIn(
        title="灵感采集",
        input_mode="hotradar",
        instruction="分析当前全网热点并输出新书世界观设定",
    )
    _validate_steps(db, [step])

    # 2. 验证 assemble_hotradar_summary_block 装配有效文本
    summary = assemble_hotradar_summary_block(db)
    assert "全网热点雷达" in summary
    assert "热门榜单" in summary

    # 3. 验证 assemble_workflow_context 传入 input_mode="hotradar" 时装配热点
    ctx = assemble_workflow_context(
        db=db,
        work_id=1,
        input_mode="hotradar",
        context_sources=["hotradar"],
    )
    assert "全网热点雷达" in ctx


def test_m8_asset_hub_recording_and_contract(client):
    """验证 M8: 作者收藏热点经 asset_hub 沉淀为 MOYU:ASSETS 契约块"""
    db = get_db()
    # 创建模拟作品
    cur_w = db.execute("INSERT INTO works (title, genre, intro) VALUES ('测试流派作品', '科幻', '测试简介')")
    work_id = cur_w.lastrowid

    # 插入热点
    cur_t = db.execute(
        "INSERT INTO hot_topics (platform, title, rank, genre_tags, heat, author) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ('晋江', '穿成反派白月光', 1, '["穿书", "甜文", "仙侠"]', 88888, '晋江写手')
    )
    topic_id = cur_t.lastrowid
    db.commit()

    # 1. 测试 asset_hub.record_hot_topic_asset 生成标准契约块
    row = db.execute("SELECT * FROM hot_topics WHERE id = ?", (topic_id,)).fetchone()
    res = record_hot_topic_asset(db, work_id, dict(row))
    assert res["ok"] is True
    assert "<!-- MOYU:ASSETS" in res["contract_block"]
    assert "MOYU:ASSETS -->" in res["contract_block"]
    payload = res["contract_payload"]
    # 验证未涉及键留空数组 [] 契约
    for key in ["entities", "relations", "timeline_events", "foreshadows", "outline_nodes", "chapter_synopses"]:
        assert payload[key] == []
    assert len(payload["notes"]) == 1
    assert "【热点灵感】穿成反派白月光" in payload["notes"][0]["title"]

    # 2. 验证万相谱术语（category='lore'）已沉淀
    ent = db.execute("SELECT * FROM entities WHERE work_id = ? AND name = ?", (work_id, "【热点灵感】穿成反派白月光")).fetchone()
    assert ent is not None
    assert ent["category"] == "lore"

    # 3. 测试 /api/hotradar/collect 接口联动沉淀
    resp = client.post("/api/hotradar/collect", json={"topic_id": topic_id, "work_id": work_id})
    assert resp.status_code == 200
    collect_data = resp.json()
    assert collect_data["ok"] is True
    assert collect_data["collected"] is True
    assert collect_data["asset"] is not None
