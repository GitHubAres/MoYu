# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""炼丹炉 API。"""
from app.features import get_alchemy_engine

router = get_alchemy_engine().build_router()
