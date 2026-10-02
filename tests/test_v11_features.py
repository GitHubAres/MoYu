# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）开发团队
# Licensed under the MIT License. See LICENSE.
"""v1.1 新增模块自动化测试：图谱、时间线、文风档案、AI任务与画廊。"""
import io
from conftest import make_work


# ---------- 关系图谱 (graph) ----------

def test_graph_relations_crud(client):
    w = make_work(client, "图谱测试作品")
    work_id = w["id"]

    # 创建两个实体
    r1 = client.post(f"/api/works/{work_id}/entities", json={
        "category": "character", "name": "师尊", "fields_json": {}, "tags": "修仙"
    })
    assert r1.status_code == 201
    e1_id = r1.json()["id"]

    r2 = client.post(f"/api/works/{work_id}/entities", json={
        "category": "character", "name": "徒弟", "fields_json": {}, "tags": "修仙"
    })
    assert r2.status_code == 201
    e2_id = r2.json()["id"]

    # 获取初始图谱
    g_res = client.get(f"/api/works/{work_id}/graph")
    assert g_res.status_code == 200
    graph = g_res.json()
    assert len(graph["nodes"]) >= 2
    assert len(graph["edges"]) == 0

    # 建立关系
    rel_res = client.post(f"/api/works/{work_id}/relations", json={
        "from_id": e1_id,
        "to_id": e2_id,
        "label": "师徒"
    })
    assert rel_res.status_code == 201
    rel = rel_res.json()
    assert rel["label"] == "师徒"
    rel_id = rel["id"]

    # 再次查询图谱，边出现
    g_res2 = client.get(f"/api/works/{work_id}/graph")
    assert g_res2.status_code == 200
    assert len(g_res2.json()["edges"]) == 1

    # 修改关系标签
    patch_res = client.patch(f"/api/relations/{rel_id}", json={"label": "宿敌"})
    assert patch_res.status_code == 200
    assert patch_res.json()["label"] == "宿敌"

    # 删除关系
    del_res = client.delete(f"/api/relations/{rel_id}")
    assert del_res.status_code == 204

    # 删除后再查
    g_res3 = client.get(f"/api/works/{work_id}/graph")
    assert len(g_res3.json()["edges"]) == 0


# ---------- 剧情时间线 (timeline) ----------

def test_timeline_crud_and_import(client):
    w = make_work(client, "时间线测试作品")
    work_id = w["id"]

    # 创建时间线事件
    ev_res = client.post(f"/api/works/{work_id}/timeline", json={
        "time_label": "太初元年",
        "event": "神剑降世",
        "characters": "主角,反派",
        "chapter_title": "第一章"
    })
    assert ev_res.status_code == 201
    event = ev_res.json()
    assert event["time_label"] == "太初元年"
    assert event["event"] == "神剑降世"
    event_id = event["id"]

    # 查看时间线列表
    t_res = client.get(f"/api/works/{work_id}/timeline")
    assert t_res.status_code == 200
    items = t_res.json()
    assert len(items) == 1
    assert items[0]["id"] == event_id

    # 修改事件
    patch_res = client.patch(f"/api/timeline/{event_id}", json={
        "time_label": "太初二年",
        "event": "神剑开锋"
    })
    assert patch_res.status_code == 200
    assert patch_res.json()["time_label"] == "太初二年"
    assert patch_res.json()["event"] == "神剑开锋"

    # 批量导入时间线
    import_res = client.post("/api/timeline/import", json={
        "work_id": work_id,
        "events": [
            {"time_label": "太初三年", "event": "宗门大比", "characters": "主角", "chapter_title": "第二章"},
            {"time_label": "太初四年", "event": "秘境探索", "characters": "主角,师姐", "chapter_title": "第三章"}
        ]
    })
    assert import_res.status_code == 201
    imported_events = import_res.json()
    assert isinstance(imported_events, list)
    assert len(imported_events) == 2

    # 校验总数
    t_res2 = client.get(f"/api/works/{work_id}/timeline")
    assert len(t_res2.json()) == 3

    # 删除首个事件
    del_res = client.delete(f"/api/timeline/{event_id}")
    assert del_res.status_code == 204
    t_res3 = client.get(f"/api/works/{work_id}/timeline")
    assert len(t_res3.json()) == 2


# ---------- 文风档案 (style) ----------

def test_style_profile_operations(client):
    w = make_work(client, "文风档案测试作品")
    work_id = w["id"]

    # 默认文风为空
    res = client.get(f"/api/works/{work_id}/style")
    assert res.status_code == 200
    assert res.json()["style_profile"] == ""

    # 更新文风
    put_res = client.put(f"/api/works/{work_id}/style", json={
        "style_profile": "冷峻克制，节奏紧凑，短句为主"
    })
    assert put_res.status_code == 200
    assert put_res.json()["style_profile"] == "冷峻克制，节奏紧凑，短句为主"

    # 再次查询确认持久化
    res2 = client.get(f"/api/works/{work_id}/style")
    assert res2.json()["style_profile"] == "冷峻克制，节奏紧凑，短句为主"

    # 清空文风
    del_res = client.delete(f"/api/works/{work_id}/style")
    assert del_res.status_code == 200
    assert del_res.json()["style_profile"] == ""


# ---------- AI 任务系统 (tasks) ----------

def test_tasks_lifecycle(client):
    from app.ai_tasks import create_task

    w = make_work(client, "任务系统测试作品")
    work_id = w["id"]

    task_id = create_task(work_id, "generate_image", "生成测试封面")
    assert task_id > 0

    # 获取单任务
    t_res = client.get(f"/api/tasks/{task_id}")
    assert t_res.status_code == 200
    task = t_res.json()
    assert task["status"] == "pending"
    assert task["task_type"] == "generate_image"

    # 取消任务
    cancel_res = client.post(f"/api/tasks/{task_id}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"

    # 重试任务
    retry_res = client.post(f"/api/tasks/{task_id}/retry")
    assert retry_res.status_code == 201
    new_task_id = retry_res.json()["id"]
    assert new_task_id != task_id

    # 列表筛选查询
    list_res = client.get(f"/api/tasks?work_id={work_id}")
    assert list_res.status_code == 200
    tasks_list = list_res.json()
    assert len(tasks_list) >= 2


# ---------- 丹青阁与封面 (gallery) ----------

def test_gallery_and_cover_upload(client):
    w = make_work(client, "画廊测试作品")
    work_id = w["id"]

    # 上传模拟图片作为封面
    fake_png = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4")
    upload_res = client.post(
        f"/api/works/{work_id}/cover-upload",
        files={"file": ("cover.png", io.BytesIO(fake_png), "image/png")}
    )
    assert upload_res.status_code == 200
    work_data = upload_res.json()
    assert work_data["cover_image"] != ""

    # 获取作品图片列表
    images_res = client.get(f"/api/works/{work_id}/images")
    assert images_res.status_code == 200
    images = images_res.json()
    assert len(images) >= 1
    cover_img = images[0]
    cover_id = cover_img["id"]

    # 查阅图片二进制文件
    file_res = client.get(f"/api/images/{cover_id}/file")
    assert file_res.status_code == 200
    assert file_res.headers["content-type"].startswith("image/")


# ---------- 炼丹炉底层生成与数据流 (alchemy) ----------

def test_alchemy_save_style_and_validation(client):
    w = make_work(client, "炼丹炉文风保存测试")
    wid = w["id"]

    # 非法作品保存文风被拒
    bad_res = client.post("/api/alchemy/save-style", json={"work_id": 99999, "style_profile": "测试文风"})
    assert bad_res.status_code == 404

    # 正常保存文风
    style_content = "·极简白描\n·冷峻克制\n·多用短句"
    res = client.post("/api/alchemy/save-style", json={"work_id": wid, "style_profile": style_content})
    assert res.status_code == 200
    assert res.json()["style_profile"] == style_content

    # 通过 style 路由确认已持久化
    get_res = client.get(f"/api/works/{wid}/style")
    assert get_res.json()["style_profile"] == style_content


def test_alchemy_import_lore_and_skip_duplicates(client):
    w = make_work(client, "资料融汇入库测试")
    wid = w["id"]

    lore_data = {
        "work_id": wid,
        "entities": [
            {"category": "character", "name": "苏白衣", "content": "极阴殿传承圣女", "tags": "魔道,冰系"},
            {"category": "place", "name": "断龙渊", "content": "上古禁地", "tags": "禁区"},
            {"category": "item", "name": "太乙玄晶", "content": "天阶灵矿", "tags": "灵材"},
        ],
        "outline": [
            {"title": "第一卷 龙潜渊底", "synopsis": "卷一总述", "parent": None},
            {"title": "第一章 踏入绝境", "synopsis": "主角初入断龙渊", "parent": "第一卷 龙潜渊底"},
        ]
    }

    # 首次入库
    res = client.post("/api/alchemy/import-lore", json=lore_data)
    assert res.status_code == 200
    data = res.json()
    assert data["created"]["entities"] == 3
    assert data["created"]["outline"] == 2
    assert data["skipped"] == 0

    # 再次入库相同设定，应当自动跳过重复条目
    res2 = client.post("/api/alchemy/import-lore", json={
        "work_id": wid,
        "entities": [
            {"category": "character", "name": "苏白衣", "content": "重复的条目"},
            {"category": "place", "name": "断龙渊", "content": "重复的条目"},
            {"category": "character", "name": "叶临渊", "content": "新角色"},
        ],
        "outline": []
    })
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["created"]["entities"] == 1
    assert data2["skipped"] == 2

    # 查询实体库验证存在性
    ents = client.get(f"/api/works/{wid}/entities").json()
    names = {e["name"] for e in ents}
    assert "苏白衣" in names and "断龙渊" in names and "太乙玄晶" in names and "叶临渊" in names


def test_alchemy_complete_new_work(client):
    brew_payload = {
        "mode": "new",
        "title": "太虚证道录",
        "brew": {
            "framework": {
                "title_suggestions": ["太虚证道录", "剑破苍穹"],
                "genre": "东方玄幻",
                "one_sentence_logline": "少年执断剑，叩问长生路",
                "core_selling_points": ["杀伐果断", "智商在线"]
            },
            "world": {
                "worldview_overview": "九天十地，万族林立",
                "power_system": "练气、筑基、金丹、元婴",
                "factions": [{"name": "青云剑宗", "type": "正道宗门", "description": "东荒第一剑宗"}],
                "locations": [{"name": "试炼古洞", "type": "秘境", "description": "宗门历练之所"}],
                "terms": [{"name": "洗髓丹", "description": "脱胎换骨之神药"}]
            },
            "characters": {
                "characters": [
                    {
                        "name": "林惊羽",
                        "role": "主角",
                        "identity": "弃徒",
                        "personality": "坚韧不拔",
                        "background": "身负绝脉",
                        "goal": "重铸剑心",
                        "ability": "太阴炼神诀"
                    }
                ]
            },
            "outline": {
                "volumes": [
                    {
                        "title": "第一卷 荒原潜龙",
                        "synopsis": "少年出大荒",
                        "chapters": [
                            {"title": "第一章 破晓之剑", "synopsis": "试炼开端"},
                            {"title": "第二章 异兽夜袭", "synopsis": "危机爆发"}
                        ]
                    }
                ]
            }
        }
    }

    res = client.post("/api/alchemy/complete", json=brew_payload)
    assert res.status_code == 201
    ret = res.json()
    work_id = ret["work_id"]
    assert work_id > 0
    assert ret["created"]["entities"] >= 4
    assert ret["created"]["outline"] == 3  # 1 volume + 2 chapters

    # 验证新作品基本属性
    w = client.get(f"/api/works/{work_id}").json()
    assert w["title"] == "太虚证道录"
    assert w["genre"] == "东方玄幻"
    assert "少年执断剑" in w["intro"]

    # 验证实体入库与结构化属性
    ents = client.get(f"/api/works/{work_id}/entities").json()
    char = next(e for e in ents if e["name"] == "林惊羽")
    assert char["category"] == "character"
    assert char["fields"]["性格"] == "坚韧不拔"
    assert char["fields"]["核心能力"] == "太阴炼神诀"

    # 验证大纲树已成功落鼎
    outline = client.get(f"/api/works/{work_id}/outline").json()
    assert len(outline) == 1
    assert outline[0]["title"] == "第一卷 荒原潜龙"
    assert len(outline[0]["children"]) == 2
    assert outline[0]["children"][0]["title"] == "第一章 破晓之剑"


def test_alchemy_complete_existing_work(client):
    w = make_work(client, "落鼎填充现有作品")
    wid = w["id"]

    res = client.post("/api/alchemy/complete", json={
        "mode": "existing",
        "work_id": wid,
        "brew": {
            "world": {
                "factions": [{"name": "暗影楼", "type": "杀手势力", "description": "刺杀组织"}]
            }
        }
    })
    assert res.status_code == 201
    assert res.json()["work_id"] == wid
    ents = client.get(f"/api/works/{wid}/entities").json()
    assert any(e["name"] == "暗影楼" for e in ents)


def test_alchemy_api_validations(client):
    # 非法 step 被拒
    r = client.post("/api/alchemy/brew", json={"step": "invalid_step"})
    assert r.status_code == 400

    # 缺少 work_id 或 file_token 拆解被拒
    r2 = client.post("/api/alchemy/analyze", json={})
    assert r2.status_code == 400

    # 不存在的 file_token 提取被拒
    r3 = client.post("/api/alchemy/extract-lore", json={"file_token": "non_existent.txt"})
    assert r3.status_code == 404

def test_alchemy_async_tasks_lifecycle(client):
    from app.ai_tasks import get_task, finish_task
    w = make_work(client, "异步炼丹测试作品")
    work_id = w["id"]

    # 1. 拆书蒸馏异步模式触发
    res = client.post("/api/alchemy/analyze?async_mode=true", json={"work_id": work_id})
    assert res.status_code == 200
    data = res.json()
    assert "task_id" in data
    assert data["status"] == "pending"
    task_id = data["task_id"]

    # 检查任务是否在台账中
    task_record = get_task(task_id)
    assert task_record["task_type"] == "alchemy_analyze"

    # 2. 开炉推演异步模式触发
    brew_res = client.post("/api/alchemy/brew?async_mode=true", json={
        "step": "framework",
        "instruction": "东方玄幻",
        "context": ""
    })
    assert brew_res.status_code == 200
    brew_data = brew_res.json()
    assert "task_id" in brew_data
    brew_task_id = brew_data["task_id"]
    brew_record = get_task(brew_task_id)
    assert brew_record["task_type"] == "alchemy_brew"

