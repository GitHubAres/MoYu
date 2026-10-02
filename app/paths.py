# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""路径解析：开发模式、Docker/VPS 模式与 PyInstaller 冻结模式兼容。"""
import os
import sys
from pathlib import Path

# 判断是否为 Windows PyInstaller 原生打包桌面应用
IS_DESKTOP_EXE = getattr(sys, "frozen", False)

if IS_DESKTOP_EXE:
    # 打包后：静态资源在临时解包目录，数据在 exe 旁
    RESOURCE_DIR = Path(sys._MEIPASS)
    EXE_DIR = Path(sys.executable).resolve().parent
else:
    RESOURCE_DIR = Path(__file__).resolve().parent.parent
    EXE_DIR = RESOURCE_DIR

STATIC_DIR = RESOURCE_DIR / "static"

# 支持通过环境变量 MOYU_DATA_DIR 自定义数据存储目录（适用于 Docker 卷与 VPS 部署）
env_data_dir = os.environ.get("MOYU_DATA_DIR")
if env_data_dir:
    DATA_DIR = Path(env_data_dir).resolve()
else:
    DATA_DIR = EXE_DIR / "data"