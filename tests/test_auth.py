import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.db import get_db, _reset_conn

def test_auth_full_lifecycle(tmp_path, monkeypatch):
    test_db = tmp_path / "test_auth.db"
    monkeypatch.setenv("MOYU_DB", str(test_db))
    monkeypatch.setenv("MOYU_CLOUD", "1")
    _reset_conn()

    app = create_app()
    client = TestClient(app)

    # 1. 云端模式初始状态：强制要求鉴权，但尚未初始化
    res = client.get("/api/auth/status")
    assert res.status_code == 200
    st = res.json()
    assert st["initialized"] is False
    assert st["enabled"] is True
    assert st["authenticated"] is False

    # 2. 首次初始化管理员
    res = client.post("/api/auth/init", json={"username": "author", "password": "securepassword123"})
    assert res.status_code == 200
    assert res.json()["ok"] is True

    # 3. 再次查询状态：已初始化、已启用、且已通过 Cookie 自动登录
    res = client.get("/api/auth/status")
    st = res.json()
    assert st["initialized"] is True
    assert st["enabled"] is True
    assert st["authenticated"] is True
    assert st["username"] == "author"

    # 4. 退出登录
    res = client.post("/api/auth/logout")
    assert res.status_code == 200

    # 5. 退出后访问受保护接口返回 401
    res = client.get("/api/works")
    assert res.status_code == 401

    # 6. 使用错误密码登录失败
    res = client.post("/api/auth/login", json={"username": "author", "password": "wrongpassword"})
    assert res.status_code == 401

    # 7. 正确密码登录成功
    res = client.post("/api/auth/login", json={"username": "author", "password": "securepassword123"})
    assert res.status_code == 200
    assert res.json()["ok"] is True

    # 8. 恢复访问权限
    res = client.get("/api/works")
    assert res.status_code == 200

    # 9. 清理测试库
    conn = get_db()
    conn.execute("DELETE FROM app_settings WHERE key IN ('auth_enabled', 'auth_username', 'auth_password')")
    conn.commit()
    _reset_conn()