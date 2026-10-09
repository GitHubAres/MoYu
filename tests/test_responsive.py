import re
from fastapi.testclient import TestClient
from app.main import create_app

def test_responsive_meta_and_layout_structure():
    """验证全局 viewport、侧边抽屉、顶栏汉堡按钮与内容区自适应属性。"""
    app = create_app()
    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    html = res.text

    # 1. 确认 viewport meta 标签
    assert 'name="viewport"' in html
    assert "width=device-width" in html
    assert "viewport-fit=cover" in html

    # 2. 确认侧边栏抽屉与遮罩
    assert 'id="sidebar-drawer"' in html
    assert "-translate-x-full" in html
    assert "lg:translate-x-0" in html
    assert 'id="sidebar-backdrop"' in html
    assert "drawer-backdrop" in html

    # 3. 确认顶栏与汉堡按钮
    assert 'id="mobile-menu-btn"' in html
    assert "lg:hidden" in html
    assert "left-0" in html
    assert "lg:left-64" in html

    # 4. 确认主容器自适应
    assert "pl-0 lg:pl-64" in html
    assert "id=\"view\"" in html

def test_responsive_css_rules():
    """验证 CSS 中防横向溢出与触屏保底规则。"""
    app = create_app()
    client = TestClient(app)
    res = client.get("/static/css/app.css")
    assert res.status_code == 200
    css = res.text

    assert "overflow-x: hidden" in css
    assert "-webkit-text-size-adjust: 100%" in css
    assert ".drawer-backdrop" in css
    assert "@media (hover: none)" in css

def test_workbench_responsive_elements():
    """验证写作工作台支持移动端抽屉与自适应布局。"""
    with open("static/js/pages/workbench.js", "r", encoding="utf-8") as f:
        js = f.read()

    assert "openMobileDrawer" in js
    assert "closeMobileDrawers" in js
    assert "mobileWorkbenchBar" in js
    assert "drawer-backdrop lg:hidden" in js
    assert "col-span-12 lg:col-span-6" in js
    assert "grid-cols-1 sm:grid-cols-2" in js

def test_ui_components_responsive_max_widths():
    """验证全局弹窗与面板使用动态 max-w，防止移动端横向撑裂。"""
    with open("static/js/ui.js", "r", encoding="utf-8") as f:
        js = f.read()

    # confirm 与 prompt 弹窗 max-w
    assert "max-w-[calc(100vw-2rem)]" in js
    # palette 搜索面板
    assert "max-w-[calc(100vw-1.5rem)]" in js
    # 触控按钮最小高度
    assert "min-h-[44px]" in js

def test_touch_target_and_fluid_css_rules():
    """验证 v1.2.3 触控热区与流式排版规范已写入 app.css。"""
    with open("static/css/app.css", "r", encoding="utf-8") as f:
        css = f.read()
    assert ".touch-target" in css
    assert "min-width: 44px" in css
    assert "min-height: 44px" in css
    assert "clamp(" in css