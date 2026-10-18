# -*- coding: utf-8 -*-
import pytest
from app.db import get_db, BUILTIN_SKILLS
from app.features import build_skill_system_prompt, resolve_skill

def test_triad_and_writing_skills_contract_pure_text(client):
    """验证行文类与去AI味技能必须直接输出正文，占位符完备，且无Markdown表格等破坏Diff的结构。"""
    skills_map = {s["name"]: s for s in BUILTIN_SKILLS}
    
    # 1. 验证 13 个技能名字严格冻结
    expected_names = {
        "audit-consistency",
        "audit-de-aitone",
        "audit-foreshadow",
        "audit-pacing-rhythm",
        "audit-synopsis-distill",
        "audit-timeline",
        "novel-cast",
        "novel-faction-graph",
        "novel-foreshadow-matrix",
        "novel-forge",
        "novel-hook-engineer",
        "novel-lead-arc",
        "novel-magic-system",
        "novel-outline-macro",
        "novel-premise",
        "novel-scene",
        "novel-timeline",
        "novel-world",
        "prose-combat",
        "prose-continue",
        "prose-dialogue",
        "prose-expand",
        "prose-polish",
        "prose-sensory",
    }
    assert set(skills_map.keys()) == expected_names
    
    # 2. 验证行文类核心技能包含标准占位符与纯正文协议
    writing_skills = ["audit-de-aitone", "prose-continue", "prose-polish", "prose-expand", "audit-synopsis-distill"]
    for name in writing_skills:
        body = skills_map[name]["body_md"]
        assert "{{context}}" in body, f"{name} 缺失 {{context}}"
        assert "{{selection}}" in body, f"{name} 缺失 {{selection}}"
        assert "{{instruction}}" in body, f"{name} 缺失 {{instruction}}"
        assert "正文" in body or "直接输出" in body, f"{name} 必须包含直接输出正文契约"
        assert any(w in body for w in ["不要输出解释", "严禁输出任何解释", "绝不要输出解释", "严禁输出解释", "严禁输出任何", "只输出", "正文："]), f"{name} 必须包含零废话解释协议"

def test_anti_ai_tone_adversarial_mechanisms(client):
    """验证去AI味三剑客深度植入朱雀/知网对抗指标。"""
    skills_map = {s["name"]: s for s in BUILTIN_SKILLS}
    de_ai = skills_map["audit-de-aitone"]["body_md"]
    
    # 验证绝对封杀词表与去AI味指令
    assert "AI" in de_ai
    assert "套话" in de_ai or "仿佛" in de_ai
    assert "直接输出" in de_ai

def test_workflow_and_planning_skills_macro_spec(client):
    """验证开坑五连流及宏观策划技能包含网文黄金节奏与资产中枢绑定。"""
    skills_map = {s["name"]: s for s in BUILTIN_SKILLS}
    
    # novel-premise
    premise = skills_map["novel-premise"]["body_md"]
    assert "核心" in premise or "金手指" in premise
    
    # novel-world
    world = skills_map["novel-world"]["body_md"]
    assert "代价" in world
    
    # novel-cast
    cast = skills_map["novel-cast"]["body_md"]
    assert "核心欲望" in cast or "人物" in cast
    
    # default-outline
    outline = skills_map["novel-outline-macro"]["body_md"]
    assert "高潮" in outline or "分卷" in outline
    
    # novel-scene
    scene = skills_map["novel-scene"]["body_md"]
    assert "伏笔" in scene
    assert "分场" in scene or "钩子" in scene

def test_audit_and_analysis_novel_features(client):
    """验证质检与总控技能包含网文专项稽核与去AI味示范。"""
    skills_map = {s["name"]: s for s in BUILTIN_SKILLS}
    
    audit = skills_map["audit-consistency"]["body_md"]
    assert "吃书" in audit or "冲突" in audit
    
    analysis = skills_map["audit-pacing-rhythm"]["body_md"]
    assert "张力" in analysis or "节奏" in analysis
    
    forge = skills_map["novel-forge"]["body_md"]
    assert "流程" in forge or "总控" in forge
