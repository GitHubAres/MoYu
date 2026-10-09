# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""导入导出与整库备份 API。"""
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..db import DATA_DIR, DB_PATH, get_db, word_count
from ..exporter import EXPORT_DIR, chapters_for_scope, export_docx, export_epub, export_txt

router = APIRouter(tags=["io"])

IMPORT_DIR = DATA_DIR / "imports"

_SCOPE_LABEL = {"all": "全书", "volumes": "按卷", "chapters": "选章"}

# 行首章节/卷标题：第X章、第X卷、Chapter N 等
_HEAD_PAT = re.compile(
    r"^\s*(第[0-9零一二两三四五六七八九十百千万]+[章节卷回部篇][^\n]{0,38}|Chapter\s+\d+[^\n]{0,60})\s*$",
    re.IGNORECASE)


def _one(sql, args=()):
    row = get_db().execute(sql, args).fetchone()
    if row is None:
        raise HTTPException(404, "资源不存在")
    return dict(row)


def _record(eid: int) -> dict:
    row = _one(
        """SELECT e.*, w.title AS work_title FROM exports e
           LEFT JOIN works w ON w.id = e.work_id WHERE e.id=?""", (eid,))
    p = Path(row["path"]) if row["path"] else None
    row["size"] = p.stat().st_size if p and p.is_file() else 0
    row["error"] = (json.loads(row["scope"] or "{}")).get("error", "")
    return row


def _safe_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name)


def _run_export(eid: int, work: dict, fmt: str, payload: dict):
    """执行导出并回写 exports 行；失败置 status=failed 并把原因记入 scope JSON。"""
    db = get_db()
    try:
        tree = chapters_for_scope(db, work["id"], payload)
        if not tree:
            raise ValueError("所选范围内没有可导出的章节")
        ts = datetime.now().strftime("%Y%m%d-%H%M")
        name = _safe_name(f"{work['title']}_{_SCOPE_LABEL.get(payload.get('type'), '全书')}_{ts}.{fmt}")
        path = EXPORT_DIR / f"{eid}_{name}"
        options = payload.get("options") or {}
        if fmt == "txt":
            _, wc = export_txt(work, tree, options, path)
        elif fmt == "epub":
            _, wc = export_epub(work, tree, options, path)
        else:
            _, wc = export_docx(work, tree, options, path)
        payload.pop("error", None)
        db.execute("UPDATE exports SET name=?, path=?, status='done', word_count=?, scope=? WHERE id=?",
                   (name, str(path), wc, json.dumps(payload, ensure_ascii=False), eid))
    except Exception as e:
        payload["error"] = str(e)
        db.execute("UPDATE exports SET status='failed', scope=? WHERE id=?",
                   (json.dumps(payload, ensure_ascii=False), eid))
    db.commit()


# ---------- 导出 ----------

class ExportIn(BaseModel):
    work_id: int
    format: str = "txt"
    scope: dict = Field(default_factory=lambda: {"type": "all", "ids": []})
    options: dict = Field(default_factory=dict)


@router.post("/export", status_code=201)
def create_export(body: ExportIn):
    fmt = body.format.lower()
    if fmt not in ("txt", "docx", "epub"):
        raise HTTPException(400, "仅支持导出 TXT / DOCX / EPUB 格式")
    work = _one("SELECT * FROM works WHERE id=?", (body.work_id,))
    stype = body.scope.get("type", "all")
    if stype not in _SCOPE_LABEL:
        raise HTTPException(400, "导出范围 type 仅支持 all / volumes / chapters")
    payload = {"type": stype, "ids": body.scope.get("ids") or [], "options": body.options}
    db = get_db()
    cur = db.execute(
        "INSERT INTO exports(work_id, name, format, scope, status) VALUES (?,?,?,?,'running')",
        (body.work_id, "生成中…", fmt, json.dumps(payload, ensure_ascii=False)))
    db.commit()
    _run_export(cur.lastrowid, work, fmt, payload)
    return _record(cur.lastrowid)


@router.get("/exports")
def list_exports(work_id: int | None = None):
    db = get_db()
    if work_id:
        rows = db.execute(
            """SELECT e.*, w.title AS work_title FROM exports e
               LEFT JOIN works w ON w.id = e.work_id
               WHERE e.work_id=? ORDER BY e.id DESC""", (work_id,)).fetchall()
    else:
        rows = db.execute(
            """SELECT e.*, w.title AS work_title FROM exports e
               LEFT JOIN works w ON w.id = e.work_id ORDER BY e.id DESC""").fetchall()
    return [_record(r["id"]) for r in rows]


@router.get("/exports/{eid}/download")
def download_export(eid: int):
    row = _one("SELECT * FROM exports WHERE id=?", (eid,))
    p = Path(row["path"]) if row["path"] else None
    if not p or not p.is_file():
        raise HTTPException(404, "导出文件已不存在，请重试生成")
    return FileResponse(p, filename=row["name"])


@router.post("/exports/{eid}/retry")
def retry_export(eid: int):
    row = _one("SELECT * FROM exports WHERE id=?", (eid,))
    if not row["work_id"]:
        raise HTTPException(400, "原作品已删除，无法重试")
    work = _one("SELECT * FROM works WHERE id=?", (row["work_id"],))
    payload = json.loads(row["scope"] or "{}")
    _run_export(eid, work, row["format"], payload)
    return _record(eid)


@router.delete("/exports/{eid}", status_code=204)
def delete_export(eid: int):
    row = _one("SELECT * FROM exports WHERE id=?", (eid,))
    db = get_db()
    if row["path"]:
        p = Path(row["path"])
        if p.is_file() and p.parent == EXPORT_DIR:
            p.unlink()
    db.execute("DELETE FROM exports WHERE id=?", (eid,))
    db.commit()


# ---------- 导入 ----------

def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("无法识别文件编码（仅支持 UTF-8 / GB18030 编码的 TXT）")


def _read_docx(path: Path) -> str:
    from docx import Document
    try:
        doc = Document(str(path))
    except Exception:
        raise ValueError("DOCX 文件解析失败，文件可能已损坏或不是有效的 Word 文档")
    return "\n".join(p.text for p in doc.paragraphs)


def _split_sections(text: str, fallback_title: str) -> list[dict]:
    """按行首标题拆章；无任何匹配时整体一章。"""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    heads = [i for i, l in enumerate(lines) if _HEAD_PAT.match(l)]
    sections = []
    if not heads:
        body = text.strip()
        if not body:
            raise ValueError("文件内容为空，没有可导入的正文")
        return [{"title": fallback_title, "content": body}]
    pre = "\n".join(lines[:heads[0]]).strip()
    if pre:
        sections.append({"title": "开篇", "content": pre})
    for j, start in enumerate(heads):
        end = heads[j + 1] if j + 1 < len(heads) else len(lines)
        sections.append({
            "title": lines[start].strip(),
            "content": "\n".join(lines[start + 1:end]).strip(),
        })
    return sections


def _parse_import(path: Path, fallback_title: str) -> list[dict]:
    if path.suffix.lower() == ".docx":
        text = _read_docx(path)
    else:
        text = _decode(path.read_bytes())
    return _split_sections(text, fallback_title)


@router.post("/import/preview")
async def import_preview(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".txt", ".docx"):
        raise HTTPException(400, "仅支持导入 TXT / DOCX 文件")
    data = await file.read()
    if not data:
        raise HTTPException(400, "文件为空")
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    token = f"{int(time.time())}_{os.urandom(4).hex()}{ext}"
    path = IMPORT_DIR / token
    path.write_bytes(data)  # 失败也保留原文件，便于排查
    try:
        sections = _parse_import(path, Path(file.filename).stem)
    except ValueError as e:
        raise HTTPException(400, str(e))
    chapters = [
        {"id": i, "title": s["title"],
         "preview": s["content"].replace("\n", " ")[:80],
         "word_count": word_count(s["content"])}
        for i, s in enumerate(sections, 1)
    ]
    return {
        "file_token": token,
        "title": Path(file.filename).stem,
        "chapters": chapters,
        "total_words": sum(c["word_count"] for c in chapters),
    }


class ImportConfirmIn(BaseModel):
    file_token: str
    title: str
    chapter_ids: list[int] | None = None  # 为空表示全选


@router.post("/import/confirm", status_code=201)
def import_confirm(body: ImportConfirmIn):
    token = Path(body.file_token).name  # 防目录穿越
    path = IMPORT_DIR / token
    if not path.is_file():
        raise HTTPException(404, "暂存文件不存在或已过期，请重新上传")
    title = body.title.strip()
    if not title:
        raise HTTPException(400, "作品名不能为空")
    try:
        sections = _parse_import(path, title)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if body.chapter_ids:
        picked = [s for i, s in enumerate(sections, 1) if i in set(body.chapter_ids)]
    else:
        picked = sections
    if not picked:
        raise HTTPException(400, "未选择任何章节")
    db = get_db()
    cur = db.execute("INSERT INTO works(title) VALUES (?)", (title,))
    work_id = cur.lastrowid
    cur = db.execute("INSERT INTO volumes(work_id, title, sort_order) VALUES (?,?,1)", (work_id, "卷一"))
    vol_id = cur.lastrowid
    for i, s in enumerate(picked, 1):
        db.execute(
            "INSERT INTO chapters(volume_id, title, content, word_count, sort_order) VALUES (?,?,?,?,?)",
            (vol_id, s["title"][:80] or f"第{i}章", s["content"], word_count(s["content"]), i))
    db.commit()
    path.unlink(missing_ok=True)
    work = _one("SELECT * FROM works WHERE id=?", (work_id,))
    work["chapter_count"] = len(picked)
    return work


# ---------- 整库备份 ----------

@router.get("/settings/backup")
def backup_db():
    if not DB_PATH.is_file():
        raise HTTPException(404, "数据库文件不存在")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return FileResponse(DB_PATH, filename=f"moyu_backup_{ts}.db",
                        media_type="application/octet-stream")
