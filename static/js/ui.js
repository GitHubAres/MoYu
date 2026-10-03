/* UI 工具函数 */
const ui = {
  /* 创建元素：ui.el('div', {class:'...', onclick:fn}, 子节点...) */
  el(tag, attrs, ...children) {
    const node = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (k === "class") node.className = v;
        else if (k.startsWith("on") && typeof v === "function")
          node.addEventListener(k.slice(2), v);
        else if (k === "html") node.innerHTML = v;
        else if (v !== null && v !== undefined) node.setAttribute(k, v);
      }
    }
    for (const c of children.flat(Infinity)) {
      if (c === null || c === undefined || c === false) continue;
      node.append(c.nodeType ? c : document.createTextNode(String(c)));
    }
    return node;
  },

  icon(name, cls = "text-[20px]") {
    return ui.el("span", { class: `material-symbols-outlined ${cls}` }, name);
  },

  toast(msg, type = "info") {
    const colors = {
      info: "bg-primary-container text-on-primary",
      ok: "bg-secondary-container text-on-secondary-container",
      err: "bg-error text-on-error",
    };
    const t = ui.el("div", {
      class: `toast-item px-4 py-2.5 rounded-xl shadow-lg font-body-sm text-body-sm ${colors[type] || colors.info}`,
    }, msg);
    document.getElementById("toast-root").append(t);
    setTimeout(() => { t.style.opacity = "0"; t.style.transform = "translateY(8px)"; }, 2600);
    setTimeout(() => t.remove(), 3000);
  },

  /* 确认弹窗，返回 Promise<boolean> */
  confirm(title, body, okText = "确认", danger = false) {
    return new Promise((resolve) => {
      const root = document.getElementById("modal-root");
      const close = (val) => { overlay.remove(); resolve(val); };
      const overlay = ui.el("div", {
        class: "fixed inset-0 z-[90] bg-ink-black/40 backdrop-blur-sm flex items-center justify-center",
        onclick: (e) => { if (e.target === overlay) close(false); },
      },
        ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-lg w-[420px] max-w-[calc(100vw-2rem)] mx-4 shadow-[0_12px_32px_rgba(27,42,56,0.12)] flex flex-col gap-space-md" },
          ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, title),
          ui.el("div", { class: "font-body-sm text-body-sm text-on-surface-variant whitespace-pre-wrap" }, body),
          ui.el("div", { class: "flex justify-end gap-2" },
            ui.el("button", {
              class: "px-4 py-2 min-h-[44px] min-w-[76px] rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md cursor-pointer flex items-center justify-center",
              onclick: () => close(false),
            }, "取消"),
            ui.el("button", {
              class: `px-4 py-2 min-h-[44px] min-w-[76px] rounded-lg font-label-md text-label-md cursor-pointer flex items-center justify-center ${danger ? "bg-error text-on-error" : "bg-primary text-on-primary"}`,
              onclick: () => close(true),
            }, okText))));
      root.append(overlay);
    });
  },

  /* 输入弹窗，返回 Promise<string|null> */
  prompt(title, placeholder = "", value = "") {
    return new Promise((resolve) => {
      const root = document.getElementById("modal-root");
      const input = ui.el("input", {
        class: "w-full px-3 py-2.5 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-md text-[16px] sm:text-body-md",
        placeholder, value,
      });
      const close = (val) => { overlay.remove(); resolve(val); };
      const overlay = ui.el("div", {
        class: "fixed inset-0 z-[90] bg-ink-black/40 backdrop-blur-sm flex items-center justify-center",
        onclick: (e) => { if (e.target === overlay) close(null); },
      },
        ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-lg w-[420px] max-w-[calc(100vw-2rem)] mx-4 shadow-[0_12px_32px_rgba(27,42,56,0.12)] flex flex-col gap-space-md" },
          ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, title),
          input,
          ui.el("div", { class: "flex justify-end gap-2" },
            ui.el("button", { class: "px-4 py-2 min-h-[44px] min-w-[76px] rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md cursor-pointer flex items-center justify-center", onclick: () => close(null) }, "取消"),
            ui.el("button", { class: "px-4 py-2 min-h-[44px] min-w-[76px] rounded-lg bg-primary text-on-primary font-label-md text-label-md cursor-pointer flex items-center justify-center", onclick: () => close(input.value.trim() || null) }, "确定"))));
      input.addEventListener("keydown", (e) => { if (e.key === "Enter") close(input.value.trim() || null); });
      root.append(overlay);
      input.focus();
    });
  },

  /* 通用模态弹窗：ui.modal(title, content, actions = [], options = {}) */
  modal(title, content, actions = [], options = {}) {
    const root = document.getElementById("modal-root");
    const close = () => overlay.remove();
    const maxWidth = options.maxWidth || "max-w-5xl";
    const overlay = ui.el("div", {
      class: "fixed inset-0 z-[90] bg-ink-black/40 backdrop-blur-sm flex items-center justify-center p-3 sm:p-4",
      onclick: (e) => { if (e.target === overlay && options.clickOutsideToClose !== false) close(); },
    },
      ui.el("div", {
        class: `bg-surface-container-lowest rounded-2xl p-space-md sm:p-space-lg w-full ${maxWidth} max-h-[92vh] shadow-[0_12px_36px_rgba(27,42,56,0.18)] border border-outline-variant/40 flex flex-col gap-space-md overflow-hidden animate-in fade-in zoom-in-95 duration-150`
      },
        ui.el("div", { class: "flex items-center justify-between gap-2 pb-2 border-b border-outline-variant/40 shrink-0" },
          ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold tracking-tight truncate" }, title),
          ui.el("button", {
            class: "p-1.5 rounded-full text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors",
            title: "??",
            onclick: close,
          }, ui.icon("close", "text-[20px]"))
        ),
        ui.el("div", { class: "flex-1 min-h-0 overflow-y-auto" }, content),
        actions && actions.length > 0
          ? ui.el("div", { class: "flex items-center justify-end gap-2 pt-2 border-t border-outline-variant/40 shrink-0" }, ...actions)
          : null
      )
    );
    root.append(overlay);
    return { overlay, close };
  },

  setCrumb(...items) {
    const c = document.getElementById("topbar-crumb");
    c.innerHTML = "";
    items.forEach((it, i) => {
      if (i > 0) c.append(ui.icon("chevron_right", "text-[16px]"));
      c.append(ui.el("span", {
        class: i === items.length - 1
          ? "font-headline-sm text-headline-sm text-primary tracking-tight font-medium"
          : "hover:text-on-surface transition-colors",
      }, it));
    });
  },

  setActions(...nodes) {
    const a = document.getElementById("topbar-actions");
    a.innerHTML = "";
    nodes.forEach((n) => n && a.append(n));
  },

  setSaveIndicator(state) {
    const box = document.getElementById("save-indicator");
    if (!state) { box.classList.add("hidden"); box.classList.remove("flex"); return; }
    box.classList.remove("hidden"); box.classList.add("flex");
    const map = {
      saving: ["sync", "正在保存…"],
      saved: ["cloud_done", "已保存"],
      error: ["cloud_off", "保存失败 · 点击重试"],
    };
    const [icon, text] = map[state] || map.saved;
    document.getElementById("save-icon").textContent = icon;
    document.getElementById("save-text").textContent = text;
  },

  fmtWords(n) {
    n = n || 0;
    return n >= 10000 ? (n / 10000).toFixed(1) + "万" : n.toLocaleString();
  },

  async refreshStats() {
    try {
      const s = await api.get("/stats/dashboard");
      const settings = await api.get("/settings");
      document.getElementById("stat-today").textContent = s.today_words.toLocaleString();
      document.getElementById("stat-goal").textContent = "/ " + Number(settings.daily_word_goal || 5000).toLocaleString();
      document.getElementById("stat-total").textContent = ui.fmtWords(s.total_words);
    } catch (e) { /* 忽略统计失败 */ }
  },

  applyTheme(theme) {
    document.body.classList.toggle("theme-dark", theme === "dark");
    document.body.classList.toggle("theme-paper", theme === "paper");
    document.documentElement.classList.toggle("dark", theme === "dark");
  },

  /* 全局搜索命令面板（Ctrl+K / Cmd+K 唤起） */
  palette() {
    if (document.getElementById("palette-overlay")) return;
    const root = document.getElementById("modal-root");
    const TYPE_META = {
      work: { icon: "menu_book", label: "作品", go: () => "#/bookshelf" },
      chapter: { icon: "article", label: "章节", go: (r) => `#/workbench/${r.work_id}?chapter=${r.id}` },
      entity: { icon: "person", label: "设定", go: (r) => `#/entities/${r.work_id}` },
      outline: { icon: "account_tree", label: "大纲", go: (r) => `#/outline/${r.work_id}` },
    };
    let items = [], active = -1, seq = 0, timer = null, q = "";

    const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
      (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const hilite = (s) => {
      const safe = esc(s);
      if (!q) return safe;
      const re = new RegExp(esc(q).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
      return safe.replace(re, (m) => `<mark class="bg-secondary-fixed text-on-secondary-fixed rounded-sm px-0.5">${m}</mark>`);
    };

    const close = () => {
      document.removeEventListener("keydown", onKey, true);
      clearTimeout(timer);
      overlay.remove();
    };
    const go = (r) => { close(); location.hash = TYPE_META[r.type].go(r); };

    const listBox = ui.el("div", { class: "max-h-[420px] overflow-y-auto px-2 py-2" });

    const refreshActive = () => {
      listBox.querySelectorAll(".palette-item").forEach((row, i) => {
        row.classList.toggle("bg-surface-container-high", i === active);
        if (i === active) row.scrollIntoView({ block: "nearest" });
      });
    };

    const renderIdle = () => {
      listBox.innerHTML = "";
      listBox.append(ui.el("div", { class: "px-3 py-6 text-center font-body-sm text-body-sm text-on-surface-variant" },
        "输入关键词，搜索作品、章节、设定、大纲"));
    };
    const renderEmpty = () => {
      listBox.innerHTML = "";
      listBox.append(ui.el("div", { class: "px-3 py-6 text-center font-body-sm text-body-sm text-on-surface-variant" },
        "已搜索作品/章节/设定/大纲，无匹配内容，换个关键词试试"));
    };
    const renderSkeleton = () => {
      listBox.innerHTML = "";
      for (let i = 0; i < 4; i++)
        listBox.append(ui.el("div", { class: "flex items-center gap-3 px-3 py-2" },
          ui.el("div", { class: "w-5 h-5 rounded bg-surface-container-high animate-pulse" }),
          ui.el("div", { class: "flex-1 flex flex-col gap-1.5" },
            ui.el("div", { class: "h-3.5 w-1/3 rounded bg-surface-container-high animate-pulse" }),
            ui.el("div", { class: "h-3 w-2/3 rounded bg-surface-container animate-pulse" }))));
    };
    const render = () => {
      listBox.innerHTML = "";
      if (!items.length) { renderEmpty(); return; }
      let idx = 0, lastType = null;
      for (const r of items) {
        const meta = TYPE_META[r.type];
        if (r.type !== lastType) {
          lastType = r.type;
          listBox.append(ui.el("div", { class: "px-3 pt-2 pb-1 font-label-sm text-label-sm text-on-surface-variant" }, meta.label));
        }
        const i = idx++;
        listBox.append(ui.el("div", {
          class: `palette-item flex items-start gap-3 px-3 py-2 rounded-lg cursor-pointer ${i === active ? "bg-surface-container-high" : ""}`,
          onclick: () => go(r),
          onmouseenter: () => { active = i; refreshActive(); },
        },
          ui.icon(meta.icon, "text-[20px] text-on-surface-variant mt-0.5 shrink-0"),
          ui.el("div", { class: "flex-1 min-w-0" },
            ui.el("div", { class: "flex items-baseline gap-2 min-w-0" },
              ui.el("span", { class: "font-body-md text-body-md text-on-surface truncate", html: hilite(r.title || r.name || "") }),
              r.work_title ? ui.el("span", { class: "font-body-sm text-body-sm text-on-surface-variant truncate shrink-0" }, r.work_title) : null),
            r.snippet ? ui.el("div", { class: "font-body-sm text-body-sm text-on-surface-variant truncate", html: hilite(r.snippet) }) : null)));
      }
    };

    const doSearch = async () => {
      q = input.value.trim();
      const mySeq = ++seq;
      if (!q) { items = []; active = -1; renderIdle(); return; }
      renderSkeleton();
      try {
        const res = await api.get("/search?q=" + encodeURIComponent(q));
        if (mySeq !== seq) return;
        items = res.results || [];
        active = items.length ? 0 : -1;
        render();
      } catch (e) {
        if (mySeq === seq) { items = []; active = -1; renderEmpty(); }
      }
    };

    const input = ui.el("input", {
      class: "flex-1 bg-transparent outline-none font-body-md text-body-md text-on-surface placeholder:text-on-surface-variant",
      placeholder: "搜索作品、章节、设定、大纲…",
    });
    input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(doSearch, 250); });

    const overlay = ui.el("div", {
      id: "palette-overlay",
      class: "fixed inset-0 z-[90] bg-ink-black/40 backdrop-blur-sm flex justify-center pt-4 sm:pt-[12vh] px-3 sm:px-0",
      onclick: (e) => { if (e.target === overlay) close(); },
    },
      ui.el("div", { class: "bg-surface-container-lowest rounded-xl w-[560px] max-w-[calc(100vw-1.5rem)] h-fit max-h-[85vh] shadow-[0_12px_32px_rgba(27,42,56,0.12)] flex flex-col overflow-hidden" },
        ui.el("div", { class: "flex items-center gap-2 px-4 py-3 border-b border-border-feather" },
          ui.icon("search", "text-[20px] text-on-surface-variant"),
          input,
          ui.el("kbd", { class: "px-1.5 py-0.5 rounded bg-surface-container font-label-sm text-label-sm text-on-surface-variant" }, "Esc")),
        listBox,
        ui.el("div", { class: "flex items-center gap-3 px-4 py-2 border-t border-border-feather font-label-sm text-label-sm text-on-surface-variant" },
          ui.el("span", null, "↑↓ 选择"),
          ui.el("span", null, "Enter 跳转"),
          ui.el("span", null, "Esc 关闭"),
          ui.el("span", { class: "ml-auto" }, "Ctrl+K 唤起"))));

    const onKey = (e) => {
      if (!overlay.isConnected) { document.removeEventListener("keydown", onKey, true); return; }
      if (e.key === "Escape") { e.preventDefault(); close(); }
      else if (e.key === "ArrowDown") { e.preventDefault(); if (items.length) { active = (active + 1) % items.length; refreshActive(); } }
      else if (e.key === "ArrowUp") { e.preventDefault(); if (items.length) { active = (active - 1 + items.length) % items.length; refreshActive(); } }
      else if (e.key === "Enter") { e.preventDefault(); if (active >= 0 && items[active]) go(items[active]); }
    };
    document.addEventListener("keydown", onKey, true);

    root.append(overlay);
    renderIdle();
    input.focus();
  },
  /* 全局快速记录灵感便签，返回 Promise<saved|null> */
  quickNoteDialog() {
    return new Promise((resolve) => {
      const root = document.getElementById("modal-root");
      const input = ui.el("textarea", {
        class: "w-full px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-sm text-[16px] sm:text-body-sm resize-none",
        rows: "4", placeholder: "捕捉掠过脑海的伏笔、绝妙对白或世界法则…",
      });
      const close = (val) => { overlay.remove(); resolve(val); };
      const overlay = ui.el("div", {
        class: "fixed inset-0 z-[90] bg-ink-black/40 backdrop-blur-sm flex items-center justify-center",
        onclick: (e) => { if (e.target === overlay) close(null); },
      },
        ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-lg w-[420px] max-w-[calc(100vw-2rem)] mx-4 shadow-[0_12px_32px_rgba(27,42,56,0.12)] flex flex-col gap-space-md" },
          ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, "快速记录"),
          input,
          ui.el("div", { class: "flex justify-end gap-2" },
            ui.el("button", { class: "px-4 py-2 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md", onclick: () => close(null) }, "取消"),
            ui.el("button", {
              class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md",
              onclick: async () => {
                const text = input.value.trim();
                if (!text) { close(null); return; }
                try {
                  const saved = await api.post("/notes", { content: text });
                  ui.toast("已记录灵感便签", "ok");
                  window.dispatchEvent(new CustomEvent("moyu:note-added", { detail: saved }));
                  close(saved);
                } catch (e) { ui.toast(e.message, "err"); }
              },
            }, "记录"))));
      root.append(overlay);
      input.focus();
    });
  },
};
