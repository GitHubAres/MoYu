# -*- coding: utf-8 -*-
import pytest
from app.db import get_db, BUILTIN_SKILLS
from app.features import build_skill_system_prompt, resolve_skill

def test_triad_and_writing_skills_contract_pure_text(client):
    """验证行文类与去AI味技能必须直接输出正文，占位符完备，且无Markdown表格等破坏Diff的结构。"""
    skills_map = {s["name"]: s for s in BUILTIN_SKILLS}
    
    # 1. 验证 13 个技能名字严格冻结
    expected_names = {
        "default-continue", "default-expand", "default-shorten", "default-rewrite",
        "default-outline", "default-audit", "default-analysis", "novel-premise",
        "novel-world", "novel-cast", "novel-scene", "novel-forge", "de-ai-tone",
        "novel-timeline", "novel-foreshadow", "novel-magic-system", "prose-combat", "audit-timeline", "audit-foreshadow",
    }
    assert set(skills_map.keys()) == expected_names
    
    # 2. 验证行文类核心技能包含标准占位符与纯正文协议
    writing_skills = ["de-ai-tone", "default-continue", "default-rewrite", "default-expand", "default-shorten"]
    for name in writing_skills:
        body = skills_map[name]["body_md"]
        assert "{{context}}" in body, f"{name} 缺失 {{context}}"
        assert "{{selection}}" in body, f"{name} 缺失 {{selection}}"
        assert "{{instruction}}" in body, f"{name} 缺失 {{instruction}}"
        assert "直接输出" in body, f"{name} 必须包含直接输出正文契约"
        assert "不要输出解释" in body or "严禁输出任何解释" in body, f"{name} 必须包含零废话解释协议"

def test_anti_ai_tone_adversarial_mechanisms(client):
    """验证去AI味三剑客深度植入朱雀/知网对抗指标。"""
    skills_map = {s["name"]: s for s in BUILTIN_SKILLS}
    de_ai = skills_map["de-ai-tone"]["body_md"]
    
    # PPL、Burstiness、生理反射、零连词
    assert "困惑度" in de_ai or "PPL" in de_ai
    assert "Burstiness" in de_ai or "3-20-3" in de_ai
    assert "生理" in de_ai
    assert "零逻辑连词" in de_ai
    # 继承历史断言
    assert "校准三原则" in de_ai
    assert "操作模式" in de_ai
    assert "74/18/8" in de_ai

def test_workflow_and_planning_skills_macro_spec(client):
    """验证开坑五连流及宏观策划技能包含网文黄金节奏与资产中枢绑定。"""
    skills_map = {s["name"]: s for s in BUILTIN_SKILLS}
    
    # novel-premise
    premise = skills_map["novel-premise"]["body_md"]
    assert "黄金" in premise or "情绪价值" in premise
    
    # novel-world
    world = skills_map["novel-world"]["body_md"]
    assert "代价" in world
    
    # novel-cast
    cast = skills_map["novel-cast"]["body_md"]
    assert "即时欲望" in cast or "反派" in cast
    
    # default-outline
    outline = skills_map["default-outline"]["body_md"]
    assert "波峰" in outline or "高潮" in outline or "断章" in outline
    
    # novel-scene
    scene = skills_map["novel-scene"]["body_md"]
    assert "伏笔" in scene
    assert "出入点" in scene or "情绪" in scene

def test_audit_and_analysis_novel_features(client):
    """验证质检与总控技能包含网文专项稽核与去AI味示范。"""
    skills_map = {s["name"]: s for s in BUILTIN_SKILLS}
    
    audit = skills_map["default-audit"]["body_md"]
    assert "战力" in audit or "吃书" in audit
    
    analysis = skills_map["default-analysis"]["body_md"]
    assert "去AI味" in analysis or "示范" in analysis
    
    forge = skills_map["novel-forge"]["body_md"]
    assert "门禁" in forge
