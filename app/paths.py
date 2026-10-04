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

# 用户自定义数据目录的持久化配置（由设置页写入，重启后生效）
CONFIG_PATH = EXE_DIR / "moyu_config.json"


def _config_data_dir() -> str | None:
    """读取 moyu_config.json 中的 data_dir 字段，不存在或损坏时返回 None。"""
    try:
        import json
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        d = str(cfg.get("data_dir") or "").strip()
        return d or None
    except Exception:
        return None


# 数据目录优先级：环境变量 MOYU_DATA_DIR > moyu_config.json 自定义 > 默认 EXE 旁 data/
env_data_dir = os.environ.get("MOYU_DATA_DIR")
if env_data_dir:
    DATA_DIR = Path(env_data_dir).resolve()
else:
    _cfg_dir = _config_data_dir()
    DATA_DIR = Path(_cfg_dir).resolve() if _cfg_dir else EXE_DIR / "data"