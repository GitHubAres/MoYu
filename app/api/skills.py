# -*- coding: utf-8 -*-
# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""Skill 市场后端 API：标准 Agent Skill 规范管理、资源挂载、导入导出与规范校验。"""

import io
import re
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional

import yaml
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..db import get_db

router = APIRouter(prefix="/skills", tags=["skills"])

# 规范常量
NAME_REGEX = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
RESOURCE_PREFIXES = ("scripts/", "references/", "assets/")
MAX_SINGLE_FILE_SIZE = 200 * 1024  # 200 KB
MAX_TOTAL_FILES_SIZE = 1024 * 1024  # 1 MB


def validate_skill_name(name: str):
    name = (name or "").strip()
    if not name or not NAME_REGEX.match(name):
        raise HTTPException(
            status_code=400,
            detail="Skill 名称不符合规范：必须全小写字母、数字或连字符开头，长度不超过 64 字符（正则：^[a-z0-9][a-z0-9-]{0,63}$）",
        )
    return name


def validate_resource_path(path: str) -> str:
    path = path.strip().replace("\\", "/").lstrip("/")
    if ".." in path.split("/") or path.startswith("/"):
        raise HTTPException(status_code=400, detail="非法资源文件路径：禁止目录穿越或绝对路径")
    if not any(path.startswith(prefix) for prefix in RESOURCE_PREFIXES):
        raise HTTPException(
            status_code=400,
            detail="资源路径必须位于 scripts/、references/ 或 assets/ 三大规范目录之一",
        )
    return path


def parse_skill_md_text(raw_text: str) -> tuple[dict, str]:
    """解析带有 YAML frontmatter 的 SKILL.md 文本，返回 (metadata_dict, body_text)。"""
    raw_text = raw_text.strip()
    if not raw_text.startswith("---"):
        return {}, raw_text
    parts = raw_text.split("---", 2)
    if len(parts) < 3:
        return {}, raw_text
    fm_str = parts[1]
    body = parts[2].lstrip("\r\n")
    try:
        data = yaml.safe_load(fm_str) or {}
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    return data, body


def dump_skill_md_text(name: str, description: str, body: str) -> str:
    """生成包含纯净 frontmatter (仅 name 与 description) 的 SKILL.md 字符串。"""
    fm_dict = {"name": name, "description": description}
    fm_yaml = yaml.dump(fm_dict, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{fm_yaml}\n---\n\n{body.lstrip()}"


class SkillCreate(BaseModel):
    name: str = Field(..., description="规范名称")
    title: str = Field(..., description="展示标题")
    description: str = Field(..., description="触发描述")
    body_md: str = Field("", description="SKILL.md 正文")
    version: str = Field("1.0.0", description="版本号")
    applies_to: str = Field("", description="适用任务类型")
    icon: str = Field("auto_awesome", description="图标")


class SkillUpdate(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    body_md: Optional[str] = None
    version: Optional[str] = None
    enabled: Optional[int] = None
    applies_to: Optional[str] = None
    icon: Optional[str] = None


class SkillFileCreate(BaseModel):
    content: str


@router.get("")
def list_skills(
    applies_to: Optional[str] = Query(None),
    enabled: Optional[int] = Query(None),
    source: Optional[str] = Query(None),
):
    """获取 Skill 列表，支持按任务类型、启停状态、来源过滤。"""
    conn = get_db()
    sql = """
        SELECT s.*,
            (SELECT COUNT(*) FROM skill_files f WHERE f.skill_id = s.id) AS files_count,
            (SELECT COALESCE(SUM(f.size), 0) FROM skill_files f WHERE f.skill_id = s.id) AS total_files_size
        FROM skills s
        WHERE 1=1
    """
    params = []
    if applies_to is not None:
        if applies_to == "":
            sql += " AND (s.applies_to = '' OR s.applies_to IS NULL)"
        else:
            sql += " AND (s.applies_to = ? OR s.applies_to = '' OR s.applies_to IS NULL)"
            params.append(applies_to)
    if enabled is not None:
        sql += " AND s.enabled = ?"
        params.append(enabled)
    if source is not None:
        sql += " AND s.source = ?"
        params.append(source)

    sql += " ORDER BY CASE s.source WHEN 'builtin' THEN 0 WHEN 'custom' THEN 1 ELSE 2 END, s.id ASC"
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@router.post("", status_code=201)
def create_skill(body: SkillCreate):
    """创建新 Skill。严格校验 name 与 description。"""
    name = validate_skill_name(body.name)
    desc = (body.description or "").strip()
    if not desc:
        raise HTTPException(status_code=400, detail="Skill 描述（description）不能为空，需阐述用途与触发时机")

    title = (body.title or "").strip() or name
    body_md = body.body_md or ""

    # 若 body_md 头部自带 frontmatter，提取并同步
    fm, clean_body = parse_skill_md_text(body_md)
    if fm:
        body_md = dump_skill_md_text(name, desc, clean_body)

    conn = get_db()
    existing = conn.execute("SELECT id FROM skills WHERE name = ?", (name,)).fetchone()
    if existing:
        raise HTTPException(status_code=400, detail=f"已存在同名 Skill: {name}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute(
        """
        INSERT INTO skills(name, title, description, body_md, version, enabled, applies_to, source, icon, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 1, ?, 'custom', ?, ?, ?)
        """,
        (name, title, desc, body_md, body.version or "1.0.0", body.applies_to or "", body.icon or "auto_awesome", now, now),
    )
    conn.commit()
    return get_skill_detail(cur.lastrowid)


@router.get("/{skill_id}")
def get_skill_detail(skill_id: int):
    """获取单个 Skill 详情及全部挂载资源文件。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM skills WHERE id = ?", (skill_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    skill_data = dict(row)

    files_rows = conn.execute(
        "SELECT id, path, size, updated_at FROM skill_files WHERE skill_id = ? ORDER BY path ASC",
        (skill_id,),
    ).fetchall()
    skill_data["files"] = [dict(f) for f in files_rows]
    return skill_data


@router.patch("/{skill_id}")
def update_skill(skill_id: int, body: SkillUpdate):
    """更新 Skill 元数据、启用状态或 SKILL.md 正文。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM skills WHERE id = ?", (skill_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Skill 不存在")

    updates = {}
    if body.name is not None:
        name = validate_skill_name(body.name)
        if name != row["name"]:
            exists = conn.execute("SELECT id FROM skills WHERE name = ? AND id != ?", (name, skill_id)).fetchone()
            if exists:
                raise HTTPException(status_code=400, detail=f"已存在同名 Skill: {name}")
            updates["name"] = name

    if body.title is not None:
        updates["title"] = body.title.strip()
    if body.description is not None:
        desc = body.description.strip()
        if not desc:
            raise HTTPException(status_code=400, detail="Skill 描述不可为空")
        updates["description"] = desc
    if body.version is not None:
        updates["version"] = body.version.strip()
    if body.enabled is not None:
        updates["enabled"] = 1 if body.enabled else 0
    if body.applies_to is not None:
        updates["applies_to"] = body.applies_to.strip()
    if body.icon is not None:
        updates["icon"] = body.icon.strip()
    if body.body_md is not None:
        updates["body_md"] = body.body_md

    if not updates:
        return get_skill_detail(skill_id)

    updates["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
    values = list(updates.values()) + [skill_id]

    conn.execute(f"UPDATE skills SET {set_clause} WHERE id = ?", values)
    conn.commit()
    return get_skill_detail(skill_id)


@router.delete("/{skill_id}", status_code=204)
def delete_skill(skill_id: int):
    """删除指定 Skill。内置 builtin Skill 禁止删除。"""
    conn = get_db()
    row = conn.execute("SELECT source FROM skills WHERE id = ?", (skill_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    if row["source"] == "builtin":
        raise HTTPException(status_code=403, detail="系统内置 Skill 禁止删除，可复制副本后进行修改")

    conn.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
    conn.commit()
    return None


@router.post("/{skill_id}/duplicate")
def duplicate_skill(skill_id: int):
    """复制副本。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM skills WHERE id = ?", (skill_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Skill 不存在")

    base_name = f"{row['name']}-copy"
    cand_name = base_name
    counter = 1
    while conn.execute("SELECT 1 FROM skills WHERE name = ?", (cand_name,)).fetchone():
        counter += 1
        cand_name = f"{base_name}-{counter}"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_title = f"{row['title']} (副本)"
    cur = conn.execute(
        """
        INSERT INTO skills(name, title, description, body_md, version, enabled, applies_to, source, icon, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 1, ?, 'custom', ?, ?, ?)
        """,
        (cand_name, new_title, row["description"], row["body_md"], row["version"], row["applies_to"], row["icon"], now, now),
    )
    new_id = cur.lastrowid

    # 复制关联文件
    files = conn.execute("SELECT path, content, size FROM skill_files WHERE skill_id = ?", (skill_id,)).fetchall()
    for f in files:
        conn.execute(
            """
            INSERT INTO skill_files(skill_id, path, content, size, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (new_id, f["path"], f["content"], f["size"], now),
        )
    conn.commit()
    return get_skill_detail(new_id)


# --- 资源文件操作 ---


@router.get("/{skill_id}/files/{path:path}")
def get_skill_file(skill_id: int, path: str):
    """获取资源文件详情与内容。"""
    valid_path = validate_resource_path(path)
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM skill_files WHERE skill_id = ? AND path = ?", (skill_id, valid_path)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="文件不存在")
    return dict(row)


@router.put("/{skill_id}/files/{path:path}")
def upsert_skill_file(skill_id: int, path: str, body: SkillFileCreate):
    """写入或更新单个挂载资源文件。"""
    valid_path = validate_resource_path(path)
    conn = get_db()
    skill = conn.execute("SELECT id FROM skills WHERE id = ?", (skill_id,)).fetchone()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")

    content_bytes = body.content.encode("utf-8")
    content_len = len(content_bytes)

    if content_len > MAX_SINGLE_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"单个资源文件大小超出上限（当前 {content_len / 1024:.1f}KB，最大允许 {MAX_SINGLE_FILE_SIZE / 1024:.0f}KB）",
        )

    # 检查总容量
    current_total_row = conn.execute(
        "SELECT COALESCE(SUM(size), 0) FROM skill_files WHERE skill_id = ? AND path != ?",
        (skill_id, valid_path),
    ).fetchone()
    current_total = current_total_row[0] if current_total_row else 0
    if current_total + content_len > MAX_TOTAL_FILES_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Skill 挂载资源总容量超出上限（最大允许 {MAX_TOTAL_FILES_SIZE / 1024 / 1024:.0f}MB）",
        )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """
        INSERT INTO skill_files(skill_id, path, content, size, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(skill_id, path) DO UPDATE SET
            content = excluded.content,
            size = excluded.size,
            updated_at = excluded.updated_at
        """,
        (skill_id, valid_path, body.content, content_len, now),
    )
    conn.commit()
    return {"ok": True, "path": valid_path, "size": content_len, "updated_at": now}


@router.delete("/{skill_id}/files/{path:path}", status_code=204)
def delete_skill_file(skill_id: int, path: str):
    """删除单个挂载文件。"""
    valid_path = validate_resource_path(path)
    conn = get_db()
    conn.execute("DELETE FROM skill_files WHERE skill_id = ? AND path = ?", (skill_id, valid_path))
    conn.commit()
    return None


# --- 校验、导出、导入 ---


@router.post("/{skill_id}/validate")
def validate_skill(skill_id: int):
    """对 Skill 执行规范契约校验，输出问题清单。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM skills WHERE id = ?", (skill_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Skill 不存在")

    issues = []

    # 1. 检查 name 命名
    name = row["name"]
    if not NAME_REGEX.match(name):
        issues.append({"level": "error", "message": f"名称「{name}」不符合命名规范（须符合 ^[a-z0-9][a-z0-9-]{{0,63}}$）"})

    # 2. 检查 description
    desc = (row["description"] or "").strip()
    if not desc:
        issues.append({"level": "error", "message": "description 描述为空"})
    elif len(desc) < 20:
        issues.append({"level": "warning", "message": "description 描述建议不低于 20 字，详细说明技能是什么及何时触发"})

    # 3. 检查 body_md
    body_md = row["body_md"] or ""
    lines = body_md.splitlines()
    if len(lines) > 500:
        issues.append({"level": "warning", "message": f"SKILL.md 正文行数达到 {len(lines)} 行（建议控制在 500 行以内）"})

    # 4. 检查资源文件
    files = conn.execute("SELECT path, size FROM skill_files WHERE skill_id = ?", (skill_id,)).fetchall()
    for f in files:
        fpath = f["path"]
        if not any(fpath.startswith(prefix) for prefix in RESOURCE_PREFIXES):
            issues.append({"level": "error", "message": f"资源文件「{fpath}」未位于 scripts/、references/ 或 assets/ 目录"})
        if "readme" in fpath.lower():
            issues.append({"level": "warning", "message": f"文件「{fpath}」：规范禁止在资源包中包含多余的 README 文档"})

    is_valid = not any(i["level"] == "error" for i in issues)
    return {"valid": is_valid, "issues": issues, "skill_name": name}


@router.get("/{skill_id}/export")
def export_skill(skill_id: int):
    """导出 Skill 为标准 .skill (zip) 包。包含 SKILL.md 与挂载文件。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM skills WHERE id = ?", (skill_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Skill 不存在")

    name = row["name"]
    desc = row["description"]
    body_md = row["body_md"]

    # 抽取纯正文，重建符合规范的 frontmatter (仅 name 与 description)
    _, clean_body = parse_skill_md_text(body_md)
    final_skill_md = dump_skill_md_text(name, desc, clean_body)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SKILL.md", final_skill_md)
        files = conn.execute("SELECT path, content FROM skill_files WHERE skill_id = ?", (skill_id,)).fetchall()
        for f in files:
            zf.writestr(f["path"], f["content"])

    buf.seek(0)
    filename = f"{name}.skill"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import")
async def import_skill(file: UploadFile = File(...)):
    """上传并导入 .skill（zip）文件。"""
    if not file.filename.endswith((".skill", ".zip")):
        raise HTTPException(status_code=400, detail="只允许导入 .skill 或 .zip 格式的技能包")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="技能安装包文件过大（上限 5MB）")

    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except Exception:
        raise HTTPException(status_code=400, detail="无法读取压缩包，文件已损坏或非有效 zip 格式")

    names = zf.namelist()
    # 查找根目录 SKILL.md
    skill_md_entry = None
    for n in names:
        if n == "SKILL.md" or n.endswith("/SKILL.md") and n.count("/") == 1:
            skill_md_entry = n
            break

    if not skill_md_entry:
        raise HTTPException(status_code=400, detail="技能包中未找到规范根文件 SKILL.md")

    raw_skill_md = zf.read(skill_md_entry).decode("utf-8", errors="replace")
    fm, clean_body = parse_skill_md_text(raw_skill_md)
    if not fm or not fm.get("name"):
        raise HTTPException(status_code=400, detail="SKILL.md 缺少有效的 YAML frontmatter 或未指定 name 字段")

    orig_name = str(fm["name"]).strip()
    if not NAME_REGEX.match(orig_name):
        raise HTTPException(status_code=400, detail=f"SKILL.md 中的 name「{orig_name}」不符合命名规范")

    desc = str(fm.get("description", "")).strip()
    if not desc:
        raise HTTPException(status_code=400, detail="SKILL.md 中的 description 描述不能为空")

    title = orig_name.replace("-", " ").title()
    prefix = skill_md_entry.rsplit("SKILL.md", 1)[0]  # 若在子目录下

    # 检查并处理 name 冲突
    conn = get_db()
    cand_name = orig_name
    if conn.execute("SELECT 1 FROM skills WHERE name = ?", (cand_name,)).fetchone():
        cand_name = f"{orig_name}-imported"
        counter = 1
        while conn.execute("SELECT 1 FROM skills WHERE name = ?", (cand_name,)).fetchone():
            counter += 1
            cand_name = f"{orig_name}-imported-{counter}"

    final_body_md = dump_skill_md_text(cand_name, desc, clean_body)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur = conn.execute(
        """
        INSERT INTO skills(name, title, description, body_md, version, enabled, applies_to, source, icon, created_at, updated_at)
        VALUES (?, ?, ?, ?, '1.0.0', 1, '', 'imported', 'auto_awesome', ?, ?)
        """,
        (cand_name, title, desc, final_body_md, now, now),
    )
    skill_id = cur.lastrowid

    # 提取符合白名单的挂载资源
    total_files_size = 0
    for n in names:
        if n == skill_md_entry or n.endswith("/"):
            continue
        rel_path = n[len(prefix):] if prefix and n.startswith(prefix) else n
        rel_path = rel_path.replace("\\", "/").lstrip("/")

        # 白名单过滤
        if ".." in rel_path.split("/") or rel_path.startswith("/"):
            continue
        if not any(rel_path.startswith(p) for p in RESOURCE_PREFIXES):
            continue

        file_bytes = zf.read(n)
        file_len = len(file_bytes)
        if file_len > MAX_SINGLE_FILE_SIZE or (total_files_size + file_len) > MAX_TOTAL_FILES_SIZE:
            continue

        file_str = file_bytes.decode("utf-8", errors="replace")
        total_files_size += file_len

        conn.execute(
            """
            INSERT INTO skill_files(skill_id, path, content, size, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (skill_id, rel_path, file_str, file_len, now),
        )

    conn.commit()
    return get_skill_detail(skill_id)