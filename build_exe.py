# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者

# Licensed under the MIT License. See LICENSE.

"""PyInstaller 打包入口脚本：

- 支持单文件模式（默认）与目录模式（--onedir）

- 开启 --noconsole 消除控制台黑框，接入 WebView2 原生桌面视窗

- 临时目录注入静态资源版本戳 ?v=<VERSION>，保护工作区源码纯净

- 自动生成 SHA256 校验文件与 release manifest.json

"""

import hashlib

import json

import re

import shutil


import sys
# 兼容海外/英文 Windows 控制台编码 (cp1252)
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import subprocess

import sys

import tempfile

from pathlib import Path



BASE = Path(__file__).resolve().parent

from app.version import APP_VERSION

VERSION = APP_VERSION

PLATFORM = "win64"





def _write_version_file() -> Path:

    path = BASE / "build" / "version.txt"

    path.parent.mkdir(parents=True, exist_ok=True)

    parts = [int(x) for x in VERSION.split(".")]

    parts += [0] * (4 - len(parts))

    content = f"""# UTF-8

VSVersionInfo(

  ffi=FixedFileInfo(

    filevers=({', '.join(map(str, parts))}, 0),

    prodvers=({', '.join(map(str, parts))}, 0),

    mask=0x3f,

    flags=0x0,

    OS=0x40004,

    fileType=0x1,

    subtype=0x0,

    date=(0, 0)

  ),

  kids=[

    StringFileInfo(

      [StringTable('080404b0', [

        StringStruct('CompanyName', '墨语MoYu团队'),

        StringStruct('FileDescription', '墨语MoYu · 本地 AI 长篇小说创作工作台'),

        StringStruct('FileVersion', '{VERSION}'),

        StringStruct('InternalName', 'MoYu'),

        StringStruct('LegalCopyright', 'Copyright (c) 2026 MoYu contributors'),

        StringStruct('OriginalFilename', '墨语MoYu-v{VERSION}-{PLATFORM}.exe'),

        StringStruct('ProductName', '墨语MoYu'),

        StringStruct('ProductVersion', '{VERSION}')])

    ]),

    VarFileInfo([VarStruct('Translation', [2052, 1200])])

  ]

)

"""

    path.write_text(content, encoding="utf-8")

    return path





def _sha256(path: Path) -> str:

    digest = hashlib.sha256()

    with path.open("rb") as stream:

        for chunk in iter(lambda: stream.read(8192), b""):

            digest.update(chunk)

    return digest.hexdigest()





def _prepare_static_temp(temp_dir: Path) -> Path:

    """在临时目录拷贝 static 并在其 index.html 中注入 ?v=<VERSION> 缓存戳，绝不污染源码工作区。"""

    st_dest = temp_dir / "static"

    shutil.copytree(BASE / "static", st_dest)

    idx_path = st_dest / "index.html"

    if idx_path.exists():

        html = idx_path.read_text(encoding="utf-8")

        html = re.sub(r'(\.(?:css|js|svg|png|ico))\?v=[a-zA-Z0-9_\.]+', r'\1?v=' + VERSION, html)

        idx_path.write_text(html, encoding="utf-8")

    return st_dest





def main():

    onedir = "--onedir" in sys.argv

    build_spec_name = f"MoYu-v{VERSION}-{PLATFORM}"

    final_display_name = f"墨语MoYu-v{VERSION}-{PLATFORM}"



    version_file = _write_version_file()

    dist_dir = BASE / "dist"

    build_dir = BASE / "build" / "pyinstaller"



    with tempfile.TemporaryDirectory(prefix="moyu_pack_") as temp_str:

        temp_dir = Path(temp_str)

        st_data_dir = _prepare_static_temp(temp_dir)



        cmd = [

            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",

            "--noconsole",  # 消除控制台黑色窗口

            "--name", build_spec_name,

            "--version-file", str(version_file),

            *(["--icon", str(icon_path)] if (icon_path := (BASE / "static" / "icon.ico" if (BASE / "static" / "icon.ico").exists() else BASE / "build" / "icon.ico")).exists() else []),

            "--add-data", f"{st_data_dir};static",

            "--add-data", f"{BASE / 'docs'};docs",

            "--add-data", f"{BASE / 'app'};app",

            "--collect-all", "webview",

            "--hidden-import", "clr",

            "--hidden-import", "clr_loader",

            "--hidden-import", "pythonnet",

            "--hidden-import", "webview.platforms.winforms",

            "--hidden-import", "webview.platforms.edgechromium",

            "--hidden-import", "uvicorn.logging",

            "--hidden-import", "uvicorn.loops.auto",

            "--hidden-import", "uvicorn.protocols.http.auto",

            "--hidden-import", "uvicorn.protocols.websockets.auto",

            "--hidden-import", "uvicorn.lifespan.on",

            "--distpath", str(dist_dir),

            "--workpath", str(build_dir),

            "--onedir" if onedir else "--onefile",

            str(BASE / "moyu_entry.py"),

        ]

        print("执行打包命令:", " ".join(cmd))

        subprocess.run(cmd, cwd=BASE, check=True)



    built_raw = dist_dir / build_spec_name / f"{build_spec_name}.exe" if onedir else dist_dir / f"{build_spec_name}.exe"

    final_exe = dist_dir / final_display_name / f"{final_display_name}.exe" if onedir else dist_dir / f"{final_display_name}.exe"



    if onedir:

        if (dist_dir / final_display_name).exists():

            shutil.rmtree(dist_dir / final_display_name)

        (dist_dir / build_spec_name).rename(dist_dir / final_display_name)

        (dist_dir / final_display_name / f"{build_spec_name}.exe").rename(final_exe)

    else:

        if final_exe.exists():

            final_exe.unlink()

        built_raw.rename(final_exe)



    checksum = _sha256(final_exe)

    (dist_dir / f"{final_display_name}.sha256").write_text(

        f"{checksum}  {final_exe.name}\n", encoding="utf-8")

    manifest = {

        "name": "墨语MoYu",

        "version": VERSION,

        "platform": PLATFORM,

        "filename": final_exe.name,

        "sha256": checksum,

        "released_at": None,

        "download_url": f"https://github.com/GitHubAres/MoYu/releases/download/v{VERSION}/{final_exe.name}",

        "channel": "stable",

    }

    (dist_dir / "manifest.json").write_text(

        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n构建成功！输出文件: {final_exe}")

    print(f"SHA256: {checksum}")

    print(f"发布清单: {dist_dir / 'manifest.json'}")

    print("运行方式: 双击 exe 启动（数据持久化在 exe 同级的 data/ 目录）")





if __name__ == "__main__":

    main()







