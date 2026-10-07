/* 应用启动：路由启动 + 鉴权拦截 + 主题加载 + 网络感知 */
(async function () {
  // 全局离线与在线状态感知
  window.addEventListener("offline", () => {
    ui.toast("网络连接已断开，本地编辑内容将自动暂存在浏览器中", "err");
  });
  window.addEventListener("online", () => {
    ui.toast("网络连接已恢复", "ok");
  });

  // 全局快捷键：Ctrl+K / Cmd+K 命令面板
  window.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
      e.preventDefault();
      ui.palette();
    }
  });


  // 移动端侧边抽屉导航控制
  const drawer = document.getElementById("sidebar-drawer");
  const backdrop = document.getElementById("sidebar-backdrop");
  const menuBtn = document.getElementById("mobile-menu-btn");

  function openDrawer() {
    if (drawer) drawer.classList.remove("-translate-x-full");
    if (backdrop) backdrop.classList.add("active");
  }
  function closeDrawer() {
    if (drawer) drawer.classList.add("-translate-x-full");
    if (backdrop) backdrop.classList.remove("active");
  }

  if (menuBtn) menuBtn.addEventListener("click", openDrawer);
  if (backdrop) backdrop.addEventListener("click", closeDrawer);

  const navItems = document.querySelectorAll("#sidebar-drawer a.nav-item");
  navItems.forEach((item) => {
    item.addEventListener("click", () => {
      if (window.innerWidth < 1024) closeDrawer();
    });
  });

  // 检查并弹出系统公告（失败绝不阻塞主流程）
  if (window.announcement && window.announcement.checkOnBoot) {
    try { await window.announcement.checkOnBoot(); } catch (e) { console.debug("Announcement checkOnBoot error:", e); }
  }

  // 1. 先启动路由系统
  router.start();

  // 2. 检查云端登录鉴权状态
  try {
    const authStatus = await api.get("/auth/status");
    if (!authStatus.is_desktop && authStatus.enabled && !authStatus.authenticated) {
      location.hash = "#/login";
      router.dispatch();
      return;
    }
    // 已登录或无需鉴权时，拉取用户设置与主题
    const settings = await api.get("/settings");
    ui.applyTheme(settings.theme || "light");
  } catch (e) {
    console.error("Auth status or settings check failed", e);
  }
})();
