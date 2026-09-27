"""PyInstaller 打包脚本：uv run python build_exe.py [--onedir]

默认 onefile 模式：dist/墨语MoYu.exe 单文件，可随意拷贝分发（启动稍慢、体积更大）。
--onedir 模式：dist/墨语MoYu/墨语MoYu.exe 文件夹形态，启动更快。
首次使用：uv pip install pyinstaller
"""
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent


def main():
    onedir = "--onedir" in sys.argv
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", "墨语MoYu",
        "--onedir" if onedir else "--onefile",
        "--add-data", "static;static",
        "--add-data", "docs;docs",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespan.on",
        "moyu_entry.py",
    ]
    subprocess.run(cmd, cwd=BASE, check=True)
    if onedir:
        print("\n打包完成：dist/墨语MoYu/墨语MoYu.exe")
    else:
        print("\n打包完成：dist/墨语MoYu.exe")
    print("数据目录：exe 旁的 data/（自动创建）")


if __name__ == "__main__":
    main()
