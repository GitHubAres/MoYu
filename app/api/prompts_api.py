# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""提示词中心 API。"""
from app.features import get_prompt_library

router = get_prompt_library().build_router()
