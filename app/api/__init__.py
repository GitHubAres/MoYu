# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""API 路由汇总。"""
from fastapi import APIRouter

from ..version import APP_VERSION

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True, "status": "ok", "app": "moyu-local", "version": APP_VERSION}


@router.get("/version")
def version():
    return {"ok": True, "app": "moyu-local", "version": APP_VERSION}


from . import (ai, alchemy, announcement, audit, auth, board, chat, entities, gallery, graph,  # noqa: E402
               io_export, notes, outlines, prefs, skills,
               search, seed, style, tasks, timeline, update, versions, works)

for _m in (auth, prefs, works, ai, chat, outlines, entities, versions, board,
           io_export, skills, audit, seed, notes, search,
           graph, timeline, style, alchemy, gallery, tasks, update, announcement):
    router.include_router(_m.router)
