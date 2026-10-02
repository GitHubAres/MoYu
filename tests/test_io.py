# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""导入导出：TXT 全书导出、TXT 拆章导入 preview + confirm。"""
from pathlib import Path

from conftest import make_wvc


def test_export_txt_full_book(client):
    w, v, c = make_wvc(client, "导出测试书")
    client.patch(f"/api/chapters/{c['id']}", json={
        "title": "第一章 风起", "content": "正文第一段。\n\n正文第二段。"})

    r = client.post("/api/export", json={"work_id": w["id"], "format": "txt"})
    assert r.status_code == 201
    rec = r.json()
    assert rec["status"] == "done"
    assert rec["word_count"] == 12  # 两段正文去空白后各 6 字
    assert rec["size"] > 0

    path = Path(rec["path"])
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "《导出测试书》" in text
    assert "第一章 风起" in text
    assert "正文第一段。" in text

    # 下载接口可用
    r = client.get(f"/api/exports/{rec['id']}/download")
    assert r.status_code == 200
    assert "第一章 风起" in r.content.decode("utf-8")

    # 列表可查；删除后文件与记录一并清除
    lst = client.get("/api/exports", params={"work_id": w["id"]}).json()
    assert [x["id"] for x in lst] == [rec["id"]]
    assert client.delete(f"/api/exports/{rec['id']}").status_code == 204
    assert not path.exists()


def test_export_empty_scope_fails(client):
    w, v, _ = make_wvc(client, "空范围测试")
    # 指定一个不存在的章节 id 范围 → 没有可导出章节 → failed
    r = client.post("/api/export", json={
        "work_id": w["id"], "format": "txt",
        "scope": {"type": "chapters", "ids": [99999]}})
    assert r.status_code == 201
    assert r.json()["status"] == "failed"
    assert r.json()["error"]

    assert client.post("/api/export", json={
        "work_id": w["id"], "format": "pdf"}).status_code == 400


SAMPLE_TXT = "第一章 风起\n正文第一段。\n\n第二章 云涌\n正文第二段，稍长一些。"


def test_import_preview_and_confirm(client):
    r = client.post("/api/import/preview",
                    files={"file": ("测试导入.txt", SAMPLE_TXT.encode("utf-8"), "text/plain")})
    assert r.status_code == 200
    prev = r.json()
    assert prev["title"] == "测试导入"
    assert [ch["title"] for ch in prev["chapters"]] == ["第一章 风起", "第二章 云涌"]
    assert prev["total_words"] > 0
    token = prev["file_token"]

    # confirm 入库：自动建 作品 + 卷一 + 两章
    r = client.post("/api/import/confirm", json={"file_token": token, "title": "导入的书"})
    assert r.status_code == 201
    work = r.json()
    assert work["title"] == "导入的书"
    assert work["chapter_count"] == 2

    tree = client.get(f"/api/works/{work['id']}/tree").json()
    assert len(tree) == 1
    assert [ch["title"] for ch in tree[0]["chapters"]] == ["第一章 风起", "第二章 云涌"]
    ch0 = client.get(f"/api/chapters/{tree[0]['chapters'][0]['id']}").json()
    assert "正文第一段。" in ch0["content"]
    assert ch0["word_count"] > 0

    # token 已消费（暂存文件被删除），重复 confirm 404
    assert client.post("/api/import/confirm", json={
        "file_token": token, "title": "再来一本"}).status_code == 404


def test_import_preview_partial_select(client):
    r = client.post("/api/import/preview",
                    files={"file": ("节选.txt", SAMPLE_TXT.encode("utf-8"), "text/plain")})
    token = r.json()["file_token"]
    r = client.post("/api/import/confirm", json={
        "file_token": token, "title": "只导第二章", "chapter_ids": [2]})
    assert r.status_code == 201
    assert r.json()["chapter_count"] == 1
    tree = client.get(f"/api/works/{r.json()['id']}/tree").json()
    assert [ch["title"] for ch in tree[0]["chapters"]] == ["第二章 云涌"]


def test_import_preview_rejects_bad_input(client):
    # 不支持的扩展名
    r = client.post("/api/import/preview",
                    files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 400
    # 空文件
    r = client.post("/api/import/preview",
                    files={"file": ("x.txt", b"", "text/plain")})
    assert r.status_code == 400

def test_export_epub_full_book(client):
    import zipfile
    w, v, c = make_wvc(client, "EPUB导出测试书")
    client.patch(f"/api/chapters/{c['id']}", json={
        "title": "第一章 初入仙门", "content": "修仙之路漫漫。\n\n唯道心坚定者可达彼岸。"})

    r = client.post("/api/export", json={"work_id": w["id"], "format": "epub"})
    assert r.status_code == 201
    rec = r.json()
    assert rec["status"] == "done"
    assert rec["word_count"] > 0
    assert rec["size"] > 0

    path = Path(rec["path"])
    assert path.is_file()

    with zipfile.ZipFile(str(path), "r") as zf:
        names = zf.namelist()
        assert names[0] == "mimetype"
        assert zf.read("mimetype") == b"application/epub+zip"
        assert "META-INF/container.xml" in names
        assert "OEBPS/content.opf" in names
        assert "OEBPS/toc.ncx" in names
        assert "OEBPS/style.css" in names
        assert "OEBPS/chapter_0001.xhtml" in names

        chap_content = zf.read("OEBPS/chapter_0001.xhtml").decode("utf-8")
        assert "第一章 初入仙门" in chap_content
        assert "修仙之路漫漫。" in chap_content

    assert client.delete(f"/api/exports/{rec['id']}").status_code == 204
    assert not path.exists()

