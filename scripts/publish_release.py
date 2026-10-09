# -*- coding: utf-8 -*-

# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT

"""本地一键推送到 GitHub Releases 脚本：

- 严格从本地 .env 读取 GITHUB_TOKEN，密钥不入库

- 自动关联 app/version.py 版本号与 dist/ 打包产物

- 自动上传可执行文件、SHA256、manifest.json 与 announcement.json

"""

import os

import sys

import json

import mimetypes

from pathlib import Path

import httpx



BASE = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(BASE))



# 1. 读取本地 .env

def load_local_env():

    env_file = BASE / ".env"

    if env_file.exists():

        for line in env_file.read_text(encoding="utf-8").splitlines():

            line = line.strip()

            if line and not line.startswith("#") and "=" in line:

                k, v = line.split("=", 1)

                os.environ.setdefault(k.strip(), v.strip())



load_local_env()



GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()

GITHUB_REPO = os.environ.get("GITHUB_REPO", "GitHubAres/MoYu").strip()



if not GITHUB_TOKEN:

    print("错误: 未在本地环境或 .env 文件中检测到 GITHUB_TOKEN！")

    print("请确认项目根目录下存在包含 GITHUB_TOKEN 的 .env 文件。")

    sys.exit(1)



from app.version import APP_VERSION



VERSION = APP_VERSION

TAG_NAME = f"v{VERSION}"

RELEASE_NAME = f"墨语 MoYu v{VERSION}"



print(f"=== 准备发布 {RELEASE_NAME} 至 {GITHUB_REPO} ===")



headers = {

    "Authorization": f"Bearer {GITHUB_TOKEN}",

    "Accept": "application/vnd.github+json",

    "X-GitHub-Api-Version": "2022-11-28",

    "User-Agent": f"MoYu-Publisher/{VERSION}",

}



def check_or_create_release():

    with httpx.Client(timeout=30.0) as client:

        # 1. 检查是否存在该 tag 的 Release

        get_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/tags/{TAG_NAME}"

        r = client.get(get_url, headers=headers)

        if r.status_code == 200:

            print(f"检测到已存在的 Release: {TAG_NAME}")

            return r.json()



        # 2. 不存在则创建新 Release

        post_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases"

        body = {

            "tag_name": TAG_NAME,

            "target_commitish": "main",

            "name": RELEASE_NAME,

            "body": f"## 墨语 MoYu {TAG_NAME} 发布说明\n\n### 新特性：Agent Skill 市场升级\n- 全面升级 Agent Skills 规范架构（SKILL.md frontmatter + 核心 Markdown 指令 + 资源挂载）；\n- 支持 references 参考文档、scripts 脚本清单与 assets 素材资源管理；\n- 彻底修复旧版提示词死占位符问题，实现服务端统一动态替换；\n- 支持 .skill 标准格式一键导入、规范校验与打包导出；\n- 写作工作台与多轮对话全面接入 Skill 注入。",

            "draft": False,

            "prerelease": ("beta" in VERSION or "rc" in VERSION),

            "generate_release_notes": True

        }

        create_res = client.post(post_url, headers=headers, json=body)

        if create_res.status_code not in (200, 201):

            print(f"创建 Release 失败: {create_res.status_code} {create_res.text}")

            sys.exit(1)

        print(f"成功创建新 Release: {TAG_NAME}")

        return create_res.json()



def upload_asset(release, file_path: Path, asset_name: str = None):

    if not file_path.exists():

        print(f"跳过不存在的文件: {file_path}")

        return



    name = asset_name or file_path.name

    # 检查是否已存在同名 asset，若存在则删除以支持覆盖更新

    existing_assets = release.get("assets", [])

    for a in existing_assets:

        if a["name"] == name:

            print(f"发现已有同名资产 {name}，正在删除以重新上传...")

            del_url = a["url"]

            with httpx.Client(timeout=30.0) as client:

                client.delete(del_url, headers=headers)



    upload_url_tmpl = release["upload_url"] # 形如 https://uploads.github.com/.../assets{?name,label}

    upload_url = upload_url_tmpl.split("{")[0] + f"?name={name}"



    content_type, _ = mimetypes.guess_type(str(file_path))

    content_type = content_type or "application/octet-stream"



    print(f"正在上传资产 {name} ({file_path.stat().st_size:,} 字节)...")

    with open(file_path, "rb") as f:

        file_bytes = f.read()



    upload_headers = dict(headers)

    upload_headers["Content-Type"] = content_type



    with httpx.Client(timeout=120.0) as client:

        r = client.post(upload_url, headers=upload_headers, content=file_bytes)

        if r.status_code in (200, 201):

            print(f"√ 资产 {name} 上传成功！")

        else:

            print(f"× 资产 {name} 上传失败: {r.status_code} {r.text[:200]}")



def main():

    release = check_or_create_release()

    dist_dir = BASE / "dist"



    # 待上传清单

    assets_to_upload = [

        dist_dir / f"墨语MoYu-v{VERSION}-win64.exe",

        dist_dir / f"墨语MoYu-v{VERSION}-win64.sha256",

        dist_dir / "manifest.json",

        BASE / "static" / "announcements" / "builtin.json",

    ]



    for asset_path in assets_to_upload:

        # 将 builtin.json 作为 announcement.json 上传到 Release 根资产供全球热拉取

        asset_name = "announcement.json" if asset_path.name == "builtin.json" else asset_path.name

        upload_asset(release, asset_path, asset_name=asset_name)



    print("\n=== 全部发布流程完成 ===")

    print(f"Release 地址: {release.get('html_url')}")



if __name__ == "__main__":

    main()

