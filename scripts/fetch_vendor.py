"""下载前端外部依赖到 static/vendor/，实现完全离线运行。

国内网络环境：Tailwind 走 npmmirror，字体走 fonts.googleapis.cn。
用法：uv run python scripts/fetch_vendor.py
"""
import io
import json
import re
import tarfile
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
VENDOR = BASE / "static" / "vendor"
FONTS = VENDOR / "fonts"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

CSS_URLS = [
    ("fonts-text", "https://fonts.googleapis.cn/css2?"
                   "family=Noto+Serif+SC:wght@400;600;700&"
                   "family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap"),
    ("fonts-icons", "https://fonts.googleapis.cn/css2?"
                    "family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@"
                    "20..48,100..700,0..1,-50..200&display=swap"),
]


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def fetch_tailwind_browser():
    """从 npmmirror 取 @tailwindcss/browser 最新版的运行时 JS。"""
    meta = json.loads(fetch("https://registry.npmmirror.com/@tailwindcss/browser"))
    ver = meta["dist-tags"]["latest"]
    tarball_url = meta["versions"][ver]["dist"]["tarball"]
    print(f"下载 @tailwindcss/browser@{ver} ...")
    data = fetch(tarball_url)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for m in tf.getmembers():
            if m.name.endswith(("index.global.js", "dist/index.js")) and "dist" in m.name:
                content = tf.extractfile(m).read()
                (VENDOR / "tailwind.js").write_bytes(content)
                print(f"  -> {m.name} ({len(content)//1024} KB)")
                return
    raise RuntimeError("包内未找到浏览器运行时文件")


def fetch_fonts():
    css_out = []
    counter = 0
    for name, url in CSS_URLS:
        print(f"下载 {name} CSS ...")
        css = fetch(url).decode("utf-8")
        for m in sorted(set(re.findall(r"url\((https://[^)]+)\)", css))):
            counter += 1
            ext = m.rsplit(".", 1)[-1]
            fname = f"{name}-{counter:03d}.{ext}"
            dest = FONTS / fname
            if not dest.exists():
                dest.write_bytes(fetch(m))
            css = css.replace(m, f"fonts/{fname}")
        css_out.append(f"/* {name} */\n{css}")
    (VENDOR / "fonts.css").write_text("\n".join(css_out), encoding="utf-8")
    print(f"字体完成：{counter} 个文件")


def main():
    VENDOR.mkdir(parents=True, exist_ok=True)
    FONTS.mkdir(parents=True, exist_ok=True)
    fetch_tailwind_browser()
    fetch_fonts()
    print(f"全部完成 -> {VENDOR}")


if __name__ == "__main__":
    main()
