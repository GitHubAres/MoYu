# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.

"""应用内 AI 与提示词功能实现。"""
import asyncio
import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import time

from app.ai_tasks import create_task, fail_task, finish_task, start_task
from app.ai_client import AIError, chat, chat_stream, get_ai_config
from app.db import get_db


class _GenIn(BaseModel):
    task: str
    instruction: str = ""
    context: str = ""
    selection: str = ""
    length: str = "medium"
    candidates: int = 1
    stream: bool = False
    work_id: int | None = None
    prompt_id: int | None = None


class _TestIn(BaseModel):
    task: str | None = None


class _PromptIn(BaseModel):
    name: str
    task_type: str = "continue"
    template: str


class _StyleGenIn(BaseModel):
    chapter_ids: list[int] = []


class _StyleIn(BaseModel):
    style_profile: str = ""


class _AnalyzeIn(BaseModel):
    work_id: int | None = None
    file_token: str | None = None


class _SaveStyleIn(BaseModel):
    work_id: int
    style_profile: str


class _ExtractLoreIn(BaseModel):
    file_token: str


class _ImportLoreIn(BaseModel):
    work_id: int
    entities: list[dict] = []
    outline: list[dict] = []


class _BrewIn(BaseModel):
    step: str
    instruction: str = ""
    context: str = ""


class _CompleteIn(BaseModel):
    mode: str = "new"
    title: str = ""
    work_id: int | None = None
    brew: dict = {}


def _extract_json(text: str) -> dict | list:
    """从大模型回复中提取并解析 JSON 对象或数组。"""
    t = text.strip()
    m = re.search(r"```(?:json)?\s*([\{\[].*?[\}\]])\s*```", t, re.DOTALL)
    if m:
        t = m.group(1).strip()
    else:
        m_obj = re.search(r"(\{.*\})", t, re.DOTALL)
        m_arr = re.search(r"(\[.*\])", t, re.DOTALL)
        if m_obj and m_arr:
            t = m_obj.group(1) if m_obj.start() < m_arr.start() else m_arr.group(1)
        elif m_obj:
            t = m_obj.group(1)
        elif m_arr:
            t = m_arr.group(1)
    return json.loads(t)


class AIOrchestrator:
    """AI 写作功能实现。"""

    BASIC_PROMPTS = {
        "continue": "你是中文小说续写助手。请根据上下文续写后续正文，只输出正文。",
        "expand": "你是中文小说扩写助手。请对选区做细节扩充，只输出扩写后的正文。",
        "condense": "你是中文小说缩写助手。请压缩给定文本，只输出缩写后的正文。",
        "polish": "你是中文小说润色助手。请改写润色给定文本，只输出润色后的正文。",
        "outline": "你是小说大纲助手。请根据要求生成简洁的分章大纲。",
        "check": "你是小说设定检查助手。请检查正文与设定是否矛盾，列出问题。",
    }

    LENGTH_HINTS = {
        "short": "控制在 100~200 字。",
        "medium": "控制在 300~500 字。",
        "long": "800 字以上。",
    }

    async def generate(self, body: _GenIn):
        task = body.task if body.task in self.BASIC_PROMPTS else "continue"
        sys_prompt = self.BASIC_PROMPTS[task]
        # 若指定了自定义提示词模板，优先使用模板内容
        if body.prompt_id:
            row = get_db().execute("SELECT task_type, template FROM prompts WHERE id=?", (body.prompt_id,)).fetchone()
            if row:
                task = row["task_type"] if row["task_type"] in self.BASIC_PROMPTS else task
                sys_prompt = row["template"]
        cfg = get_ai_config()
        if not cfg.get("ai_api_key") or not cfg.get("ai_model"):
            raise HTTPException(400, "未配置 AI 接口，请先到系统设置页配置")

        sys_prompt += "\n" + self.LENGTH_HINTS.get(body.length, self.LENGTH_HINTS["medium"])
        parts = []
        if body.context:
            parts.append("【上下文】\n" + body.context)
        if body.selection:
            parts.append("【选中文本】\n" + body.selection)
        if body.instruction:
            parts.append("【写作要求】\n" + body.instruction)
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": "\n\n".join(parts) or "请开始。"},
        ]

        body.candidates = max(1, min(body.candidates, 3))

        if not body.stream:
            task_id = create_task(body.work_id, body.task, f"{body.task} / {body.length} / {body.candidates} 候选")
            start_time = time.time()
            start_task(task_id)
            try:
                results = await asyncio.gather(
                    *(chat(messages, cfg) for _ in range(body.candidates)),
                    return_exceptions=True)
                texts = []
                total_tokens = 0
                for r in results:
                    if isinstance(r, Exception):
                        continue
                    texts.append(r[0])
                    if isinstance(r[1], int):
                        total_tokens += r[1]
                if not texts:
                    raise HTTPException(502, "AI 生成失败")
                elapsed = int((time.time() - start_time) * 1000)
                finish_task(task_id, {"candidates": texts, "candidate_count": len(texts)},
                            token_used=total_tokens, elapsed_ms=elapsed)
                return {"candidates": texts, "usage": {"total_tokens": total_tokens}, "task_id": task_id}
            except Exception as e:
                fail_task(task_id, str(e), int((time.time() - start_time) * 1000))
                raise

        task_id = create_task(body.work_id, body.task, f"{body.task} / {body.length} / {body.candidates} 候选")
        start_time = time.time()
        start_task(task_id)

        async def event_stream():
            full_texts = [[] for _ in range(body.candidates)]
            total_tokens = 0
            try:
                yield "data: " + json.dumps({"task_id": task_id}, ensure_ascii=False) + "\n\n"
                for i in range(body.candidates):
                    yield "data: " + json.dumps({"candidate": i, "start": True}, ensure_ascii=False) + "\n\n"
                    async for delta in chat_stream(messages, cfg, {}):
                        full_texts[i].append(delta)
                        yield "data: " + json.dumps({"candidate": i, "delta": delta}, ensure_ascii=False) + "\n\n"
                texts = ["".join(t) for t in full_texts]
                elapsed = int((time.time() - start_time) * 1000)
                finish_task(task_id, {"candidates": texts, "candidate_count": len(texts)},
                            token_used=total_tokens, elapsed_ms=elapsed)
                yield "data: " + json.dumps({"done": True, "usage": {"total_tokens": total_tokens}, "task_id": task_id}, ensure_ascii=False) + "\n\n"
            except AIError as e:
                fail_task(task_id, str(e), int((time.time() - start_time) * 1000))
                yield "data: " + json.dumps({"error": str(e), "task_id": task_id}, ensure_ascii=False) + "\n\n"
            except Exception as e:
                fail_task(task_id, f"生成失败：{e}", int((time.time() - start_time) * 1000))
                yield "data: " + json.dumps({"error": f"生成失败：{e}", "task_id": task_id}, ensure_ascii=False) + "\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    async def test_connection(self, body: _TestIn | None = None):
        cfg = get_ai_config()
        if not cfg.get("ai_base_url") or not cfg.get("ai_api_key"):
            return {"ok": False, "message": "尚未填写 Base URL 或 API Key"}
        try:
            await chat([{"role": "user", "content": "hi"}], cfg, max_tokens=1)
            return {"ok": True, "message": "连接成功"}
        except AIError as e:
            return {"ok": False, "message": str(e)}
        except Exception as e:
            return {"ok": False, "message": f"连接失败：{e}"}

    def build_router(self) -> APIRouter:
        router = APIRouter(prefix="/ai", tags=["ai"])
        orchestrator = self

        @router.post("/generate")
        async def generate(body: _GenIn):
            return await orchestrator.generate(body)

        @router.post("/test")
        async def test_connection(body: _TestIn | None = None):
            return await orchestrator.test_connection(body)

        return router


class PromptLibrary:
    """提示词库：内置模板与用户自定义模板。"""

    TASK_TYPES = {
        "continue": "续写",
        "expand": "扩写",
        "shorten": "缩写",
        "rewrite": "改写润色",
        "outline": "大纲生成",
        "audit": "设定检查",
    }

    BUILTIN_PROMPTS = [
        ("续写·顺延文势", "continue",
         "你是一位长篇小说写作助手。请阅读以下上下文，顺着既有文势自然续写，"
         "保持人物的口吻与叙事节奏一致，不要复述已有内容。\n\n"
         "【上下文】\n{{context}}\n\n"
         "【当前选区】\n{{selection}}\n\n"
         "【写作要求】\n{{instruction}}\n\n请直接输出续写的正文，不要输出解释。"),
        ("扩写·充实细节", "expand",
         "你是一位长篇小说写作助手。请将选区内容扩写得更丰满：补充环境、动作、心理与感官细节，"
         "不改变情节走向，保持原有文风。\n\n"
         "【上下文】\n{{context}}\n\n"
         "【待扩写选区】\n{{selection}}\n\n"
         "【写作要求】\n{{instruction}}\n\n请直接输出扩写后的正文，不要输出解释。"),
        ("缩写·凝练取舍", "shorten",
         "你是一位长篇小说写作助手。请将选区内容缩写压缩，保留关键情节信息与最有力的意象，"
         "删去冗余铺陈，语言凝练。\n\n"
         "【上下文】\n{{context}}\n\n"
         "【待缩写选区】\n{{selection}}\n\n"
         "【写作要求】\n{{instruction}}\n\n请直接输出缩写后的正文，不要输出解释。"),
        ("改写润色·字句打磨", "rewrite",
         "你是一位长篇小说写作助手。请对选区文字进行改写润色：修正语病、替换平淡表达、"
         "调整句式节奏，但保留原意与叙事视角。\n\n"
         "【上下文】\n{{context}}\n\n"
         "【待润色选区】\n{{selection}}\n\n"
         "【写作要求】\n{{instruction}}\n\n请直接输出润色后的正文，不要输出解释。"),
        ("大纲生成·纲举目张", "outline",
         "你是一位长篇小说策划助手。请基于已有上下文与设定，生成结构清晰的故事大纲，"
         "按「卷/章」层级列出节点，每个节点给出标题与一句话梗概，注意承接收束已有伏笔。\n\n"
         "【上下文】\n{{context}}\n\n"
         "【相关要求】\n{{instruction}}\n\n请直接输出大纲，不要输出解释。"),
        ("设定检查·脉络稽核", "audit",
         "你是一位长篇小说的设定一致性审校助手。请对照作品设定库，检查所选章节正文中"
         "是否存在与设定矛盾、遗忘前后文、时间线错位等问题。\n\n"
         "【作品设定】\n{{context}}\n\n"
         "【待检查章节】\n{{selection}}\n\n"
         "【检查要求】\n{{instruction}}\n\n"
         "请逐条列出问题：问题类型、严重程度、涉及设定、问题描述、原文引用、所在章节。"),
    ]

    def _one(self, sql, args=()):
        row = get_db().execute(sql, args).fetchone()
        if row is None:
            raise HTTPException(404, "资源不存在")
        return dict(row)

    def _all(self, sql, args=()):
        return [dict(r) for r in get_db().execute(sql, args).fetchall()]

    def seed_builtin(self):
        db = get_db()
        if db.execute("SELECT COUNT(*) FROM prompts").fetchone()[0] == 0:
            for name, task_type, template in self.BUILTIN_PROMPTS:
                db.execute(
                    "INSERT INTO prompts(name, task_type, template, builtin) VALUES (?,?,?,1)",
                    (name, task_type, template))
            db.commit()

    def list_prompts(self, task_type: str = ""):
        sql = "SELECT * FROM prompts"
        args: list = []
        if task_type:
            sql += " WHERE task_type=?"
            args.append(task_type)
        sql += " ORDER BY builtin DESC, id"
        return self._all(sql, args)

    def create_prompt(self, body: _PromptIn):
        if body.task_type not in self.TASK_TYPES:
            raise HTTPException(400, f"未知任务类型：{body.task_type}")
        db = get_db()
        cur = db.execute(
            "INSERT INTO prompts(name, task_type, template, builtin) VALUES (?,?,?,0)",
            (body.name, body.task_type, body.template))
        db.commit()
        return self._one("SELECT * FROM prompts WHERE id=?", (cur.lastrowid,))

    def update_prompt(self, prompt_id: int, body: dict):
        self._one("SELECT id FROM prompts WHERE id=?", (prompt_id,))
        db = get_db()
        for k in ("name", "task_type", "template"):
            if k in body:
                db.execute(f"UPDATE prompts SET {k}=? WHERE id=?", (body[k], prompt_id))
        db.commit()
        return self._one("SELECT * FROM prompts WHERE id=?", (prompt_id,))

    def delete_prompt(self, prompt_id: int):
        row = self._one("SELECT * FROM prompts WHERE id=?", (prompt_id,))
        if row["builtin"]:
            raise HTTPException(400, "内置模板不可删除，可复制副本后修改")
        db = get_db()
        db.execute("DELETE FROM prompts WHERE id=?", (prompt_id,))
        db.commit()

    def duplicate_prompt(self, prompt_id: int):
        row = self._one("SELECT * FROM prompts WHERE id=?", (prompt_id,))
        db = get_db()
        cur = db.execute(
            "INSERT INTO prompts(name, task_type, template, builtin) VALUES (?,?,?,0)",
            (row["name"] + "（副本）", row["task_type"], row["template"]))
        db.commit()
        return self._one("SELECT * FROM prompts WHERE id=?", (cur.lastrowid,))

    def build_router(self) -> APIRouter:
        router = APIRouter(prefix="/prompts", tags=["prompts"])
        lib = self

        @router.get("")
        def list_prompts(task_type: str = ""):
            return lib.list_prompts(task_type)

        @router.post("", status_code=201)
        def create_prompt(body: _PromptIn):
            return lib.create_prompt(body)

        @router.patch("/{prompt_id}")
        def update_prompt(prompt_id: int, body: dict):
            return lib.update_prompt(prompt_id, body)

        @router.delete("/{prompt_id}", status_code=204)
        def delete_prompt(prompt_id: int):
            lib.delete_prompt(prompt_id)

        @router.post("/{prompt_id}/duplicate", status_code=201)
        def duplicate_prompt(prompt_id: int):
            return lib.duplicate_prompt(prompt_id)

        return router


class AlchemyEngine:
    """炼丹炉核心引擎：拆书蒸馏、资料融汇、开炉炼丹与成丹出炉。"""

    async def analyze(self, body: _AnalyzeIn):
        if body.file_token:
            from app.api.io_export import IMPORT_DIR, _parse_import
            token = Path(body.file_token).name
            p = IMPORT_DIR / token
            if not p.is_file():
                raise HTTPException(404, "暂存文件不存在或已过期，请重新上传")
            try:
                sections = _parse_import(p, p.stem)
            except Exception as e:
                raise HTTPException(400, f"文件解析失败：{e}")
            if not sections or not any((s.get("content") or "").strip() for s in sections):
                raise HTTPException(400, "文件内容为空，无法进行拆解")
            total_chars = sum(len(s.get("content", "")) for s in sections)
            sampled = sections if len(sections) <= 3 else [sections[0], sections[len(sections) // 2], sections[-1]]
            sample_texts = [f"【片段：{s.get('title', '正文')}】\n{(s.get('content') or '')[:1800]}" for s in sampled]
            sampled_chars = sum(len((s.get("content") or "")[:1800]) for s in sampled)
            sample_info = {
                "source": "file",
                "name": p.stem,
                "total_chars": total_chars,
                "sampled_chars": sampled_chars,
            }
        elif body.work_id:
            db = get_db()
            work = db.execute("SELECT id, title FROM works WHERE id=?", (body.work_id,)).fetchone()
            if not work:
                raise HTTPException(404, "作品不存在")
            chapters = db.execute(
                """SELECT c.id, c.title, c.content FROM chapters c
                   JOIN volumes v ON v.id = c.volume_id
                   WHERE v.work_id=? ORDER BY v.sort_order, c.sort_order, c.id""",
                (body.work_id,)).fetchall()
            if not chapters or not any((c["content"] or "").strip() for c in chapters):
                raise HTTPException(400, "该作品暂无有效章节正文，无法进行文风拆解")
            sampled = chapters if len(chapters) <= 3 else [chapters[0], chapters[len(chapters) // 2], chapters[-1]]
            sample_texts = [f"【章节：{c['title']}】\n{(c['content'] or '')[:1800]}" for c in sampled]
            sampled_chars = sum(len((c["content"] or "")[:1800]) for c in sampled)
            sample_info = {
                "source": "work",
                "name": work["title"],
                "chapter_count": len(chapters),
                "sampled_chapters": [c["title"] for c in sampled],
                "sampled_chars": sampled_chars,
            }
        else:
            raise HTTPException(400, "请指定要拆解的文件 (file_token) 或作品 (work_id)")

        cfg = get_ai_config()
        if not cfg.get("ai_api_key") or not cfg.get("ai_model"):
            raise HTTPException(400, "尚未配置 AI 接口，请先到系统设置页配置")

        sys_prompt = (
            "你是一位资深的文学评论家与长篇小说写作指导专家。请对以下提供的文本样本进行深度文风拆解与风格画像，"
            "提炼出可以直接指导后续创作与模仿的“文风档案”。\n\n"
            "请从以下维度进行专业、具体、条理清晰的剖析（使用 Markdown 格式）：\n"
            "1. **视角与叙事距离**：叙述视角、心理活动渗透度、客观冷峻或主观共情；\n"
            "2. **句式与叙事节奏**：长短句搭配、断句习惯、动作节拍、紧张与舒缓的转换；\n"
            "3. **词汇与意象特征**：动词精度、名词质感、修辞偏好、色彩与物象；\n"
            "4. **动作与感官描写**：视听触嗅味觉的调度、生理感受与具象细节；\n"
            "5. **对话与留白技巧**：对话密度、潜台词、肢体语言配合、悬念营造；\n"
            "6. **情绪基调与世界观质感**：作品底色、氛围铺设、文学气质总结。\n\n"
            "最后请附带一段「核心文风准则（6-8条紧凑要点）」，便于 AI 写作时精确遵循。"
        )
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": "\n\n----\n\n".join(sample_texts)},
        ]
        try:
            report, _ = await chat(messages, cfg)
        except AIError as e:
            raise HTTPException(502, str(e))
        return {"report": report.strip(), "sample_info": sample_info}

    def save_style(self, body: _SaveStyleIn):
        db = get_db()
        work = db.execute("SELECT id FROM works WHERE id=?", (body.work_id,)).fetchone()
        if not work:
            raise HTTPException(404, "目标作品不存在")
        profile = body.style_profile.strip()
        db.execute(
            "UPDATE works SET style_profile=?, updated_at=datetime('now','localtime') WHERE id=?",
            (profile, body.work_id))
        db.commit()
        return {"ok": True, "style_profile": profile}

    async def extract_lore(self, body: _ExtractLoreIn):
        from app.api.io_export import IMPORT_DIR, _parse_import
        token = Path(body.file_token).name
        p = IMPORT_DIR / token
        if not p.is_file():
            raise HTTPException(404, "暂存文件不存在或已过期，请重新上传")
        try:
            sections = _parse_import(p, p.stem)
        except Exception as e:
            raise HTTPException(400, f"文件解析失败：{e}")
        if not sections:
            raise HTTPException(400, "文件内容为空，无法提取设定")

        combined = []
        cur_len = 0
        for s in sections:
            txt = f"【{s.get('title', '片段')}】\n{s.get('content', '')}"
            combined.append(txt)
            cur_len += len(txt)
            if cur_len >= 8000:
                break
        doc_text = "\n\n".join(combined)[:8000]

        cfg = get_ai_config()
        if not cfg.get("ai_api_key") or not cfg.get("ai_model"):
            raise HTTPException(400, "尚未配置 AI 接口，请先到系统设置页配置")

        sys_prompt = (
            "你是一位长篇小说世界观设定与剧情大纲架构专家。请通读用户给出的资料文本，"
            "提炼出世界观设定（人物/地点/势力/物品/术语）与剧情大纲节点。\n\n"
            "必须输出严格合法的 JSON 格式（使用 ```json 代码块包裹），结构如下：\n"
            "{\n"
            '  "entities": [\n'
            '    {\n'
            '      "category": "character" | "place" | "faction" | "item" | "term",\n'
            '      "name": "设定条目名称",\n'
            '      "tags": "标签1, 标签2",\n'
            '      "content": "详细设定说明（身份/性格/背景/特征/规则等）"\n'
            '    }\n'
            "  ],\n"
            '  "outline": [\n'
            '    {\n'
            '      "title": "大纲章节或情节点标题",\n'
            '      "synopsis": "该情节点或章节的剧情梗概",\n'
            '      "parent": "可选所属分卷名或父节点标题"\n'
            '    }\n'
            "  ]\n"
            "}"
        )
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": doc_text},
        ]
        try:
            raw_text, _ = await chat(messages, cfg)
            data = _extract_json(raw_text)
        except AIError as e:
            raise HTTPException(502, str(e))
        except Exception as e:
            raise HTTPException(502, f"解析 AI 提炼结果失败：{e}")

        entities = data.get("entities", []) if isinstance(data, dict) else []
        outline = data.get("outline", []) if isinstance(data, dict) else []
        valid_cats = {"character", "place", "faction", "item", "term"}
        cleaned_entities = []
        for e in entities:
            if isinstance(e, dict) and str(e.get("name", "")).strip():
                cat = str(e.get("category", "term")).lower().strip()
                if cat not in valid_cats:
                    cat = "term"
                cleaned_entities.append({
                    "category": cat,
                    "name": str(e["name"]).strip(),
                    "tags": str(e.get("tags", "")).strip(),
                    "content": str(e.get("content", "")).strip(),
                })
        cleaned_outline = []
        for o in outline:
            if isinstance(o, dict) and str(o.get("title", "")).strip():
                cleaned_outline.append({
                    "title": str(o["title"]).strip(),
                    "synopsis": str(o.get("synopsis", "")).strip(),
                    "parent": str(o.get("parent", "")).strip() if o.get("parent") else None,
                })
        return {"entities": cleaned_entities, "outline": cleaned_outline}

    def import_lore(self, body: _ImportLoreIn):
        db = get_db()
        work = db.execute("SELECT id FROM works WHERE id=?", (body.work_id,)).fetchone()
        if not work:
            raise HTTPException(404, "目标作品不存在")

        existing_ents = {
            (r["category"], r["name"])
            for r in db.execute(
                "SELECT category, name FROM entities WHERE work_id=? AND archived=0",
                (body.work_id,)).fetchall()
        }
        valid_cats = {"character", "place", "faction", "item", "term", "custom"}
        ent_created = 0
        skipped = 0
        for e in body.entities:
            cat = str(e.get("category", "term")).strip()
            if cat not in valid_cats:
                cat = "term"
            name = str(e.get("name", "")).strip()
            if not name:
                continue
            if (cat, name) in existing_ents:
                skipped += 1
                continue
            content = str(e.get("content", "")).strip()
            tags = str(e.get("tags", "")).strip()
            db.execute(
                "INSERT INTO entities(work_id, category, name, content, tags) VALUES (?, ?, ?, ?, ?)",
                (body.work_id, cat, name, content, tags))
            existing_ents.add((cat, name))
            ent_created += 1

        out_created = 0
        parent_map = {}
        for o in body.outline:
            title = str(o.get("title", "")).strip()
            if not title:
                continue
            synopsis = str(o.get("synopsis", "")).strip()
            parent_name = str(o.get("parent") or "").strip()
            parent_id = None
            if parent_name:
                if parent_name not in parent_map:
                    row = db.execute(
                        "SELECT id FROM outline_nodes WHERE work_id=? AND title=?",
                        (body.work_id, parent_name)).fetchone()
                    if row:
                        parent_map[parent_name] = row["id"]
                    else:
                        cur = db.execute(
                            "INSERT INTO outline_nodes(work_id, title, synopsis, sort_order) VALUES (?, ?, '', ?)",
                            (body.work_id, parent_name, out_created))
                        parent_map[parent_name] = cur.lastrowid
                        out_created += 1
                parent_id = parent_map[parent_name]
            db.execute(
                "INSERT INTO outline_nodes(work_id, parent_id, title, synopsis, sort_order) VALUES (?, ?, ?, ?, ?)",
                (body.work_id, parent_id, title, synopsis, out_created))
            out_created += 1

        db.execute("UPDATE works SET updated_at=datetime('now','localtime') WHERE id=?", (body.work_id,))
        db.commit()
        return {"created": {"entities": ent_created, "outline": out_created}, "skipped": skipped}

    async def brew(self, body: _BrewIn):
        if body.step not in ("framework", "world", "characters", "outline"):
            raise HTTPException(400, "step 必须为 framework / world / characters / outline 之一")

        cfg = get_ai_config()
        if not cfg.get("ai_api_key") or not cfg.get("ai_model"):
            raise HTTPException(400, "尚未配置 AI 接口，请先到系统设置页配置")

        step_prompts = {
            "framework": (
                "你是一位资深网络文学总编与长篇小说策划专家。请根据用户的构想或指令，设计小说的【题材框架】。\n"
                "必须输出严格合法的 JSON 对象（使用 ```json 代码块包裹），字段规范如下：\n"
                "{\n"
                '  "title_suggestions": ["书名建议1", "书名建议2", "书名建议3", "书名建议4"],\n'
                '  "genre": "题材流派（如：东方仙侠、废土末日、规则怪谈、赛博悬疑）",\n'
                '  "target_audience": "核心受众画像与爽点定位",\n'
                '  "core_selling_points": ["核心卖点1", "核心卖点2", "核心卖点3"],\n'
                '  "one_sentence_logline": "一句话核心主线（包含主角处境、核心冲突与终极目标）"\n'
                "}"
            ),
            "world": (
                "你是一位宏大的长篇小说世界观设计师。请结合前序已确定的题材框架与用户指令，构建【世界观设定集】。\n"
                "必须输出严格合法的 JSON 对象（使用 ```json 代码块包裹），字段规范如下：\n"
                "{\n"
                '  "worldview_overview": "世界历史背景、核心法则与宏观矛盾总述",\n'
                '  "power_system": "修炼境界/超凡序列/科技等级与核心晋升代价",\n'
                '  "factions": [{"name": "势力名", "type": "宗门/组织/财阀", "description": "背景与立场说明"}],\n'
                '  "locations": [{"name": "地点名", "type": "核心地图/秘境/禁区", "description": "风貌与剧情定位"}],\n'
                '  "terms": [{"name": "专有术语或关键宝物", "description": "概念定义或物品效果"}]\n'
                "}"
            ),
            "characters": (
                "你是一位深刻的人物塑造专家。请结合前序的题材框架与世界观，设计小说的【主要人物角色集】。\n"
                "必须输出严格合法的 JSON 对象（使用 ```json 代码块包裹），字段规范如下：\n"
                "{\n"
                '  "characters": [\n'
                '    {\n'
                '      "name": "人物姓名",\n'
                '      "role": "主角 / 宿敌反派 / 核心配角",\n'
                '      "identity": "表面身份与隐藏背景",\n'
                '      "personality": "性格特质、行事准则与人物弧光",\n'
                '      "background": "身世过往与生平重要转折",\n'
                '      "goal": "短期欲求与终极目标",\n'
                '      "ability": "核心功法、专精能力或金手指"\n'
                '    }\n'
                "  ]\n"
                "}\n"
                "请至少塑造 1 名主角、1 名核心反派及 2 名重要配角。"
            ),
            "outline": (
                "你是一位精通长篇小说节奏把控的故事架构师。请结合前序的题材、世界观与人物，编排【分卷分章大纲树】。\n"
                "必须输出严格合法的 JSON 对象（使用 ```json 代码块包裹），字段规范如下：\n"
                "{\n"
                '  "volumes": [\n'
                '    {\n'
                '      "title": "第一卷 卷名",\n'
                '      "synopsis": "本卷主线脉络与高潮节点",\n'
                '      "chapters": [\n'
                '        {"title": "第一章 章名", "synopsis": "本章开篇场景、核心冲突与悬念"},\n'
                '        {"title": "第二章 章名", "synopsis": "本章剧情推进与伏笔展开"}\n'
                '      ]\n'
                '    }\n'
                "  ]\n"
                "}"
            ),
        }

        parts = []
        if body.context.strip():
            parts.append(f"【前序已确认设定上下文】\n{body.context.strip()}")
        if body.instruction.strip():
            parts.append(f"【作者指令与构想】\n{body.instruction.strip()}")
        user_msg = "\n\n".join(parts) or "请按照题材规律开始推演。"

        messages = [
            {"role": "system", "content": step_prompts[body.step]},
            {"role": "user", "content": user_msg},
        ]
        try:
            raw_text, _ = await chat(messages, cfg)
            data = _extract_json(raw_text)
        except AIError as e:
            raise HTTPException(502, str(e))
        except Exception as e:
            raise HTTPException(502, f"解析炼丹结果 JSON 失败：{e}")
        return {"result": data}

    def complete(self, body: _CompleteIn):
        db = get_db()
        brew = body.brew or {}
        framework = brew.get("framework") or {}
        world = brew.get("world") or {}
        chars = brew.get("characters") or {}
        outline = brew.get("outline") or {}

        if body.mode == "new":
            suggestions = framework.get("title_suggestions") or []
            title = body.title.strip() or (suggestions[0] if suggestions else "未命名新书")
            genre = str(framework.get("genre", "")).strip()
            intro = str(framework.get("one_sentence_logline", "")).strip()
            cur = db.execute(
                "INSERT INTO works(title, genre, intro) VALUES (?, ?, ?)",
                (title, genre, intro))
            work_id = cur.lastrowid
            db.execute("INSERT INTO volumes(work_id, title, sort_order) VALUES (?, '卷一', 1)", (work_id,))
        else:
            if not body.work_id:
                raise HTTPException(400, "现有作品模式必须指定 work_id")
            work = db.execute("SELECT id, genre, intro FROM works WHERE id=?", (body.work_id,)).fetchone()
            if not work:
                raise HTTPException(404, "目标作品不存在")
            work_id = body.work_id
            new_genre = work["genre"] or str(framework.get("genre", "")).strip()
            new_intro = work["intro"] or str(framework.get("one_sentence_logline", "")).strip()
            db.execute(
                "UPDATE works SET genre=?, intro=?, updated_at=datetime('now','localtime') WHERE id=?",
                (new_genre, new_intro, work_id))

        ent_count = 0
        if isinstance(world, dict):
            if world.get("worldview_overview"):
                db.execute(
                    "INSERT INTO entities(work_id, category, name, content, tags) VALUES (?, ?, ?, ?, ?)",
                    (work_id, "custom", "世界观架构总述", str(world["worldview_overview"]).strip(), "世界观,总纲"))
                ent_count += 1
            if world.get("power_system"):
                db.execute(
                    "INSERT INTO entities(work_id, category, name, content, tags) VALUES (?, ?, ?, ?, ?)",
                    (work_id, "term", "力量与境界体系", str(world["power_system"]).strip(), "力量体系,境界"))
                ent_count += 1
            for f in world.get("factions", []):
                if isinstance(f, dict) and str(f.get("name", "")).strip():
                    db.execute(
                        "INSERT INTO entities(work_id, category, name, content, tags) VALUES (?, ?, ?, ?, ?)",
                        (work_id, "faction", str(f["name"]).strip(),
                         str(f.get("description", "")).strip(), str(f.get("type", "")).strip()))
                    ent_count += 1
            for loc in world.get("locations", []):
                if isinstance(loc, dict) and str(loc.get("name", "")).strip():
                    db.execute(
                        "INSERT INTO entities(work_id, category, name, content, tags) VALUES (?, ?, ?, ?, ?)",
                        (work_id, "place", str(loc["name"]).strip(),
                         str(loc.get("description", "")).strip(), str(loc.get("type", "")).strip()))
                    ent_count += 1
            for t in world.get("terms", []):
                if isinstance(t, dict) and str(t.get("name", "")).strip():
                    db.execute(
                        "INSERT INTO entities(work_id, category, name, content, tags) VALUES (?, ?, ?, ?, ?)",
                        (work_id, "term", str(t["name"]).strip(),
                         str(t.get("description", "")).strip(), "术语"))
                    ent_count += 1

        char_list = chars.get("characters", []) if isinstance(chars, dict) else (chars if isinstance(chars, list) else [])
        for c in char_list:
            if isinstance(c, dict) and str(c.get("name", "")).strip():
                fields = {}
                for k_src, k_dst in [("identity", "身份"), ("personality", "性格"), ("goal", "目标与变化"), ("ability", "核心能力")]:
                    if c.get(k_src):
                        fields[k_dst] = str(c[k_src]).strip()
                db.execute(
                    "INSERT INTO entities(work_id, category, name, content, fields_json, tags) VALUES (?, ?, ?, ?, ?, ?)",
                    (work_id, "character", str(c["name"]).strip(),
                     str(c.get("background", "")).strip(),
                     json.dumps(fields, ensure_ascii=False),
                     str(c.get("role", "角色")).strip()))
                ent_count += 1

        out_count = 0
        vol_list = outline.get("volumes", []) if isinstance(outline, dict) else (outline if isinstance(outline, list) else [])
        for v_idx, vol in enumerate(vol_list):
            if not isinstance(vol, dict):
                continue
            v_title = str(vol.get("title") or f"第{v_idx + 1}卷").strip()
            v_syn = str(vol.get("synopsis") or "").strip()
            cur = db.execute(
                "INSERT INTO outline_nodes(work_id, title, synopsis, sort_order) VALUES (?, ?, ?, ?)",
                (work_id, v_title, v_syn, v_idx))
            vol_node_id = cur.lastrowid
            out_count += 1
            for c_idx, ch in enumerate(vol.get("chapters", [])):
                if not isinstance(ch, dict):
                    continue
                c_title = str(ch.get("title") or f"第{c_idx + 1}章").strip()
                c_syn = str(ch.get("synopsis") or "").strip()
                db.execute(
                    "INSERT INTO outline_nodes(work_id, parent_id, title, synopsis, sort_order) VALUES (?, ?, ?, ?, ?)",
                    (work_id, vol_node_id, c_title, c_syn, c_idx))
                out_count += 1

        db.commit()
        return {"work_id": work_id, "created": {"entities": ent_count, "outline": out_count}}

    def build_router(self) -> APIRouter:
        router = APIRouter(prefix="/alchemy", tags=["alchemy"])
        engine = self

        @router.post("/analyze")
        async def analyze(body: _AnalyzeIn, async_mode: bool = False):
            if async_mode:
                from app.ai_tasks import create_task, run_async_task
                import asyncio
                task_id = create_task(body.work_id, "alchemy_analyze", f"拆书分析: {body.file_token or body.work_id}")
                asyncio.create_task(run_async_task(task_id, engine.analyze(body)))
                return {"task_id": task_id, "status": "pending"}
            return await engine.analyze(body)

        @router.post("/save-style")
        def save_style(body: _SaveStyleIn):
            return engine.save_style(body)

        @router.post("/extract-lore")
        async def extract_lore(body: _ExtractLoreIn, async_mode: bool = False):
            if async_mode:
                from app.ai_tasks import create_task, run_async_task
                import asyncio
                task_id = create_task(None, "alchemy_extract_lore", f"资料融汇: {body.file_token}")
                asyncio.create_task(run_async_task(task_id, engine.extract_lore(body)))
                return {"task_id": task_id, "status": "pending"}
            return await engine.extract_lore(body)

        @router.post("/import-lore")
        def import_lore(body: _ImportLoreIn):
            return engine.import_lore(body)

        @router.post("/brew")
        async def brew(body: _BrewIn, async_mode: bool = False):
            if async_mode:
                from app.ai_tasks import create_task, run_async_task
                import asyncio
                task_id = create_task(None, "alchemy_brew", f"开炉推演: {body.step}")
                asyncio.create_task(run_async_task(task_id, engine.brew(body)))
                return {"task_id": task_id, "status": "pending"}
            return await engine.brew(body)

        @router.post("/complete", status_code=201)
        def complete(body: _CompleteIn):
            return engine.complete(body)

        return router


class StyleEngine:
    """文风档案 API 实现。"""

    def get_style(self, work_id: int):
        row = get_db().execute("SELECT style_profile FROM works WHERE id=?",
                               (work_id,)).fetchone()
        return {"style_profile": (row["style_profile"] or "") if row else ""}

    async def generate_style(self, work_id: int, body: _StyleGenIn):
        db = get_db()
        work = db.execute("SELECT id, title FROM works WHERE id=?", (work_id,)).fetchone()
        if not work:
            raise HTTPException(404, "作品不存在")
        if body.chapter_ids:
            q_marks = ",".join("?" for _ in body.chapter_ids)
            chapters = db.execute(
                f"SELECT id, title, content FROM chapters WHERE id IN ({q_marks})",
                tuple(body.chapter_ids)).fetchall()
        else:
            chapters = db.execute(
                """SELECT c.id, c.title, c.content FROM chapters c
                   JOIN volumes v ON v.id = c.volume_id
                   WHERE v.work_id=? ORDER BY v.sort_order, c.sort_order, c.id LIMIT 5""",
                (work_id,)).fetchall()
        if not chapters or not any((c["content"] or "").strip() for c in chapters):
            raise HTTPException(400, "所选章节无有效正文内容，无法提炼文风档案")

        cfg = get_ai_config()
        if not cfg.get("ai_api_key") or not cfg.get("ai_model"):
            raise HTTPException(400, "尚未配置 AI 接口，请先到系统设置页配置")

        sample_texts = [f"【{c['title']}】\n{(c['content'] or '')[:1500]}" for c in chapters]
        sys_prompt = (
            "你是一位文风精炼专家。请阅读用户作品正文样本，提炼出 6-8 条紧凑、具体、具备可操作性的文风档案规则，"
            "每条以圆点 `·` 开头，重点包含：叙事视角、句式长短与节奏、动词与名词质感、感官描写、对话与留白风格、情绪氛围。\n"
            "只输出这 6-8 条规则要点，无需额外标题或寒暄。"
        )
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": "\n\n----\n\n".join(sample_texts)},
        ]
        try:
            text, _ = await chat(messages, cfg)
        except AIError as e:
            raise HTTPException(502, str(e))
        return {"style_profile": text.strip()}

    def save_style(self, work_id, body):
        db = get_db()
        db.execute("UPDATE works SET style_profile=? WHERE id=?",
                   (body.style_profile.strip(), work_id))
        db.commit()
        return {"style_profile": body.style_profile.strip()}

    def clear_style(self, work_id):
        db = get_db()
        db.execute("UPDATE works SET style_profile='' WHERE id=?", (work_id,))
        db.commit()
        return {"style_profile": ""}

    def build_router(self) -> APIRouter:
        router = APIRouter(tags=["style"])
        engine = self

        @router.get("/works/{work_id}/style")
        def get_style(work_id: int):
            return engine.get_style(work_id)

        @router.post("/works/{work_id}/style/generate")
        async def generate_style(work_id: int, body: _StyleGenIn):
            return await engine.generate_style(work_id, body)

        @router.put("/works/{work_id}/style")
        def save_style(work_id: int, body: _StyleIn):
            return engine.save_style(work_id, body)

        @router.delete("/works/{work_id}/style")
        def clear_style(work_id: int):
            return engine.clear_style(work_id)

        return router


_orchestrator = AIOrchestrator()
_prompt_library = PromptLibrary()
_alchemy_engine = AlchemyEngine()
_style_engine = StyleEngine()


def get_orchestrator():
    return _orchestrator


def get_prompt_library():
    return _prompt_library


def get_alchemy_engine():
    return _alchemy_engine


def get_style_engine():
    return _style_engine
