/* 应用启动：主题加载 + 路由启动 */
(async function () {
  try {
    const settings = await api.get("/settings");
    ui.applyTheme(settings.theme || "light");
  } catch (e) {}
  // 全局快捷键：Ctrl+K / Cmd+K 打开搜索面板
  window.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
      e.preventDefault();
      ui.palette();
    }
  });
  router.start();
})();
