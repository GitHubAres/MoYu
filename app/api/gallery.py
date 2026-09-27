"""丹青阁：作品图片生成与图库 API（OpenAI Images 兼容协议）。"""
import base64
import binascii

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..ai_client import AIError, chat, get_ai_config
from ..db import DB_PATH, get_db

router = APIRouter(tags=["gallery"])

IMG_TIMEOUT = 180.0

# 图片文件存到数据库同级目录的 images/ 下：生产即 data/images/，测试随 MOYU_DB 隔离
IMAGES_DIR = DB_PATH.parent / "images"


def _one(sql, args=()):
    row = get_db().execute(sql, args).fetchone()
    if row is None:
        raise HTTPException(404, "资源不存在")
    return dict(row)


def _all(sql, args=()):
    return [dict(r) for r in get_db().execute(sql, args).fetchall()]


def _img_config() -> dict:
    rows = get_db().execute(
        "SELECT key, value FROM app_settings WHERE key LIKE 'img_%'").fetchall()
    return {r["key"]: r["value"] for r in rows}


def _check_img_config(cfg: dict) -> dict:
    if not (cfg.get("img_base_url") or "").strip() or not (cfg.get("img_api_key") or "").strip():
        raise HTTPException(400, "尚未配置生图接口：请到「系统设置 · 生图接口（丹青阁）」填写 Base URL 与 API Key")
    if not (cfg.get("img_model") or "").strip():
        raise HTTPException(400, "尚未配置生图模型：请到「系统设置 · 生图接口（丹青阁）」填写模型名")
    return cfg


def _img_client(cfg: dict, timeout: float = IMG_TIMEOUT) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=(cfg.get("img_base_url") or "").rstrip("/"),
        headers={"Authorization": f"Bearer {cfg.get('img_api_key', '')}"},
        timeout=timeout)


def _friendly(e: Exception) -> HTTPException:
    if isinstance(e, httpx.ConnectError):
        return HTTPException(502, "无法连接生图接口，请检查 Base URL 是否正确、网络是否通畅")
    if isinstance(e, httpx.TimeoutException):
        return HTTPException(502, "生图接口请求超时，请稍后重试")
    return HTTPException(502, f"生图接口调用失败：{e}")


async def _fetch_image_bytes(cfg: dict, prompt: str, size: str) -> bytes:
    """调 OpenAI Images 兼容接口，返回 PNG 字节。失败抛 HTTPException(502)。"""
    payload = {"model": cfg["img_model"], "prompt": prompt, "size": size, "n": 1}
    try:
        async with _img_client(cfg) as c:
            resp = await c.post("/images/generations", json=payload)
    except HTTPException:
        raise
    except Exception as e:
        raise _friendly(e)
    if resp.status_code == 401:
        raise HTTPException(502, "生图 API Key 无效或已过期（401）")
    if resp.status_code == 404:
        raise HTTPException(502, "生图接口路径不存在（404），请确认 Base URL 以 /v1 结尾且服务支持 OpenAI Images 协议")
    if resp.status_code >= 400:
        raise HTTPException(502, f"生图接口返回错误（{resp.status_code}）：{resp.text[:200]}")
    try:
        item = (resp.json().get("data") or [{}])[0]
    except Exception:
        raise HTTPException(502, "生图接口返回了无法解析的内容")
    if item.get("b64_json"):
        try:
            return base64.b64decode(item["b64_json"])
        except (binascii.Error, ValueError):
            raise HTTPException(502, "生图接口返回的图片数据损坏（b64 解码失败）")
    if item.get("url"):
        try:
            async with httpx.AsyncClient(timeout=IMG_TIMEOUT) as c:
                dl = await c.get(item["url"])
        except Exception as e:
            raise _friendly(e)
        if dl.status_code >= 400:
            raise HTTPException(502, f"图片下载失败（{dl.status_code}）")
        return dl.content
    raise HTTPException(502, "生图接口未返回图片（既无 url 也无 b64_json）")


# ---------- 生图 ----------

class GenerateIn(BaseModel):
    work_id: int
    kind: str = "illustration"  # cover | illustration
    prompt: str
    size: str = ""  # 留空用设置里的 img_size


@router.post("/gallery/generate", status_code=201)
async def generate_image(body: GenerateIn):
    _one("SELECT id FROM works WHERE id=?", (body.work_id,))
    if body.kind not in ("cover", "illustration"):
        raise HTTPException(400, "kind 只能是 cover（封面）或 illustration（插图）")
    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(400, "请先填写画面描述")
    cfg = _check_img_config(_img_config())
    size = (body.size or cfg.get("img_size") or "1024x1024").strip()

    data = await _fetch_image_bytes(cfg, prompt, size)

    db = get_db()
    cur = db.execute(
        "INSERT INTO images(work_id, kind, prompt, path) VALUES (?,?,?, '')",
        (body.work_id, body.kind, prompt))
    img_id = cur.lastrowid
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    fname = f"{img_id}_{body.kind}.png"
    (IMAGES_DIR / fname).write_bytes(data)
    db.execute("UPDATE images SET path=? WHERE id=?", (fname, img_id))
    db.commit()
    return _one("SELECT * FROM images WHERE id=?", (img_id,))


# ---------- 图库 ----------

@router.get("/works/{work_id}/images")
def list_images(work_id: int):
    _one("SELECT id FROM works WHERE id=?", (work_id,))
    return _all("SELECT * FROM images WHERE work_id=? ORDER BY id DESC", (work_id,))


@router.get("/images/{image_id}/file")
def image_file(image_id: int):
    img = _one("SELECT * FROM images WHERE id=?", (image_id,))
    f = IMAGES_DIR / img["path"]
    if not img["path"] or not f.is_file():
        raise HTTPException(404, "图片文件不存在（可能已被移动或清理）")
    return FileResponse(f, media_type="image/png", filename=f"image_{image_id}.png")


@router.delete("/images/{image_id}", status_code=204)
def delete_image(image_id: int):
    img = _one("SELECT * FROM images WHERE id=?", (image_id,))
    db = get_db()
    db.execute("DELETE FROM images WHERE id=?", (image_id,))
    # 若该图是作品当前封面，顺带清空封面
    db.execute("UPDATE works SET cover_image='' WHERE cover_image=?", (str(image_id),))
    db.commit()
    if img["path"]:
        f = IMAGES_DIR / img["path"]
        if f.is_file():
            f.unlink()


# ---------- 作品封面 ----------

class CoverIn(BaseModel):
    image_id: int


@router.post("/works/{work_id}/cover")
def set_cover(work_id: int, body: CoverIn):
    _one("SELECT id FROM works WHERE id=?", (work_id,))
    img = _one("SELECT * FROM images WHERE id=?", (body.image_id,))
    if img["work_id"] != work_id:
        raise HTTPException(400, "该图片不属于此作品")
    db = get_db()
    db.execute("UPDATE works SET cover_image=?, updated_at=datetime('now','localtime') WHERE id=?",
               (str(body.image_id), work_id))
    db.commit()
    return _one("SELECT * FROM works WHERE id=?", (work_id,))


# ---------- 配置测试 ----------

@router.post("/gallery/test")
async def test_connection():
    cfg = _img_config()
    if not (cfg.get("img_base_url") or "").strip() or not (cfg.get("img_api_key") or "").strip():
        return {"ok": False, "message": "尚未填写 Base URL 或 API Key"}
    try:
        # 用 /models 做轻量连通性验证（OpenAI 兼容服务普遍支持），不真正消耗生图额度
        async with _img_client(cfg, timeout=15.0) as c:
            resp = await c.get("/models")
        if resp.status_code == 200:
            return {"ok": True, "message": "连接成功，接口可用"}
        if resp.status_code == 401:
            return {"ok": False, "message": "API Key 无效（401）"}
        return {"ok": False, "message": f"接口可达但返回异常（{resp.status_code}），请确认服务支持 OpenAI Images 协议"}
    except HTTPException:
        raise
    except Exception as e:
        return {"ok": False, "message": str(_friendly(e).detail)}


# ---------- AI 代写画面描述 ----------

class PromptSuggestIn(BaseModel):
    work_id: int
    kind: str = "illustration"


@router.post("/gallery/prompt-suggest")
async def prompt_suggest(body: PromptSuggestIn):
    work = _one("SELECT * FROM works WHERE id=?", (body.work_id,))
    cfg = get_ai_config()
    if not (cfg.get("ai_api_key") or "").strip() or not (cfg.get("ai_model") or "").strip():
        raise HTTPException(400, "未配置文字 AI 接口，请先到「系统设置 · AI 模型配置」填写后再使用 AI 代写")
    kind_label = "小说封面" if body.kind == "cover" else "小说插图"
    sys_prompt = (
        "你是一位专业的 AI 绘画提示词撰稿人。请根据作品信息为文生图模型撰写一条中文画面描述，"
        "要求：具象、有画面感，包含主体、环境、光线、色调与风格关键词；"
        "只输出这一条描述本身，不要任何解释、标题或引号；控制在 120 字以内。")
    user = (f"请为以下作品写一条{kind_label}的画面描述。\n"
            f"书名：《{work['title']}》\n"
            f"类型：{work.get('genre') or '未分类'}\n"
            f"简介：{work.get('intro') or '（暂无简介）'}")
    try:
        text, _ = await chat(
            [{"role": "system", "content": sys_prompt},
             {"role": "user", "content": user}], cfg, max_tokens=300)
    except AIError as e:
        raise HTTPException(502, str(e))
    text = text.strip().strip('"「」')
    if not text:
        raise HTTPException(502, "AI 没有返回有效描述，请重试")
    return {"prompt": text}
