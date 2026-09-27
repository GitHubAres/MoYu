"""作品导出引擎：按范围取章节并生成 TXT / DOCX 文件。"""
import re
from pathlib import Path

from docx import Document
from docx.shared import Pt

from .db import DATA_DIR, get_db, word_count

EXPORT_DIR = DATA_DIR / "exports"

_CHAPTER_PAT = re.compile(r"^第[0-9零一二两三四五六七八九十百千万]+[章节回]")
_CATEGORY_LABEL = {
    "character": "人物",
    "location": "地点",
    "item": "物品",
    "worldbuilding": "设定",
    "other": "其他",
}

_DIGITS = "零一二三四五六七八九"


def _cn_num(n: int) -> str:
    """1-9999 转中文数字（够章节序号用）。"""
    if n <= 10:
        return "十" if n == 10 else _DIGITS[n]
    if n < 20:
        return "十" + _DIGITS[n % 10]
    if n < 100:
        s = _DIGITS[n // 10] + "十"
        return s + (_DIGITS[n % 10] if n % 10 else "")
    if n < 1000:
        s = _DIGITS[n // 100] + "百"
        r = n % 100
        if r:
            s += ("零" if r < 10 else "") + _cn_num(r)
        return s
    s = _DIGITS[n // 1000] + "千"
    r = n % 1000
    if r:
        s += ("零" if r < 100 else "") + _cn_num(r)
    return s


def _fmt_title(title: str, options: dict, index: int) -> str:
    """章节标题规范化：已符合「第X章」样式的原样保留，否则补序号前缀。"""
    t = (title or "").strip() or f"第{_cn_num(index)}章"
    if options.get("format_titles") and not _CHAPTER_PAT.match(t):
        return f"第{_cn_num(index)}章 {t}"
    return t


def _paragraphs(content: str) -> list[str]:
    """正文拆段：去掉空行，保留原有段落顺序。"""
    return [p.strip() for p in (content or "").replace("\r\n", "\n").replace("\r", "\n").split("\n") if p.strip()]


def chapters_for_scope(db, work_id: int, scope: dict) -> list[tuple[str, list[dict]]]:
    """按导出范围返回有序 [(卷名, [章节行])]；scope = {"type": all|volumes|chapters, "ids": [...]}。"""
    scope = scope or {}
    stype = scope.get("type", "all")
    ids = [int(i) for i in (scope.get("ids") or [])]
    if stype == "volumes" and ids:
        marks = ",".join("?" * len(ids))
        vols = db.execute(
            f"SELECT * FROM volumes WHERE work_id=? AND id IN ({marks}) ORDER BY sort_order, id",
            [work_id, *ids]).fetchall()
    else:
        vols = db.execute(
            "SELECT * FROM volumes WHERE work_id=? ORDER BY sort_order, id", (work_id,)).fetchall()
    tree: list[tuple[str, list[dict]]] = []
    for v in vols:
        if stype == "chapters" and ids:
            marks = ",".join("?" * len(ids))
            chs = db.execute(
                f"SELECT * FROM chapters WHERE volume_id=? AND id IN ({marks}) ORDER BY sort_order, id",
                [v["id"], *ids]).fetchall()
        else:
            chs = db.execute(
                "SELECT * FROM chapters WHERE volume_id=? ORDER BY sort_order, id", (v["id"],)).fetchall()
        if chs:
            tree.append((v["title"], [dict(c) for c in chs]))
    return tree


def _entities_appendix(work_id: int) -> list[tuple[str, str, str]]:
    """文末附录素材：[(分类名, 名称, 简介)]。"""
    rows = get_db().execute(
        "SELECT category, name, content FROM entities WHERE work_id=? AND archived=0 ORDER BY category, id",
        (work_id,)).fetchall()
    return [(_CATEGORY_LABEL.get(r["category"], r["category"]), r["name"], (r["content"] or "").strip())
            for r in rows]


def export_txt(work: dict, tree: list[tuple[str, list[dict]]], options: dict, out_path: Path):
    """生成 TXT（UTF-8 无 BOM），返回 (文件路径, 字数)。"""
    lines = [f"《{work['title']}》"]
    if work.get("intro"):
        lines += ["", work["intro"].strip()]
    total = 0
    for vol_name, chs in tree:
        lines += ["", "", vol_name]
        for i, ch in enumerate(chs, 1):
            lines += ["", _fmt_title(ch["title"], options, i), ""]
            for para in _paragraphs(ch["content"]):
                lines.append(("　　" + para) if options.get("indent") else para)
            total += word_count(ch["content"])
    if options.get("append_entities"):
        appendix = _entities_appendix(work["id"])
        if appendix:
            lines += ["", "", "附录：设定简介", ""]
            for cat, name, content in appendix:
                lines.append(f"【{cat}】{name}")
                if content:
                    lines.append(content)
                lines.append("")
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return out_path, total


def export_docx(work: dict, tree: list[tuple[str, list[dict]]], options: dict, out_path: Path):
    """生成 DOCX（标题分级 + 正文段落 + 可选首行缩进），返回 (文件路径, 字数)。"""
    doc = Document()
    doc.add_heading(work["title"], level=0)
    if work.get("intro"):
        doc.add_paragraph(work["intro"].strip())
    total = 0
    for vol_name, chs in tree:
        doc.add_heading(vol_name, level=1)
        for i, ch in enumerate(chs, 1):
            doc.add_heading(_fmt_title(ch["title"], options, i), level=2)
            for para in _paragraphs(ch["content"]):
                p = doc.add_paragraph(para)
                if options.get("indent"):
                    p.paragraph_format.first_line_indent = Pt(24)
            total += word_count(ch["content"])
    if options.get("append_entities"):
        appendix = _entities_appendix(work["id"])
        if appendix:
            doc.add_heading("附录：设定简介", level=1)
            for cat, name, content in appendix:
                doc.add_heading(f"【{cat}】{name}", level=2)
                if content:
                    doc.add_paragraph(content)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return out_path, total
