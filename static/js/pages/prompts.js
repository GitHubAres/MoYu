/* 提示词中心页（对应设计稿 _7，简版） */
registerPage("prompts", async (view) => {
  ui.setCrumb("提示词中心");
  ui.setActions(
    ui.el("button", {
      class: "flex items-center gap-1 px-space-sm py-1.5 rounded-full bg-primary text-on-primary shadow-[0_2px_12px_rgba(6,21,35,0.2)] hover:bg-primary-container transition-all",
      onclick: () => promptForm(null),
    }, ui.icon("add", "text-[18px]"), ui.el("span", { class: "font-label-md text-label-md" }, "新建模板")),
  );

  const TASKS = [
    ["continue", "续写"], ["expand", "扩写"], ["shorten", "缩写"],
    ["rewrite", "改写润色"], ["outline", "大纲生成"], ["audit", "设定检查"],
  ];
  const TASK_LABEL = Object.fromEntries(TASKS);
  const TASK_ICON = {
    continue: "edit_note", expand: "unfold_more", shorten: "unfold_less",
    rewrite: "auto_fix_high", outline: "account_tree", audit: "fact_check",
  };

  let prompts = [];
  let activeTab = "all";

  const tabBar = ui.el("div", { class: "flex flex-wrap gap-2" });
  const grid = ui.el("div", { class: "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-space-md" });

  view.append(
    ui.el("div", { class: "flex flex-col gap-space-lg" },
      ui.el("div", { class: "relative overflow-hidden rounded-xl bg-surface-container-lowest shadow-[0_4px_20px_rgba(6,21,35,0.03)] p-space-lg flex flex-col lg:flex-row lg:items-center justify-between gap-space-md" },
        ui.el("div", { class: "absolute -right-12 -top-12 w-64 h-64 rounded-full bg-secondary-fixed/30 blur-3xl pointer-events-none" }),
        ui.el("div", { class: "flex flex-col gap-space-xs z-10" },
          ui.el("div", { class: "flex items-center gap-space-xs" },
            ui.el("span", { class: "inline-flex items-center justify-center w-6 h-6 rounded-full bg-secondary text-on-secondary shadow-sm" },
              ui.icon("neurology", "text-[15px]")),
            ui.el("span", { class: "font-label-sm text-label-sm text-secondary tracking-widest uppercase" }, "PROMPT HUB"),
            ui.el("span", { class: "text-outline-variant font-body-sm text-body-sm" }, "•"),
            ui.el("span", { class: "font-body-sm text-body-sm text-on-surface-variant" }, "工作台 AI 侧栏可直接调用这里的模板")),
          ui.el("h1", { class: "font-headline-lg text-headline-lg text-primary tracking-tight" }, "提示词中心"),
          ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant" },
            "模板中可用占位符 {{context}}（上下文）、{{selection}}（选区）、{{instruction}}（本次要求），调用时自动替换。")),
        ui.el("div", { class: "flex items-center gap-space-md z-10 shrink-0" },
          ui.el("div", { class: "flex items-center gap-space-sm bg-surface-container-low px-space-md py-space-sm rounded-xl" },
            ui.el("div", { class: "flex flex-col items-center" },
              ui.el("span", { class: "font-headline-sm text-headline-sm text-primary font-semibold", id: "prompt-stat-total" }, "0"),
              ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "全部模板")),
            ui.el("div", { class: "w-px h-8 bg-surface-container-highest" }),
            ui.el("div", { class: "flex flex-col items-center" },
              ui.el("span", { class: "font-headline-sm text-headline-sm text-secondary font-semibold", id: "prompt-stat-builtin" }, "0"),
              ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "内置预设")),
            ui.el("div", { class: "w-px h-8 bg-surface-container-highest" }),
            ui.el("div", { class: "flex flex-col items-center" },
              ui.el("span", { class: "font-headline-sm text-headline-sm text-cinnabar-accent font-semibold", id: "prompt-stat-custom" }, "0"),
              ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "自定义"))))),
      tabBar,
      grid));

  function renderTabs() {
    tabBar.innerHTML = "";
    const counts = { all: prompts.length };
    for (const p of prompts) counts[p.task_type] = (counts[p.task_type] || 0) + 1;
    const tabs = [["all", "全部"], ...TASKS];
    for (const [key, label] of tabs) {
      const active = key === activeTab;
      tabBar.append(ui.el("button", {
        class: "flex items-center gap-1.5 px-space-sm py-1.5 rounded-full font-label-md text-label-md transition-all "
          + (active
            ? "bg-primary-container text-on-primary-container font-semibold shadow-[0_2px_8px_rgba(6,21,35,0.08)]"
            : "bg-surface-container-lowest text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface"),
        onclick: () => { activeTab = key; renderTabs(); renderGrid(); },
      }, label, ui.el("span", {
        class: "px-1.5 py-0.5 rounded-full font-label-sm text-label-sm "
          + (active ? "bg-primary/20 text-on-primary-container" : "bg-surface-container-high text-on-surface-variant"),
      }, String(counts[key] || 0))));
    }
  }

  function renderGrid() {
    grid.innerHTML = "";
    const list = activeTab === "all" ? prompts : prompts.filter((p) => p.task_type === activeTab);
    if (!list.length) {
      grid.append(ui.el("div", { class: "col-span-full flex flex-col items-center gap-space-md py-space-xl text-center" },
        ui.icon("neurology", "text-[48px] text-outline-variant"),
        ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" }, "该分类下还没有模板"),
        ui.el("button", {
          class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md",
          onclick: () => promptForm(null, activeTab === "all" ? "continue" : activeTab),
        }, "新建模板")));
      return;
    }
    for (const p of list) grid.append(promptCard(p));
  }

  /* 模板内容预览：{{占位符}} 高亮 */
  function highlightTemplate(text) {
    const frag = document.createDocumentFragment();
    const re = /\{\{[^{}]+\}\}/g;
    let last = 0;
    for (const m of text.matchAll(re)) {
      frag.append(document.createTextNode(text.slice(last, m.index)));
      frag.append(ui.el("span", { class: "text-secondary font-semibold" }, m[0]));
      last = m.index + m[0].length;
    }
    frag.append(document.createTextNode(text.slice(last)));
    return frag;
  }

  function promptCard(p) {
    return ui.el("div", {
      class: "group p-space-lg rounded-xl bg-surface-container-lowest shadow-[0_4px_20px_rgba(6,21,35,0.03)] hover:shadow-[0_8px_28px_rgba(6,21,35,0.08)] transition-all duration-300 flex flex-col gap-space-md",
    },
      ui.el("div", { class: "flex items-start justify-between" },
        ui.el("div", { class: "flex items-start gap-space-sm min-w-0" },
          ui.el("div", { class: "w-10 h-10 rounded-xl bg-secondary/10 text-secondary flex items-center justify-center shrink-0" },
            ui.icon(TASK_ICON[p.task_type] || "neurology", "text-[22px]")),
          ui.el("div", { class: "flex flex-col min-w-0" },
            ui.el("div", { class: "flex items-center gap-2 flex-wrap" },
              ui.el("h4", { class: "font-headline-sm text-headline-sm text-primary group-hover:text-secondary transition-colors" }, p.name),
              ui.el("span", { class: "px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed font-label-sm text-label-sm font-semibold" },
                TASK_LABEL[p.task_type] || p.task_type),
              p.builtin ? ui.el("span", { class: "px-2 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant font-label-sm text-label-sm" }, "内置") : null))),
        null),
      ui.el("div", { class: "p-space-sm rounded-xl bg-surface-container-low font-mono text-[12px] leading-relaxed text-on-surface-variant whitespace-pre-wrap line-clamp-5 max-h-40 overflow-hidden" },
        highlightTemplate(p.template)),
      ui.el("div", { class: "flex items-center justify-end gap-space-xs pt-1" },
        ui.el("button", {
          class: "flex items-center gap-1 px-space-sm py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface font-label-md text-label-md transition-colors",
          title: "编辑",
          onclick: () => promptForm(p),
        }, ui.icon("edit", "text-[16px]"), "编辑"),
        ui.el("button", {
          class: "flex items-center gap-1 px-space-sm py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface font-label-md text-label-md transition-colors",
          title: "复制副本",
          onclick: async () => {
            try {
              const copy = await api.post(`/prompts/${p.id}/duplicate`);
              ui.toast(`已创建副本「${copy.name}」`, "ok");
              await load();
            } catch (e) { ui.toast(e.message, "err"); }
          },
        }, ui.icon("content_copy", "text-[16px]"), "复制副本"),
        !p.builtin && ui.el("button", {
          class: "flex items-center gap-1 px-space-sm py-1.5 rounded-lg bg-surface-container text-on-surface-variant hover:text-error hover:bg-error-container font-label-md text-label-md transition-colors",
          title: "删除",
          onclick: async () => {
            const ok = await ui.confirm("删除模板", `将删除模板「${p.name}」，且不可恢复。确定继续？`, "删除", true);
            if (!ok) return;
            try {
              await api.del(`/prompts/${p.id}`);
              ui.toast("已删除", "ok");
              await load();
            } catch (e) { ui.toast(e.message, "err"); }
          },
        }, ui.icon("delete", "text-[16px]"), "删除")));
  }

  /* 新建 / 编辑 弹窗表单 */
  function promptForm(p, defaultType) {
    const isBuiltin = p && p.builtin;
    const nameInput = ui.el("input", {
      class: "w-full px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-md text-body-md",
      placeholder: "模板名称", value: p ? p.name : "",
    });
    const typeSelect = ui.el("select", {
      class: "w-full px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-md text-body-md",
    }, TASKS.map(([k, label]) =>
      ui.el("option", { value: k, ...(p ? (p.task_type === k ? { selected: "" } : {}) : (k === defaultType ? { selected: "" } : {})) }, label)));
    const tplInput = ui.el("textarea", {
      class: "w-full h-56 px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-mono text-[13px] leading-relaxed resize-y",
      placeholder: "在此编写提示词模板…",
    });
    tplInput.value = p ? p.template : "";

    const overlay = ui.el("div", {
      class: "fixed inset-0 z-[90] bg-ink-black/40 backdrop-blur-sm flex items-center justify-center",
      onclick: (e) => { if (e.target === overlay) overlay.remove(); },
    },
      ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-lg w-[640px] max-w-[calc(100vw-1.5rem)] mx-2 sm:mx-0 max-h-[90vh] overflow-y-auto shadow-[0_12px_32px_rgba(27,42,56,0.12)] flex flex-col gap-space-md" },
        ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold" },
          p ? (isBuiltin ? `编辑「${p.name}」（内置）` : `编辑「${p.name}」`) : "新建模板"),
        isBuiltin && ui.el("div", { class: "flex items-start gap-space-xs rounded-lg bg-secondary-fixed/60 px-space-sm py-space-xs text-on-secondary-fixed font-body-sm text-body-sm" },
          ui.icon("info", "text-[16px] shrink-0 mt-0.5"),
          "内置模板不可直接修改，保存时将另存为一份自定义副本。"),
        ui.el("label", { class: "flex flex-col gap-1 font-label-md text-label-md text-on-surface-variant" }, "名称", nameInput),
        ui.el("label", { class: "flex flex-col gap-1 font-label-md text-label-md text-on-surface-variant" }, "任务类型", typeSelect),
        ui.el("label", { class: "flex flex-col gap-1 font-label-md text-label-md text-on-surface-variant" },
          "模板内容",
          tplInput,
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant/70" },
            "可用占位符：{{context}} 上下文、{{selection}} 当前选区、{{instruction}} 本次要求")),
        ui.el("div", { class: "flex justify-end gap-2" },
          ui.el("button", {
            class: "px-4 py-2 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md",
            onclick: () => overlay.remove(),
          }, "取消"),
          ui.el("button", {
            class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md",
            onclick: save,
          }, isBuiltin ? "另存为副本" : "保存"))));
    document.getElementById("modal-root").append(overlay);
    nameInput.focus();

    async function save() {
      const name = nameInput.value.trim();
      const template = tplInput.value.trim();
      if (!name || !template) { ui.toast("名称与模板内容不能为空", "err"); return; }
      const body = { name, task_type: typeSelect.value, template };
      try {
        if (!p) {
          await api.post("/prompts", body);
          ui.toast("模板已创建", "ok");
        } else if (isBuiltin) {
          const copy = await api.post(`/prompts/${p.id}/duplicate`);
          await api.patch(`/prompts/${copy.id}`, body);
          ui.toast("已另存为自定义副本", "ok");
        } else {
          await api.patch(`/prompts/${p.id}`, body);
          ui.toast("已保存", "ok");
        }
        overlay.remove();
        await load();
      } catch (e) { ui.toast(e.message, "err"); }
    }
  }

  async function load() {
    try { prompts = await api.get("/prompts"); }
    catch (e) { ui.toast(e.message, "err"); return; }
    document.getElementById("prompt-stat-total").textContent = prompts.length;
    document.getElementById("prompt-stat-builtin").textContent = prompts.filter((p) => p.builtin).length;
    document.getElementById("prompt-stat-custom").textContent = prompts.filter((p) => !p.builtin).length;
    renderTabs();
    renderGrid();
  }

  await load();
});
