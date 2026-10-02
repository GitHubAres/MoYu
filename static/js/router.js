/* Hash 路由：页面模块通过 registerPage(name, renderFn) 注册 */
const router = {
  pages: {},
  current: null,

  register(name, renderFn) { this.pages[name] = renderFn; },

  parse() {
    const hash = location.hash.slice(2) || "bookshelf"; // 去掉 '#/'
    const [pathPart, queryPart] = hash.split("?");
    const segs = pathPart.split("/").filter(Boolean);
    const params = new URLSearchParams(queryPart || "");
    return { name: segs[0] || "bookshelf", segs, params };
  },

  async dispatch() {
    const view = document.getElementById("view");
    const { name, segs, params } = this.parse();
    const fn = this.pages[name] || this.pages.bookshelf;
    this.current = name;

    const sidebar = document.getElementById("sidebar-drawer");
    const header = document.querySelector("header");
    const fab = document.getElementById("global-quick-note-fab");

    if (name === "login") {
      if (view) view.classList.remove("pt-16");
      if (sidebar) sidebar.classList.add("hidden");
      if (header) header.classList.add("hidden");
      if (fab) fab.classList.add("hidden");
    } else {
      if (view) view.classList.add("pt-16");
      if (sidebar) sidebar.classList.remove("hidden");
      if (header) header.classList.remove("hidden");
      if (fab) fab.classList.remove("hidden");
    }

    document.querySelectorAll(".nav-item").forEach((a) => {
      const active = a.dataset.route === name;
      a.classList.toggle("bg-primary-container", active);
      a.classList.toggle("text-on-primary-container", active);
      a.classList.toggle("font-semibold", active);
      a.classList.toggle("text-on-surface-variant", !active);
    });
    ui.setCrumb();
    ui.setActions();
    ui.setSaveIndicator(null);
    document.getElementById("modal-root").innerHTML = "";
    if (view) view.innerHTML = "";
    try {
      await fn(view, { segs: segs.slice(1), params });
    } catch (e) {
      console.error(e);
      if (view) view.append(ui.el("div", { class: "p-space-xl text-error font-body-md" }, "页面加载失败：" + e.message));
    }
    ui.refreshStats();
  },

  start() {
    window.addEventListener("hashchange", () => this.dispatch());
    this.dispatch();
  },
};

function registerPage(name, fn) { router.register(name, fn); }
