# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""文风档案 API。"""
from app.features import get_style_engine

router = get_style_engine().build_router()
