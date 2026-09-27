"""API 路由汇总。"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True, "app": "moyu-local"}


from . import (ai, alchemy, audit, board, entities, gallery, graph,  # noqa: E402
               io_export, notes, outlines, prefs, prompts_api, search,
               seed, style, timeline, versions, works)

for _m in (prefs, works, ai, outlines, entities, versions, board,
           io_export, prompts_api, audit, seed, notes, search,
           graph, timeline, style, alchemy, gallery):
    router.include_router(_m.router)
