# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""设定人物库 API：分类条目 CRUD、归档、章节关联。"""
import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_db

router = APIRouter(tags=["entities"])

CATEGORIES = ("character", "place", "faction", "item", "term", "custom")


def _one(sql, args=()):
    row = get_db().execute(sql, args).fetchone()
    if row is None:
        raise HTTPException(404, "资源不存在")
    return dict(row)


def _all(sql, args=()):
    return [dict(r) for r in get_db().execute(sql, args).fetchall()]


def _serialize(e: dict) -> dict:
    """fields_json 解析为 fields 对象，并附带关联关系。"""
    try:
        e["fields"] = json.loads(e.get("fields_json") or "{}")
    except (ValueError, TypeError):
        e["fields"] = {}
    if "id" in e:
        db = get_db()
        rels = db.execute(
            """SELECT r.id, r.from_id, r.to_id, r.label, e2.name AS to_name, e2.category AS to_category
               FROM entity_relations r
               JOIN entities e2 ON e2.id = r.to_id
               WHERE r.from_id=? ORDER BY r.id ASC""",
            (e["id"],)
        ).fetchall()
        e["relations"] = [dict(r) for r in rels]
    else:
        e["relations"] = []
    return e


def _sync_relations(db, work_id: int, from_id: int, relations: list[dict] | None):
    if relations is None:
        return
    db.execute("DELETE FROM entity_relations WHERE work_id=? AND from_id=?", (work_id, from_id))
    for rel in relations:
        to_id = rel.get("to_id")
        label = (rel.get("label") or "").strip()
        if not to_id or to_id == from_id:
            continue
        target = db.execute("SELECT id FROM entities WHERE id=? AND work_id=?", (to_id, work_id)).fetchone()
        if not target:
            continue
        db.execute(
            "INSERT INTO entity_relations (work_id, from_id, to_id, label) VALUES (?, ?, ?, ?)",
            (work_id, from_id, to_id, label)
        )


def _check_category(category: str):
    if category not in CATEGORIES:
        raise HTTPException(400, f"category 仅支持 {'/'.join(CATEGORIES)}")


# ---------- 条目 ----------

@router.get("/works/{work_id}/entities")
def list_entities(work_id: int, category: str = "", q: str = "", archived: int = 0):
    _one("SELECT id FROM works WHERE id=?", (work_id,))
    sql = "SELECT * FROM entities WHERE work_id=? AND archived=?"
    args: list = [work_id, 1 if archived else 0]
    if category:
        _check_category(category)
        sql += " AND category=?"
        args.append(category)
    if q:
        sql += " AND (name LIKE ? OR tags LIKE ? OR content LIKE ?)"
        args += [f"%{q}%"] * 3
    sql += " ORDER BY updated_at DESC, id DESC"
    return [_serialize(e) for e in _all(sql, args)]


class EntityIn(BaseModel):
    category: str = "character"
    name: str
    content: str = ""
    fields_json: dict = {}
    tags: str = ""
    relations: list[dict] | None = None


@router.post("/works/{work_id}/entities", status_code=201)
def create_entity(work_id: int, body: EntityIn):
    _one("SELECT id FROM works WHERE id=?", (work_id,))
    _check_category(body.category)
    db = get_db()
    cur = db.execute(
        "INSERT INTO entities(work_id, category, name, content, fields_json, tags) VALUES (?,?,?,?,?,?)",
        (work_id, body.category, body.name, body.content,
         json.dumps(body.fields_json, ensure_ascii=False), body.tags))
    entity_id = cur.lastrowid
    _sync_relations(db, work_id, entity_id, body.relations)
    db.execute("UPDATE works SET updated_at=datetime('now','localtime') WHERE id=?", (work_id,))
    db.commit()
    return _serialize(_one("SELECT * FROM entities WHERE id=?", (entity_id,)))


@router.get("/entities/{entity_id}")
def get_entity(entity_id: int):
    return _serialize(_one("SELECT * FROM entities WHERE id=?", (entity_id,)))


class EntityPatch(BaseModel):
    category: str | None = None
    name: str | None = None
    content: str | None = None
    fields_json: dict | None = None
    tags: str | None = None
    relations: list[dict] | None = None


@router.patch("/entities/{entity_id}")
def update_entity(entity_id: int, body: EntityPatch):
    old = _one("SELECT * FROM entities WHERE id=?", (entity_id,))
    data = body.model_dump(exclude_unset=True)
    if "category" in data and data["category"] is not None:
        _check_category(data["category"])
    db = get_db()
    for k in ("category", "name", "content", "tags"):
        if data.get(k) is not None:
            db.execute(f"UPDATE entities SET {k}=? WHERE id=?", (data[k], entity_id))
    if data.get("fields_json") is not None:
        db.execute("UPDATE entities SET fields_json=? WHERE id=?",
                   (json.dumps(data["fields_json"], ensure_ascii=False), entity_id))
    if "relations" in data:
        _sync_relations(db, old["work_id"], entity_id, data["relations"])
    db.execute("UPDATE entities SET updated_at=datetime('now','localtime') WHERE id=?", (entity_id,))
    db.commit()
    return _serialize(_one("SELECT * FROM entities WHERE id=?", (entity_id,)))


@router.delete("/entities/{entity_id}", status_code=204)
def delete_entity(entity_id: int):
    _one("SELECT id FROM entities WHERE id=?", (entity_id,))
    db = get_db()
    db.execute("DELETE FROM entities WHERE id=?", (entity_id,))
    db.commit()


@router.post("/entities/{entity_id}/archive")
def toggle_archive(entity_id: int):
    e = _one("SELECT id, archived FROM entities WHERE id=?", (entity_id,))
    db = get_db()
    db.execute("UPDATE entities SET archived=?, updated_at=datetime('now','localtime') WHERE id=?",
               (0 if e["archived"] else 1, entity_id))
    db.commit()
    return _serialize(_one("SELECT * FROM entities WHERE id=?", (entity_id,)))


# ---------- 章节关联 ----------

@router.get("/entities/{entity_id}/chapters")
def entity_chapters(entity_id: int):
    _one("SELECT id FROM entities WHERE id=?", (entity_id,))
    return _all(
        """SELECT c.id, c.title, c.status, c.word_count, c.updated_at,
                  v.title AS volume_title, v.id AS volume_id
           FROM chapter_entities ce
           JOIN chapters c ON c.id = ce.chapter_id
           JOIN volumes v ON v.id = c.volume_id
           WHERE ce.entity_id=? ORDER BY v.sort_order, c.sort_order, c.id""", (entity_id,))


class ChapterLinkIn(BaseModel):
    chapter_id: int


@router.post("/entities/{entity_id}/chapters", status_code=201)
def link_entity_chapter(entity_id: int, body: ChapterLinkIn):
    e = _one("SELECT id, work_id FROM entities WHERE id=?", (entity_id,))
    db = get_db()
    row = db.execute(
        """SELECT c.id FROM chapters c
           JOIN volumes v ON v.id = c.volume_id
           WHERE c.id=? AND v.work_id=?""", (body.chapter_id, e["work_id"])).fetchone()
    if row is None:
        raise HTTPException(400, "章节不存在或不属于该作品")
    db.execute("INSERT OR IGNORE INTO chapter_entities(chapter_id, entity_id) VALUES (?,?)",
               (body.chapter_id, entity_id))
    db.commit()
    return entity_chapters(entity_id)


@router.delete("/entities/{entity_id}/chapters/{chapter_id}", status_code=204)
def unlink_entity_chapter(entity_id: int, chapter_id: int):
    _one("SELECT id FROM entities WHERE id=?", (entity_id,))
    db = get_db()
    db.execute("DELETE FROM chapter_entities WHERE entity_id=? AND chapter_id=?",
               (entity_id, chapter_id))
    db.commit()


@router.get("/chapters/{chapter_id}/entities")
def chapter_entities(chapter_id: int):
    """某章节关联的设定条目（工作台 AI 上下文用）。"""
    _one("SELECT id FROM chapters WHERE id=?", (chapter_id,))
    rows = _all(
        """SELECT e.id, e.work_id, e.name, e.category, e.tags, e.content, e.fields_json, e.updated_at
           FROM entities e JOIN chapter_entities ce ON ce.entity_id=e.id
           WHERE ce.chapter_id=? AND e.archived=0
           ORDER BY e.category, e.name, e.id""", (chapter_id,))
    return [_serialize(r) for r in rows]


class ChapterEntityLinkIn(BaseModel):
    entity_id: int


@router.post("/chapters/{chapter_id}/entities", status_code=201)
def link_chapter_entity(chapter_id: int, body: ChapterEntityLinkIn):
    ch = _one("""SELECT c.id, v.work_id FROM chapters c
                 JOIN volumes v ON v.id = c.volume_id WHERE c.id=?""", (chapter_id,))
    ent = _one("SELECT id, work_id FROM entities WHERE id=?", (body.entity_id,))
    if ch["work_id"] != ent["work_id"]:
        raise HTTPException(400, "实体与章节不属于同一作品")
    db = get_db()
    db.execute("INSERT OR IGNORE INTO chapter_entities(chapter_id, entity_id) VALUES (?,?)",
               (chapter_id, body.entity_id))
    db.commit()
    return chapter_entities(chapter_id)


@router.delete("/chapters/{chapter_id}/entities/{entity_id}", status_code=204)
def unlink_chapter_entity(chapter_id: int, entity_id: int):
    _one("SELECT id FROM chapters WHERE id=?", (chapter_id,))
    _one("SELECT id FROM entities WHERE id=?", (entity_id,))
    db = get_db()
    db.execute("DELETE FROM chapter_entities WHERE chapter_id=? AND entity_id=?",
               (chapter_id, entity_id))
    db.commit()


class ChapterBatchEntitiesIn(BaseModel):
    entity_ids: list[int]


@router.post("/chapters/{chapter_id}/entities/batch", status_code=200)
def batch_link_chapter_entities(chapter_id: int, body: ChapterBatchEntitiesIn):
    ch = _one("""SELECT c.id, v.work_id FROM chapters c
                 JOIN volumes v ON v.id = c.volume_id WHERE c.id=?""", (chapter_id,))
    db = get_db()
    for eid in body.entity_ids:
        ent = db.execute("SELECT id, work_id FROM entities WHERE id=?", (eid,)).fetchone()
        if ent and ent["work_id"] == ch["work_id"]:
            db.execute("INSERT OR IGNORE INTO chapter_entities(chapter_id, entity_id) VALUES (?,?)",
                       (chapter_id, eid))
    db.commit()
    return chapter_entities(chapter_id)


# ---------- 未入库实体探测与批量入库 ----------

class DetectUnregisteredIn(BaseModel):
    content: str
    chapter_id: int | None = None


STOP_WORDS = {
    '主角', '配角', '反派', '宗主', '掌门', '长老', '师尊', '师傅', '师父', '师兄', '师弟', '师姐', '师妹',
    '弟子', '众人', '所有人', '此时', '片刻', '刹那', '翌日', '第二天', '不知', '没有', '什么', '这个', '那个',
    '一个', '自己', '他们', '我们', '你们', '天下', '人间', '江湖', '天地', '苍生', '世间', '时间', '地点',
    '人物', '角色', '身份', '关系', '能力', '限制', '目标', '冲突', '转折', '伏笔', '细纲', '大纲', '场景'
}

CATEGORY_MAP = {
    'character': 'character',
    '人物': 'character',
    '角色': 'character',
    '主角': 'character',
    '配角': 'character',
    '反派': 'character',
    'item': 'item',
    '道具': 'item',
    '法宝': 'item',
    '武器': 'item',
    '神兵': 'item',
    '物品': 'item',
    '功法': 'item',
    '秘籍': 'item',
    '灵药': 'item',
    '丹药': 'item',
    'place': 'place',
    'location': 'place',
    '地点': 'place',
    '场景': 'place',
    '城池': 'place',
    '秘境': 'place',
    '洞府': 'place',
    '世界': 'place',
    'faction': 'faction',
    '势力': 'faction',
    '宗门': 'faction',
    '家族': 'faction',
    '帮派': 'faction',
    '门派': 'faction',
    '组织': 'faction',
    'term': 'term',
    'lore': 'term',
    '法则': 'term',
    '规则': 'term',
    '体系': 'term',
    '设定': 'term',
    '境界': 'term',
    '概念': 'term'
}


@router.post('/works/{work_id}/entities/detect-unregistered')
def detect_unregistered_entities(work_id: int, body: DetectUnregisteredIn):
    _one('SELECT id FROM works WHERE id=?', (work_id,))
    content = (body.content or '').strip()
    if not content:
        return {'unregistered': []}

    db = get_db()
    existing_rows = db.execute('SELECT name, fields_json FROM entities WHERE work_id=?', (work_id,)).fetchall()
    known_names = set()
    for row in existing_rows:
        if row['name']:
            known_names.add(row['name'].strip().lower())
        try:
            fields = json.loads(row['fields_json'] or '{}')
            for alias_key in ('aliases', 'alias', '别名'):
                val = fields.get(alias_key)
                if isinstance(val, list):
                    for v in val:
                        if v and str(v).strip():
                            known_names.add(str(v).strip().lower())
                elif isinstance(val, str) and val.strip():
                    for v in val.replace('，', ',').split(','):
                        if v.strip():
                            known_names.add(v.strip().lower())
        except Exception:
            pass

    import re
    from ..workflow_assets import extract_structured_assets_from_text

    raw_candidates = []

    # 1. workflow_assets 提取
    structured = extract_structured_assets_from_text(content)
    for ent in structured.get('entities', []):
        raw_candidates.append({
            'name': (ent.get('name') or '').strip(),
            'category': ent.get('category', 'term'),
            'snippet': ent.get('content') or ent.get('summary') or ''
        })

    # 2. 显式标记提取 【类别】名称
    cat_keys_re = '|'.join(re.escape(k) for k in CATEGORY_MAP.keys())
    tag_pattern = re.compile(r'[【\[](' + cat_keys_re + r')[】\]]\s*[:：]?\s*([^\s:：(（【】\[\]，,。！？!?]{2,20})')
    for match in tag_pattern.finditer(content):
        cat_raw = match.group(1)
        name = match.group(2).strip()
        name = re.split(r'[的了在是有与和同从至向对入出被把]', name)[0].strip()
        start = max(0, match.start() - 20)
        end = min(len(content), match.end() + 20)
        raw_candidates.append({
            'name': name,
            'category': CATEGORY_MAP.get(cat_raw, 'term'),
            'snippet': content[start:end].strip()
        })

    # 3. 标题档案卡 ### 名称（身份）
    header_pattern = re.compile(r'^[#*>\s\-]*###\s+([^\s:：（(—–#\-]{2,20})(?:[（(]([^）)]+)[）)])?', re.MULTILINE)
    for match in header_pattern.finditer(content):
        name = match.group(1).strip()
        sub = match.group(2) or ''
        cat = 'character'
        for k, v in CATEGORY_MAP.items():
            if k in sub:
                cat = v
                break
        start = max(0, match.start() - 10)
        end = min(len(content), match.end() + 30)
        raw_candidates.append({
            'name': name,
            'category': cat,
            'snippet': content[start:end].strip()
        })

    # 4. 专名特征提取 《宝物/秘籍》
    book_pattern = re.compile(r'《([^》\s]{2,15})》')
    for match in book_pattern.finditer(content):
        name = match.group(1).strip()
        start = max(0, match.start() - 20)
        end = min(len(content), match.end() + 20)
        raw_candidates.append({
            'name': name,
            'category': 'item',
            'snippet': content[start:end].strip()
        })

    seen_names = set()
    unregistered = []

    for c in raw_candidates:
        name = c['name'].strip()
        if not name or len(name) < 2 or len(name) > 25:
            continue
        name = re.sub(r'[^\w\u4e00-\u9fa5]+$|^[^\w\u4e00-\u9fa5]+', '', name)
        if not name or len(name) < 2 or name in STOP_WORDS or name.lower() in STOP_WORDS:
            continue
        if name.lower() in known_names or name.lower() in seen_names:
            continue

        seen_names.add(name.lower())
        cat = CATEGORY_MAP.get(c.get('category', ''), 'term')
        if cat not in CATEGORIES:
            cat = 'term'

        snippet = (c.get('snippet') or '').strip()
        if not snippet:
            idx = content.find(name)
            if idx != -1:
                start = max(0, idx - 20)
                end = min(len(content), idx + len(name) + 20)
                snippet = content[start:end].strip()

        cat_names_cn = {
            'character': '人物',
            'item': '道具',
            'place': '地点',
            'faction': '势力',
            'term': '术语/法则',
            'custom': '自定义'
        }
        tag_val = cat_names_cn.get(cat, '设定')
        suggested_tags = f'新设定,{tag_val}'

        unregistered.append({
            'name': name,
            'category': cat,
            'snippet': snippet,
            'suggested_tags': suggested_tags
        })

    return {'unregistered': unregistered}


class BatchIntakeItem(BaseModel):
    name: str
    category: str = 'character'
    content: str = ''
    tags: str = ''
    fields_json: dict = {}


class BatchIntakeIn(BaseModel):
    entities: list[BatchIntakeItem]
    chapter_id: int | None = None


@router.post('/works/{work_id}/entities/batch-intake', status_code=201)
def batch_intake_entities(work_id: int, body: BatchIntakeIn):
    _one('SELECT id FROM works WHERE id=?', (work_id,))
    db = get_db()

    target_chapter_id = None
    if body.chapter_id:
        ch = db.execute(
            'SELECT c.id FROM chapters c JOIN volumes v ON v.id = c.volume_id WHERE c.id=? AND v.work_id=?',
            (body.chapter_id, work_id)
        ).fetchone()
        if ch:
            target_chapter_id = ch['id']

    created_or_linked = []
    added_count = 0

    for item in body.entities:
        name = (item.name or '').strip()
        if not name:
            continue
        cat = item.category if item.category in CATEGORIES else 'term'
        content = (item.content or '').strip()
        tags = (item.tags or '').strip()
        fields_str = json.dumps(item.fields_json or {}, ensure_ascii=False)

        exist = db.execute('SELECT id FROM entities WHERE work_id=? AND name=?', (work_id, name)).fetchone()
        if exist:
            eid = exist['id']
        else:
            cur = db.execute(
                'INSERT INTO entities (work_id, category, name, content, fields_json, tags) VALUES (?,?,?,?,?,?)',
                (work_id, cat, name, content, fields_str, tags)
            )
            eid = cur.lastrowid
            added_count += 1

        if target_chapter_id:
            db.execute(
                'INSERT OR IGNORE INTO chapter_entities (chapter_id, entity_id) VALUES (?,?)',
                (target_chapter_id, eid)
            )

        row = _one('SELECT * FROM entities WHERE id=?', (eid,))
        created_or_linked.append(_serialize(row))

    db.execute("UPDATE works SET updated_at=datetime('now','localtime') WHERE id=?", (work_id,))
    db.commit()

    return {
        'added_count': added_count,
        'total_processed': len(created_or_linked),
        'entities': created_or_linked
    }
