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
    const { name, segs, params } = this.parse();
    const fn = this.pages[name] || this.pages.bookshelf;
    this.current = name;
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
    const view = document.getElementById("view");
    view.innerHTML = "";
    try {
      await fn(view, { segs: segs.slice(1), params });
    } catch (e) {
      console.error(e);
      view.append(ui.el("div", { class: "p-space-xl text-error font-body-md" }, "页面加载失败：" + e.message));
    }
    ui.refreshStats();
  },

  start() {
    window.addEventListener("hashchange", () => this.dispatch());
    this.dispatch();
  },
};

function registerPage(name, fn) { router.register(name, fn); }
