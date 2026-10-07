# -*- coding: utf-8 -*-
# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""Agent Skills 市场自动化验收测试套件：
- 覆盖数据层迁移与幂等性
- 规范 CRUD 与内置 Skill 保护
- 挂载资源白名单与容量拦截
- 规范契约校验（Validate）
- .skill 导入导出与安全性往返
- AI 提示词装配、死占位符修复与参考文档内联
"""

import io
import zipfile
import pytest
from fastapi import HTTPException
from app.db import get_db, migrate_and_seed_skills
from app.features import build_skill_system_prompt


def test_skills_seed_and_builtin_protection(client):
    """验证系统内置 6 项 Agent Skill 自动播种就绪，且受到保护不可删除。"""
    res = client.get("/api/skills")
    assert res.status_code == 200
    skills = res.json()
    builtins = [s for s in skills if s["source"] == "builtin"]
    assert len(builtins) >= 6

    names = {s["name"] for s in builtins}
    expected = {
        "default-continue", "default-expand", "default-shorten",
        "default-rewrite", "default-outline", "default-audit"
    }
    assert expected.issubset(names)

    # 尝试删除内置 Skill 必须被 403 拦截
    target = builtins[0]
    del_res = client.delete(f"/api/skills/{target['id']}")
    assert del_res.status_code == 403
    assert "内置" in del_res.json()["detail"]


def test_skills_crud_and_validation(client):
    """测试规范新建、非法命名校验、description 必填校验与 PATCH 启停。"""
    # 1. 规范名合法校验：全小写字母、连字符
    bad_res1 = client.post("/api/skills", json={
        "name": "Invalid_Skill_Name",
        "title": "测试大写与下划线",
        "description": "这是一段详细描述"
    })
    assert bad_res1.status_code == 400
    assert "规范" in bad_res1.json()["detail"]

    # 2. description 描述不可为空
    bad_res2 = client.post("/api/skills", json={
        "name": "valid-name",
        "title": "合法名称",
        "description": ""
    })
    assert bad_res2.status_code == 400

    # 3. 正常创建
    create_res = client.post("/api/skills", json={
        "name": "wuxia-combat",
        "title": "武侠打斗精修",
        "description": "专精于高武武侠打斗场景动作拆解、气机感应与节奏反转，适合场景高潮打斗时触发。",
        "body_md": "【招式推演】\n{{selection}}\n\n要求：强化动宾搭配与兵刃鸣响。",
        "applies_to": "expand",
        "icon": "swords"
    })
    assert create_res.status_code == 201
    skill = create_res.json()
    assert skill["name"] == "wuxia-combat"
    assert skill["source"] == "custom"
    assert skill["enabled"] == 1

    # 4. PATCH 更新与停用
    patch_res = client.patch(f"/api/skills/{skill['id']}", json={
        "title": "武侠格斗与气机精修",
        "enabled": 0
    })
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["title"] == "武侠格斗与气机精修"
    assert updated["enabled"] == 0

    # 5. 过滤查询
    list_disabled = client.get("/api/skills", params={"enabled": 0}).json()
    assert any(s["id"] == skill["id"] for s in list_disabled)

    # 6. 删除自定义 Skill
    del_res = client.delete(f"/api/skills/{skill['id']}")
    assert del_res.status_code == 204


def test_skills_duplicate(client):
    """测试创建副本（自动重命名与挂载文件同步继承）。"""
    create_res = client.post("/api/skills", json={
        "name": "orig-skill",
        "title": "原始技能",
        "description": "用于验证副本复制与文件继承机制的描述。",
        "body_md": "正文内容"
    })
    s_id = create_res.json()["id"]

    # 挂载一个参考文件
    client.put(f"/api/skills/{s_id}/files/references/style.txt", json={"content": "风格参考指南"})

    # 复制副本
    dup_res = client.post(f"/api/skills/{s_id}/duplicate")
    assert dup_res.status_code == 200
    dup = dup_res.json()
    assert dup["name"].startswith("orig-skill-copy")
    assert "副本" in dup["title"]
    assert dup["source"] == "custom"
    assert len(dup["files"]) == 1
    assert dup["files"][0]["path"] == "references/style.txt"

    # 清理
    client.delete(f"/api/skills/{s_id}")
    client.delete(f"/api/skills/{dup['id']}")


def test_skill_files_whitelist_and_size_limits(client):
    """挂载文件管理：严格白名单（scripts/、references/、assets/）、路径穿越拦截与尺寸限制。"""
    c = client.post("/api/skills", json={
        "name": "files-test-skill",
        "title": "文件测试",
        "description": "用于文件白名单拦截与容量测试的技能。"
    }).json()
    s_id = c["id"]

    # 1. 非法路径前缀拒绝
    bad_path1 = client.put(f"/api/skills/{s_id}/files/docs/readme.md", json={"content": "hello"})
    assert bad_path1.status_code == 400
    assert "三大规范目录" in bad_path1.json()["detail"]

    # 2. 路径穿越拒绝
    bad_path2 = client.put(f"/api/skills/{s_id}/files/references/../etc/passwd", json={"content": "hello"})
    assert bad_path2.status_code == 400

    # 3. 合法路径写入
    ok_res = client.put(f"/api/skills/{s_id}/files/references/world-lore.txt", json={"content": "修真九阶境界设定"})
    assert ok_res.status_code == 200
    assert ok_res.json()["size"] > 0

    # 读取文件
    get_file = client.get(f"/api/skills/{s_id}/files/references/world-lore.txt")
    assert get_file.status_code == 200
    assert get_file.json()["content"] == "修真九阶境界设定"

    # 4. 单文件超限拦截（> 200KB）
    huge_text = "A" * (205 * 1024)
    huge_res = client.put(f"/api/skills/{s_id}/files/references/huge.txt", json={"content": huge_text})
    assert huge_res.status_code == 400
    assert "上限" in huge_res.json()["detail"]

    # 5. 删除文件
    del_f = client.delete(f"/api/skills/{s_id}/files/references/world-lore.txt")
    assert del_f.status_code == 204
    assert client.get(f"/api/skills/{s_id}/files/references/world-lore.txt").status_code == 404

    client.delete(f"/api/skills/{s_id}")


def test_skill_contract_validation(client):
    """测试规范校验器接口：输出结构化诊断清单。"""
    c = client.post("/api/skills", json={
        "name": "val-check-skill",
        "title": "校验测试",
        "description": "短描述" # 少于 20 字，应触发 warning
    }).json()
    s_id = c["id"]

    val_res = client.post(f"/api/skills/{s_id}/validate")
    assert val_res.status_code == 200
    report = val_res.json()
    assert "issues" in report
    # 存在 description 字数建议告警
    warns = [i for i in report["issues"] if i["level"] == "warning"]
    assert any("20" in w["message"] for w in warns)

    client.delete(f"/api/skills/{s_id}")


def test_skill_export_and_import_roundtrip(client):
    """测试 .skill 标准 zip 包导出与导入往返完整性。"""
    c = client.post("/api/skills", json={
        "name": "export-demo",
        "title": "导出演示技能",
        "description": "一段标准且完整的技能触发描述，用于验证端到端打包与导入往返。",
        "body_md": "【剧情主干】\n{{context}}\n\n请输出推演正文。"
    }).json()
    s_id = c["id"]

    client.put(f"/api/skills/{s_id}/files/references/guide.md", json={"content": "# 参考指南\n详述分支。"})
    client.put(f"/api/skills/{s_id}/files/scripts/eval.py", json={"content": "print('eval logic')"})

    # 1. 导出 .skill
    export_res = client.get(f"/api/skills/{s_id}/export")
    assert export_res.status_code == 200
    assert export_res.headers["content-type"] == "application/zip"
    zip_bytes = export_res.content

    # 检验 zip 结构
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    names = zf.namelist()
    assert "SKILL.md" in names
    assert "references/guide.md" in names
    assert "scripts/eval.py" in names

    skill_md_content = zf.read("SKILL.md").decode("utf-8")
    assert "name: export-demo" in skill_md_content
    assert "description:" in skill_md_content

    # 2. 将导出的包导入（测试重名自动命名）
    files = {"file": ("export-demo.skill", zip_bytes, "application/zip")}
    import_res = client.post("/api/skills/import", files=files)
    assert import_res.status_code == 200
    imported = import_res.json()
    assert imported["name"] == "export-demo-imported"
    assert imported["source"] == "imported"
    assert len(imported["files"]) == 2

    # 清理
    client.delete(f"/api/skills/{s_id}")
    client.delete(f"/api/skills/{imported['id']}")


def test_build_skill_system_prompt_placeholders_and_inline(client):
    """核心 AI 集成测试：死占位符替换、references 内联与截断、scripts 仅列清单。"""
    # 建立测试 Skill
    c = client.post("/api/skills", json={
        "name": "inline-ai-test",
        "title": "AI 装配测试技能",
        "description": "测试占位符和资源内联装配逻辑的专用技能。",
        "body_md": "你是一位写作专家。\n\n【选区】\n{{selection}}\n\n【要求】\n{{instruction}}\n\n请直接输出结果。"
    }).json()
    s_id = c["id"]

    # 挂载参考文档与脚本
    client.put(f"/api/skills/{s_id}/files/references/bible.txt", json={"content": "这是设定宝典：九界归一。"})
    client.put(f"/api/skills/{s_id}/files/scripts/check.py", json={"content": "import sys"})
    client.put(f"/api/skills/{s_id}/files/assets/banner.png", json={"content": "fake-asset-bytes"})

    prompt_text, consumed = build_skill_system_prompt(
        skill_id=s_id,
        task="expand",
        context="前文五百年背景",
        selection="主角挥剑断江",
        instruction="突出剑气磅礴",
        length="short"
    )

    # 1. 验证占位符消费标记
    assert consumed["selection"] is True
    assert consumed["instruction"] is True
    assert consumed["context"] is False # 正文中未包含 {{context}}，未被静态消费

    # 2. 验证内容已嵌入 system prompt
    assert "主角挥剑断江" in prompt_text
    assert "突出剑气磅礴" in prompt_text

    # 3. 验证 references 被自动内联
    assert "【参考资源】" in prompt_text
    assert "这是设定宝典：九界归一" in prompt_text
    assert "references/bible.txt" in prompt_text

    # 4. 验证 scripts 与 assets 仅列清单
    assert "【附带资源清单】" in prompt_text
    assert "scripts/check.py" in prompt_text
    assert "assets/banner.png" in prompt_text
    assert "import sys" not in prompt_text # 脚本内容禁止内联

    # 5. 验证长度提示
    assert "100~200 字" in prompt_text

    client.delete(f"/api/skills/{s_id}")


def test_build_skill_fallback_and_disabled_error(client):
    """测试缺省兜底内置 Skill 与禁用 Skill 400 拦截。"""
    # 1. 不传 skill_id，默认走 continue 对应的 default-continue 内置 Skill
    prompt_text, _ = build_skill_system_prompt(skill_id=None, task="continue")
    assert "default-continue" in prompt_text

    # 2. 创建并禁用一个 Skill
    c = client.post("/api/skills", json={
        "name": "disabled-demo",
        "title": "禁用技能",
        "description": "将被禁用的测试技能。"
    }).json()
    s_id = c["id"]
    client.patch(f"/api/skills/{s_id}", json={"enabled": 0})

    # 调用被禁用的 Skill 必须抛出 HTTPException(400)
    with pytest.raises(HTTPException) as exc:
        build_skill_system_prompt(skill_id=s_id)
    assert exc.value.status_code == 400
    assert "已被禁用" in exc.value.detail

    client.delete(f"/api/skills/{s_id}")


def test_skill_migration_idempotent():
    """测试迁移函数幂等性：执行多次不报错、不重复插入。"""
    db = get_db()
    # 执行一次
    migrate_and_seed_skills(db)
    cnt1 = db.execute("SELECT COUNT(*) FROM skills").fetchone()[0]

    # 再次执行
    migrate_and_seed_skills(db)
    cnt2 = db.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
    assert cnt1 == cnt2

def test_length_hint_numeric_and_legacy():
    """v1.7.9：长度档位支持具体字数（如 "2000"），并兼容旧 short/medium/long 键。"""
    from app.features import AIOrchestrator
    assert "2000 字" in AIOrchestrator.length_hint("2000")
    assert "1500 字" in AIOrchestrator.length_hint("1500")
    assert "篇幅不上限" in AIOrchestrator.length_hint("unlimited")
    assert "篇幅不上限" in AIOrchestrator.length_hint("不上限")
    assert AIOrchestrator.length_hint("short") == AIOrchestrator.LENGTH_HINTS["short"]
    assert AIOrchestrator.length_hint("long") == AIOrchestrator.LENGTH_HINTS["long"]
    # 空值与非法值回退 medium
    assert AIOrchestrator.length_hint("") == AIOrchestrator.LENGTH_HINTS["medium"]
    assert AIOrchestrator.length_hint("abc") == AIOrchestrator.LENGTH_HINTS["medium"]


def test_numeric_length_in_prompt():
    """字数档位直接进入系统提示词的输出长度要求段。"""
    prompt_text, _ = build_skill_system_prompt(
        skill_id=None, task="continue", context="", selection="", instruction="", length="2000")
    assert "2000 字" in prompt_text


def test_builtin_skills_v1710(client):
    """v1.7.10：新增 default-analysis / de-ai-tone 内置技能，大纲与设定检查覆盖为方法论参考版。"""
    db = get_db()
    rows = {r["name"]: r for r in db.execute("SELECT * FROM skills WHERE source='builtin'")}
    assert "default-analysis" in rows
    assert rows["default-analysis"]["applies_to"] == "analysis"
    assert "de-ai-tone" in rows
    assert rows["de-ai-tone"]["applies_to"] == "rewrite"
    for name, ref in [
        ("default-outline", "references/structure-models.md"),
        ("default-audit", "references/consistency-taxonomy.md"),
        ("default-analysis", "references/analysis-rubric.md"),
        ("de-ai-tone", "references/ai-tone-catalog.md"),
    ]:
        f = db.execute(
            "SELECT content FROM skill_files WHERE skill_id=? AND path=?",
            (rows[name]["id"], ref),
        ).fetchone()
        assert f is not None, f"{name} 缺少挂载文件 {ref}"
        assert len(f["content"]) > 1000


def test_analyze_task_resolves_default_analysis(client):
    """analyze 任务不传 skill_id 时，经映射兜底命中 default-analysis 内置技能。"""
    prompt_text, _ = build_skill_system_prompt(skill_id=None, task="analyze")
    assert "default-analysis" in prompt_text
    assert "分析·十维体检" in prompt_text


def test_analysis_rubric_fully_inlined(client):
    """参考文档内联容量提升后，评分量表完整装载（尾部文本可见、无截断标记）。"""
    prompt_text, _ = build_skill_system_prompt(skill_id=None, task="analyze")
    assert "references/analysis-rubric.md" in prompt_text
    assert "用户要的是判断，不是过程" in prompt_text
    assert "[内容过长已截断]" not in prompt_text
