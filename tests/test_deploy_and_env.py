import os
from fastapi.testclient import TestClient
from app.main import create_app
import app.paths as paths

def test_api_health_endpoint():
    """验证健康检查端点 /api/health 返回 200 及版本信息。"""
    app = create_app()
    client = TestClient(app)
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["status"] == "ok"
    assert "moyu" in data["app"]
    assert "version" in data

def test_custom_data_dir_env(tmp_path, monkeypatch):
    """验证 MOYU_DATA_DIR 环境变量能否正确覆盖数据存储路径。"""
    custom_dir = tmp_path / "custom_data"
    monkeypatch.setenv("MOYU_DATA_DIR", str(custom_dir))
    
    import importlib
    importlib.reload(paths)
    assert paths.DATA_DIR == custom_dir.resolve()
def test_api_version_endpoint():
    """验证版本端点 /api/version 返回 200 及当前应用版本号。"""
    app = create_app()
    client = TestClient(app)
    res = client.get("/api/version")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["version"] == "1.9.3"
