# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""AI 助手 API。"""
from app.features import get_orchestrator

router = get_orchestrator().build_router()
