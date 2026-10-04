# -*- coding: utf-8 -*-
# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""v1.7.9 数据目录自定义：设置路由 /settings/data-dir 的验收测试。"""

import json

import pytest

import app.api.prefs as prefs


@pytest.fixture
def cfg_tmp(tmp_path, monkeypatch):
    """把配置文件与数据目录引用重定向到临时目录，避免污染真实工程目录。"""
    cfg = tmp_path / "moyu_config.json"
    monkeypatch.setattr(prefs, "CONFIG_PATH", cfg)
    src = tmp_path / "old_data"
    src.mkdir()
    monkeypatch.setattr(prefs, "DATA_DIR", src)
    db_file = src / "moyu.db"
    db_file.write_bytes(b"fake-db-bytes")
    monkeypatch.setattr(prefs, "DB_PATH", db_file)
    return {"cfg": cfg, "src": src, "db": db_file, "tmp": tmp_path}


def test_get_data_dir_defaults(client, cfg_tmp):
    r = client.get("/api/settings/data-dir")
    assert r.status_code == 200
    data = r.json()
    assert data["current"] == str(cfg_tmp["src"])
    assert data["custom"] is None
    assert data["env_override"] is False
    assert data["default"]
    assert data["db_path"] == str(cfg_tmp["db"])


def test_set_data_dir_validation(client, cfg_tmp):
    r = client.post("/api/settings/data-dir", json={"path": ""})
    assert r.status_code == 400
    r = client.post("/api/settings/data-dir", json={"path": "relative/dir"})
    assert r.status_code == 400


def test_set_data_dir_with_migrate(client, cfg_tmp):
    (cfg_tmp["src"] / "exports").mkdir()
    (cfg_tmp["src"] / "exports" / "a.txt").write_text("x", encoding="utf-8")
    target = cfg_tmp["tmp"] / "new_data"
    r = client.post("/api/settings/data-dir", json={"path": str(target), "migrate": True})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True and data["need_restart"] is True
    assert "moyu.db" in data["migrated"]
    assert "exports" in data["migrated"]
    assert (target / "moyu.db").read_bytes() == b"fake-db-bytes"
    assert (target / "exports" / "a.txt").read_text(encoding="utf-8") == "x"
    cfg = json.loads(cfg_tmp["cfg"].read_text(encoding="utf-8"))
    assert cfg["data_dir"] == str(target)
    g = client.get("/api/settings/data-dir").json()
    assert g["custom"] == str(target)


def test_set_data_dir_migrate_skips_existing(client, cfg_tmp):
    target = cfg_tmp["tmp"] / "new_data"
    target.mkdir()
    (target / "moyu.db").write_bytes(b"existing")
    r = client.post("/api/settings/data-dir", json={"path": str(target), "migrate": True})
    assert r.status_code == 200
    data = r.json()
    assert "moyu.db" in data["skipped"]
    assert (target / "moyu.db").read_bytes() == b"existing"


def test_reset_data_dir(client, cfg_tmp):
    target = cfg_tmp["tmp"] / "new_data"
    client.post("/api/settings/data-dir", json={"path": str(target), "migrate": False})
    assert cfg_tmp["cfg"].exists()
    r = client.delete("/api/settings/data-dir")
    assert r.status_code == 200
    assert r.json()["need_restart"] is True
    if cfg_tmp["cfg"].exists():
        assert "data_dir" not in json.loads(cfg_tmp["cfg"].read_text(encoding="utf-8"))


def test_env_override_blocks_set(client, cfg_tmp, monkeypatch):
    monkeypatch.setenv("MOYU_DATA_DIR", str(cfg_tmp["tmp"] / "env_data"))
    r = client.post("/api/settings/data-dir", json={"path": str(cfg_tmp["tmp"] / "new_data")})
    assert r.status_code == 400
    g = client.get("/api/settings/data-dir").json()
    assert g["env_override"] is True
