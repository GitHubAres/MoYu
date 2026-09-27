"""路径解析：开发模式与 PyInstaller 冻结模式兼容。"""
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # 打包后：静态资源在临时解包目录，数据在 exe 旁
    RESOURCE_DIR = Path(sys._MEIPASS)
    EXE_DIR = Path(sys.executable).resolve().parent
else:
    RESOURCE_DIR = Path(__file__).resolve().parent.parent
    EXE_DIR = RESOURCE_DIR

STATIC_DIR = RESOURCE_DIR / "static"
DATA_DIR = EXE_DIR / "data"
