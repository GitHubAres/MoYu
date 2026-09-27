/* 导入导出页（对应设计稿 _8，本地版裁剪：去掉发布/邮箱） */
registerPage("io", async (view) => {
  ui.setCrumb("导入导出");

  /* ---------- 状态 ---------- */
  let works = [];
  let work = null;          // 当前选中作品
  let tree = [];            // 当前作品卷章树
  let scopeType = "all";    // all | volumes | chapters
  let selVolumes = new Set();
  let selChapters = new Set();
  let format = "docx";      // txt | docx
  const options = { indent: true, format_titles: true, append_entities: false };
  let importing = null;     // preview 返回 {file_token, title, chapters, total_words}

  /* ---------- 布局骨架 ---------- */
  const tabBtnCls = (on) =>
    `flex items-center gap-space-xs px-space-md py-1.5 rounded-lg font-label-md text-label-md transition-all duration-200 ${
      on ? "bg-surface-container-lowest text-primary font-semibold shadow-sm" : "text-on-surface-variant hover:text-on-surface"}`;
  const tabExport = ui.el("button", { class: tabBtnCls(true), onclick: () => switchTab("export") },
    ui.icon("publish", "text-[18px]"), "作品导出");
  const tabImport = ui.el("button", { class: tabBtnCls(false), onclick: () => switchTab("import") },
    ui.icon("file_download", "text-[18px]"), "稿件导入");

  const exportView = ui.el("div", { class: "flex flex-col gap-space-lg" });
  const importView = ui.el("div", { class: "hidden flex-col gap-space-lg" });

  view.append(
    ui.el("div", { class: "flex flex-col md:flex-row md:items-center justify-between gap-space-md" },
      ui.el("div", { class: "flex flex-col gap-1" },
        ui.el("span", { class: "font-label-sm text-label-sm text-secondary tracking-widest uppercase" }, "PRD 5.7 · 本地导入导出"),
        ui.el("h1", { class: "font-display text-display text-primary tracking-tight" }, "作品导入与导出工坊"),
        ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" },
          "支持 TXT / DOCX 智能拆章入库与标准排版导出，全部文件保存在本地 data/ 目录。")),
      ui.el("div", { class: "flex items-center p-1 bg-surface-container rounded-xl self-start md:self-auto shadow-sm" },
        tabExport, tabImport)),
    exportView, importView);

  function switchTab(tab) {
    exportView.className = tab === "export" ? "flex flex-col gap-space-lg" : "hidden";
    importView.className = tab === "import" ? "flex flex-col gap-space-lg" : "hidden";
    tabExport.className = tabBtnCls(tab === "export");
    tabImport.className = tabBtnCls(tab === "import");
  }

  /* ================= 导出视图 ================= */

  const workSelect = ui.el("select", {
    class: "flex-1 bg-surface-container-low text-primary p-space-xs px-space-sm rounded-lg font-body-sm text-body-sm outline-none",
    onchange: () => loadWork(Number(workSelect.value)),
  });
  const scopeDetail = ui.el("div", { class: "flex flex-col gap-1" });
  const previewBox = ui.el("div", { class: "bg-surface-container-low rounded-xl p-space-md flex flex-col gap-space-sm max-h-[420px] overflow-y-auto" });
  const previewMeta = ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" });
  const genBtn = ui.el("button", {
    class: "w-full flex items-center justify-center gap-space-xs py-space-sm px-space-md rounded-xl bg-primary text-on-primary font-label-md text-label-md font-semibold shadow-md hover:bg-primary-container transition-all disabled:opacity-50",
    onclick: doExport,
  }, ui.icon("file_download", "text-[18px]"), "立即生成导出文件");
  const historyBody = ui.el("tbody", { class: "divide-y-0 text-on-surface" });

  const scopeCards = {};
  for (const [key, label, desc] of [
    ["all", "全书导出", "全部卷章 · 完整归档推荐"],
    ["volumes", "按卷选择", "仅导出勾选的卷"],
    ["chapters", "自定义勾选", "逐章勾选导出"],
  ]) {
    const radio = ui.el("input", { type: "radio", name: "export-scope", class: "accent-secondary h-4 w-4" });
    radio.checked = key === "all";
    radio.addEventListener("change", () => { scopeType = key; renderScopeDetail(); renderPreview(); });
    scopeCards[key] = ui.el("label", {
      class: "relative flex flex-col p-space-sm rounded-xl bg-surface-container-low cursor-pointer hover:bg-surface-container transition-all",
    },
      ui.el("div", { class: "flex items-center justify-between mb-1" },
        ui.el("span", { class: "font-label-md text-label-md text-primary font-semibold" }, label), radio),
      ui.el("span", { class: "font-body-sm text-body-sm text-on-surface-variant" }, desc));
  }

  const fmtCards = {};
  for (const [key, icon, label, desc] of [
    ["txt", "text_snippet", "TXT 纯文本", "标准 UTF-8 编码，各大文学站点连载后台首选。"],
    ["docx", "article", "DOCX 标准排版", "内置大纲级别标题、规范首行缩进，适合送审归档。"],
  ]) {
    fmtCards[key] = ui.el("div", {
      class: "flex flex-col p-space-sm rounded-xl cursor-pointer transition-all",
      onclick: () => { format = key; renderFmtCards(); renderPreview(); },
    },
      ui.el("div", { class: "flex items-center justify-between" },
        ui.el("div", { class: "w-8 h-8 rounded-lg flex items-center justify-center fmt-icon" }, ui.icon(icon, "text-[18px]")),
        ui.el("span", { class: "px-1.5 py-0.5 rounded text-[10px] font-semibold fmt-tag" }, key.toUpperCase())),
      ui.el("span", { class: "font-label-md text-label-md font-semibold mt-space-xs fmt-title" }, label),
      ui.el("p", { class: "font-body-sm text-body-sm line-clamp-2 mt-0.5 fmt-desc" }, desc));
  }

  function renderFmtCards() {
    for (const [key, card] of Object.entries(fmtCards)) {
      const on = key === format;
      card.className = `flex flex-col p-space-sm rounded-xl cursor-pointer transition-all ${
        on ? "bg-primary-container text-on-primary-container shadow-sm" : "bg-surface-container-low hover:bg-surface-container"}`;
      card.querySelector(".fmt-icon").className = `w-8 h-8 rounded-lg flex items-center justify-center fmt-icon ${
        on ? "bg-secondary-container text-on-secondary-container" : "bg-primary text-on-primary"}`;
      card.querySelector(".fmt-tag").className = `px-1.5 py-0.5 rounded text-[10px] font-semibold fmt-tag ${
        on ? "bg-surface-container-lowest text-primary" : "bg-secondary-fixed text-on-secondary-fixed"}`;
      card.querySelector(".fmt-title").className = `font-label-md text-label-md font-semibold mt-space-xs fmt-title ${
        on ? "text-surface-container-lowest" : "text-primary"}`;
      card.querySelector(".fmt-desc").className = `font-body-sm text-body-sm line-clamp-2 mt-0.5 fmt-desc ${
        on ? "text-on-primary-container" : "text-on-surface-variant"}`;
    }
  }

  function optionRow(key, icon, label, desc) {
    const cb = ui.el("input", { type: "checkbox", class: "accent-secondary h-4 w-4 rounded" });
    cb.checked = options[key];
    cb.addEventListener("change", () => { options[key] = cb.checked; renderPreview(); });
    return ui.el("label", {
      class: "flex items-center justify-between p-space-xs px-space-sm rounded-xl bg-surface-container-low cursor-pointer hover:bg-surface-container transition-colors",
    },
      ui.el("div", { class: "flex items-center gap-space-xs" },
        cb,
        ui.el("div", { class: "flex flex-col" },
          ui.el("span", { class: "font-label-md text-label-md text-primary font-medium" }, label),
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, desc))),
      ui.icon(icon, "text-[18px] text-on-surface-variant"));
  }

  const configCard = ui.el("div", { class: "lg:col-span-7 bg-surface-container-lowest rounded-xl p-space-lg shadow-sm flex flex-col gap-space-md" },
    ui.el("div", { class: "flex items-center justify-between" },
      ui.el("span", { class: "font-headline-sm text-headline-sm text-primary font-semibold flex items-center gap-space-xs" },
        ui.icon("settings_suggest", "text-secondary text-[22px]"), "导出工程配置"),
      ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant px-space-xs py-0.5 rounded-md bg-surface-container-low" }, "标准排版模版")),
    ui.el("div", { class: "flex flex-col gap-1.5" },
      ui.el("label", { class: "font-label-md text-label-md text-on-surface-variant font-medium" }, "当前导出标的作品"),
      workSelect),
    ui.el("div", { class: "flex flex-col gap-2 pt-space-xs" },
      ui.el("label", { class: "font-label-md text-label-md text-on-surface-variant font-medium" }, "导出卷章范围"),
      ui.el("div", { class: "grid grid-cols-1 sm:grid-cols-3 gap-space-xs" },
        scopeCards.all, scopeCards.volumes, scopeCards.chapters),
      scopeDetail),
    ui.el("div", { class: "flex flex-col gap-2 pt-space-xs" },
      ui.el("label", { class: "font-label-md text-label-md text-on-surface-variant font-medium" }, "目标交付格式"),
      ui.el("div", { class: "grid grid-cols-1 sm:grid-cols-2 gap-space-xs" }, fmtCards.txt, fmtCards.docx)),
    ui.el("div", { class: "flex flex-col gap-2 pt-space-xs" },
      ui.el("label", { class: "font-label-md text-label-md text-on-surface-variant font-medium" }, "排版规范与包含附录"),
      optionRow("indent", "format_indent_increase", "段首统一缩进两全角字符 (Indent 2em)", "清理空行冗余，中国当代小说规范排版"),
      optionRow("format_titles", "format_size", "自动格式化卷章序号与标题", "不符合「第X章 标题」格式的标题自动补序号"),
      optionRow("append_entities", "badge", "文末附带设定简介附录", "添加人物/地点/物品等设定条目供审读")));

  const previewCard = ui.el("div", { class: "lg:col-span-5 bg-surface-container-lowest rounded-xl p-space-lg shadow-md flex flex-col gap-space-md sticky top-20" },
    ui.el("div", { class: "flex items-center justify-between" },
      ui.el("div", { class: "flex items-center gap-space-xs" },
        ui.el("span", { class: "w-2.5 h-2.5 rounded-full bg-secondary animate-pulse" }),
        ui.el("span", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, "排版样张实时预览")),
      previewMeta),
    previewBox,
    genBtn);

  const historyCard = ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-lg shadow-sm flex flex-col gap-space-md" },
    ui.el("div", { class: "flex items-center gap-space-xs" },
      ui.icon("history", "text-primary text-[20px]"),
      ui.el("span", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, "导出交付历史记录")),
    ui.el("div", { class: "overflow-x-auto" },
      ui.el("table", { class: "w-full text-left font-body-sm text-body-sm" },
        ui.el("thead", {},
          ui.el("tr", { class: "bg-surface-container-low text-on-surface-variant font-label-md text-label-md" },
            ui.el("th", { class: "py-space-xs px-space-sm rounded-l-lg" }, "导出工程名称"),
            ui.el("th", { class: "py-space-xs px-space-sm" }, "格式"),
            ui.el("th", { class: "py-space-xs px-space-sm" }, "涵盖范围"),
            ui.el("th", { class: "py-space-xs px-space-sm" }, "字数与大小"),
            ui.el("th", { class: "py-space-xs px-space-sm" }, "生成时间"),
            ui.el("th", { class: "py-space-xs px-space-sm" }, "状态"),
            ui.el("th", { class: "py-space-xs px-space-sm rounded-r-lg text-right" }, "操作"))),
        historyBody)));

  exportView.append(
    ui.el("div", { class: "grid grid-cols-1 lg:grid-cols-12 gap-space-lg items-start" }, configCard, previewCard),
    historyCard);

  /* ---------- 导出：数据加载与渲染 ---------- */

  function currentScope() {
    if (scopeType === "volumes") return { type: "volumes", ids: [...selVolumes] };
    if (scopeType === "chapters") return { type: "chapters", ids: [...selChapters] };
    return { type: "all", ids: [] };
  }

  function scopedChapters() {
    const scope = currentScope();
    const out = [];
    for (const v of tree) {
      const chs = (v.chapters || []).filter((c) =>
        scope.type === "all" ||
        (scope.type === "volumes" && selVolumes.has(v.id)) ||
        (scope.type === "chapters" && selChapters.has(c.id)));
      if (chs.length) out.push([v.title, chs]);
    }
    return out;
  }

  function renderScopeDetail() {
    scopeDetail.innerHTML = "";
    if (scopeType === "all") return;
    if (scopeType === "volumes") {
      scopeDetail.append(ui.el("div", { class: "flex flex-wrap gap-2 p-space-xs" },
        tree.map((v) => checkChip(v.title, selVolumes.has(v.id), (on) => {
          on ? selVolumes.add(v.id) : selVolumes.delete(v.id);
          renderPreview();
        }))));
      return;
    }
    for (const v of tree) {
      scopeDetail.append(
        ui.el("div", { class: "flex flex-col gap-1 py-1" },
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, v.title),
          ui.el("div", { class: "flex flex-wrap gap-2" },
            (v.chapters || []).map((c) => checkChip(c.title, selChapters.has(c.id), (on) => {
              on ? selChapters.add(c.id) : selChapters.delete(c.id);
              renderPreview();
            })))));
    }
  }

  function checkChip(label, checked, onChange) {
    const cb = ui.el("input", { type: "checkbox", class: "accent-secondary h-3.5 w-3.5" });
    cb.checked = checked;
    cb.addEventListener("change", () => onChange(cb.checked));
    return ui.el("label", {
      class: "flex items-center gap-1.5 px-2 py-1 rounded-lg bg-surface-container-low hover:bg-surface-container cursor-pointer font-label-sm text-label-sm text-on-surface",
    }, cb, label);
  }

  function renderPreview() {
    renderFmtCards();
    previewBox.innerHTML = "";
    if (!work) {
      previewBox.append(ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant text-center py-space-lg" },
        "书架还没有作品，请先创建或导入"));
      previewMeta.textContent = "";
      return;
    }
    const scoped = scopedChapters();
    const chCount = scoped.reduce((n, [, chs]) => n + chs.length, 0);
    previewMeta.textContent = `${format.toUpperCase()} 规范 · ${scoped.length}卷 ${chCount}章`;
    previewBox.append(
      ui.el("div", { class: "flex flex-col gap-space-sm" },
        ui.el("div", { class: "p-space-md bg-surface-container-lowest rounded-xl shadow-sm flex flex-col items-center text-center gap-space-xs" },
        ui.el("div", {
          class: "w-16 h-24 rounded shadow-sm flex items-center justify-center text-on-primary font-headline-sm text-headline-sm font-bold mb-1",
          style: `background:linear-gradient(135deg, ${work.cover_color || "#1B2A38"}, #1B2A38)`,
        }, (work.title || "书")[0]),
        ui.el("span", { class: "font-headline-md text-headline-md text-primary font-semibold" }, work.title),
        ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant tracking-widest uppercase" }, "墨语·本地工坊导出"),
        work.intro && ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant max-w-xs line-clamp-3" }, work.intro)),
      ui.el("div", { class: "p-space-sm bg-surface-container-lowest rounded-xl shadow-sm flex flex-col gap-1.5" },
        ui.el("span", { class: "font-label-md text-label-md text-primary font-semibold flex items-center justify-between" },
          ui.el("span", {}, "生成目录 (TOC)"),
          ui.el("span", { class: "text-secondary font-label-sm text-label-sm" }, `${chCount} Chapters`)),
        ui.el("div", { class: "flex flex-col gap-1 font-body-sm text-body-sm text-on-surface-variant" },
          scoped.flatMap(([vol, chs]) => [
            ui.el("div", { class: "flex justify-between items-center py-0.5 px-1 bg-surface-container-low rounded" },
              ui.el("span", { class: "font-semibold text-primary" }, vol),
              ui.el("span", { class: "text-on-surface-variant" }, `${chs.length}章`)),
            chs.slice(0, 3).map((c) =>
              ui.el("div", { class: "flex pl-space-md py-0.5 text-xs text-on-surface-variant" }, c.title)),
            chs.length > 3 && ui.el("div", { class: "pl-space-md py-0.5 text-xs text-outline" }, `… 共 ${chs.length} 章`),
          ]))),
        options.append_entities && ui.el("div", { class: "p-2 rounded-lg bg-surface-container-low flex items-center gap-1.5" },
          ui.icon("collections_bookmark", "text-[16px] text-secondary"),
          ui.el("span", { class: "font-label-sm text-label-sm text-primary font-medium" }, "文末将附加设定简介附录"))));
  }

  async function doExport() {
    if (!work) { ui.toast("请先选择要导出的作品", "err"); return; }
    const scope = currentScope();
    if (scope.type !== "all" && !scope.ids.length) { ui.toast("请先勾选要导出的卷或章节", "err"); return; }
    genBtn.disabled = true;
    try {
      const rec = await api.post("/export", { work_id: work.id, format, scope, options });
      if (rec.status === "done") {
        ui.toast(`已生成 ${rec.name}（${ui.fmtWords(rec.word_count)} 字）`, "ok");
      } else {
        ui.toast("导出失败：" + (rec.error || "未知原因"), "err");
      }
    } catch (e) { ui.toast(e.message, "err"); }
    genBtn.disabled = false;
    loadHistory();
  }

  function fmtSize(bytes) {
    if (!bytes) return "0 KB";
    return bytes >= 1048576 ? (bytes / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(bytes / 1024)) + " KB";
  }

  function scopeLabel(rec) {
    try {
      const s = JSON.parse(rec.scope || "{}");
      if (s.type === "volumes") return `按卷 (${(s.ids || []).length}卷)`;
      if (s.type === "chapters") return `选章 (${(s.ids || []).length}章)`;
    } catch (e) { /* 忽略 */ }
    return "全书";
  }

  async function loadHistory() {
    historyBody.innerHTML = "";
    let rows;
    try { rows = await api.get("/exports"); } catch (e) { ui.toast(e.message, "err"); return; }
    if (!rows.length) {
      historyBody.append(ui.el("tr", {},
        ui.el("td", { colspan: "7", class: "py-space-lg text-center text-on-surface-variant" }, "还没有导出记录")));
      return;
    }
    for (const r of rows) {
      const done = r.status === "done";
      historyBody.append(ui.el("tr", { class: "hover:bg-surface-container-low transition-colors" },
        ui.el("td", { class: "py-space-sm px-space-sm font-semibold text-primary" },
          ui.el("div", { class: "flex items-center gap-space-xs" },
            ui.icon(r.format === "docx" ? "article" : "text_snippet", "text-[18px] text-secondary"),
            ui.el("div", { class: "flex flex-col min-w-0" },
              ui.el("span", { class: "truncate max-w-[280px]", title: r.name }, r.name),
              ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant font-normal" }, r.work_title || "（作品已删除）")))),
        ui.el("td", { class: "py-space-sm px-space-sm" },
          ui.el("span", { class: "px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed font-label-sm text-label-sm" }, r.format.toUpperCase())),
        ui.el("td", { class: "py-space-sm px-space-sm text-on-surface-variant" }, scopeLabel(r)),
        ui.el("td", { class: "py-space-sm px-space-sm" }, `${ui.fmtWords(r.word_count)}字 • ${fmtSize(r.size)}`),
        ui.el("td", { class: "py-space-sm px-space-sm text-on-surface-variant" }, (r.created_at || "").slice(5, 16)),
        ui.el("td", { class: "py-space-sm px-space-sm" },
          done
            ? ui.el("span", { class: "inline-flex items-center gap-1 text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full font-label-sm text-label-sm" },
                ui.el("span", { class: "w-1.5 h-1.5 rounded-full bg-emerald-600" }), "已就绪")
            : ui.el("span", { class: "inline-flex items-center gap-1 text-error bg-error-container px-2 py-0.5 rounded-full font-label-sm text-label-sm", title: r.error || "" },
                ui.el("span", { class: "w-1.5 h-1.5 rounded-full bg-error" }), "失败")),
        ui.el("td", { class: "py-space-sm px-space-sm text-right" },
          ui.el("div", { class: "flex items-center justify-end gap-1" },
            done && ui.el("a", {
              class: "px-2.5 py-1 rounded-lg bg-surface-container hover:bg-secondary-container hover:text-on-secondary-container transition-colors font-label-md text-label-md",
              href: `/api/exports/${r.id}/download`,
            }, "下载"),
            ui.el("button", {
              class: "p-1.5 rounded-lg bg-surface-container-low text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-colors",
              title: "重试",
              onclick: async () => {
                try {
                  const rec = await api.post(`/exports/${r.id}/retry`);
                  rec.status === "done" ? ui.toast("已重新生成", "ok") : ui.toast("重试失败：" + (rec.error || ""), "err");
                } catch (e) { ui.toast(e.message, "err"); }
                loadHistory();
              },
            }, ui.icon("refresh", "text-[16px]")),
            ui.el("button", {
              class: "p-1.5 rounded-lg bg-surface-container-low text-on-surface-variant hover:text-error hover:bg-error-container transition-colors",
              title: "删除",
              onclick: async () => {
                const ok = await ui.confirm("删除导出记录", `将删除「${r.name}」及对应文件，确定继续？`, "删除", true);
                if (!ok) return;
                await api.del(`/exports/${r.id}`);
                ui.toast("已删除", "ok");
                loadHistory();
              },
            }, ui.icon("delete", "text-[16px]"))))));
    }
  }

  async function loadWork(workId) {
    work = works.find((w) => w.id === workId) || null;
    tree = work ? await api.get(`/works/${work.id}/tree`) : [];
    scopeType = "all";
    selVolumes = new Set(tree.map((v) => v.id));
    selChapters = new Set(tree.flatMap((v) => (v.chapters || []).map((c) => c.id)));
    scopeCards.all.querySelector("input").checked = true;
    renderScopeDetail();
    renderPreview();
  }

  /* ================= 导入视图 ================= */

  const fileInput = ui.el("input", { type: "file", accept: ".txt,.docx", class: "hidden" });
  const dropZone = ui.el("div", {
    class: "p-space-xl bg-surface-container-low rounded-xl flex flex-col items-center justify-center text-center gap-space-sm cursor-pointer hover:bg-surface-container transition-all group",
    onclick: () => fileInput.click(),
  },
    ui.el("div", { class: "w-14 h-14 rounded-full bg-surface-container flex items-center justify-center group-hover:scale-110 transition-transform" },
      ui.icon("cloud_upload", "text-[32px] text-secondary")),
    ui.el("div", { class: "flex flex-col" },
      ui.el("span", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, "点击选择文件或直接拖放至此处"),
      ui.el("span", { class: "font-body-sm text-body-sm text-on-surface-variant mt-1" }, "按「第X章 / Chapter N」行首标题自动拆章，确认后入库")),
    fileInput,
    ui.el("button", {
      class: "mt-2 px-space-md py-1.5 rounded-full bg-primary text-on-primary font-label-md text-label-md font-medium shadow-sm hover:bg-primary-container transition-colors",
      onclick: (e) => { e.stopPropagation(); fileInput.click(); },
    }, "浏览本地稿件"));
  dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.classList.add("bg-surface-container"); });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("bg-surface-container"));
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("bg-surface-container");
    if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener("change", () => { if (fileInput.files.length) uploadFile(fileInput.files[0]); fileInput.value = ""; });

  const importRight = ui.el("div", { class: "lg:col-span-6 flex flex-col gap-space-md" });

  importView.append(ui.el("div", { class: "grid grid-cols-1 lg:grid-cols-12 gap-space-lg items-start" },
    ui.el("div", { class: "lg:col-span-6 bg-surface-container-lowest rounded-xl p-space-lg shadow-sm flex flex-col gap-space-md" },
      ui.el("div", { class: "flex items-center justify-between" },
        ui.el("span", { class: "font-headline-sm text-headline-sm text-primary font-semibold flex items-center gap-space-xs" },
          ui.icon("upload_file", "text-secondary text-[22px]"), "导入稿件文件"),
        ui.el("span", { class: "font-label-sm text-label-sm text-secondary bg-secondary-fixed px-2 py-0.5 rounded-full font-semibold" }, "本地解析")),
      dropZone,
      ui.el("div", { class: "p-space-md bg-surface-container-low rounded-xl flex flex-col gap-space-xs" },
        ui.el("span", { class: "font-label-md text-label-md text-primary font-semibold flex items-center gap-1" },
          ui.icon("info", "text-[16px] text-on-surface-variant"), "格式支持与拆分规则"),
        ui.el("div", { class: "flex flex-col gap-1 pt-1 font-body-sm text-body-sm text-on-surface-variant" },
          ui.el("span", {}, "TXT（UTF-8 / GB18030 编码自动识别）"),
          ui.el("span", {}, "DOCX（Word 2007+，按段落解析）"),
          ui.el("span", {}, "拆分规则：行首「第X章/卷」或「Chapter N」标题；无匹配时整体作为一章")))),
    importRight));

  function renderImportIdle() {
    importing = null;
    importRight.innerHTML = "";
    importRight.append(ui.el("div", {
      class: "bg-surface-container-lowest rounded-xl p-space-xl shadow-sm flex flex-col items-center gap-space-sm text-center",
    },
      ui.icon("account_tree", "text-[48px] text-outline-variant"),
      ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" }, "上传稿件后，这里会显示拆分预览")));
  }

  async function uploadFile(file) {
    const fd = new FormData();
    fd.append("file", file);
    importRight.innerHTML = "";
    importRight.append(ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-xl shadow-sm flex items-center justify-center gap-2 text-on-surface-variant" },
      ui.icon("progress_activity", "text-[24px] animate-spin"), "正在解析稿件…"));
    try {
      const resp = await fetch("/api/import/preview", { method: "POST", body: fd });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "解析失败");
      importing = data;
      renderImportPreview();
    } catch (e) {
      renderImportIdle();
      ui.toast(e.message, "err");
    }
  }

  function renderImportPreview() {
    const checked = new Set(importing.chapters.map((c) => c.id));
    importRight.innerHTML = "";

    const titleInput = ui.el("input", {
      class: "flex-1 px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-md text-body-md",
      value: importing.title,
    });
    const listBox = ui.el("div", { class: "max-h-[320px] overflow-y-auto bg-surface-container-low rounded-xl p-space-xs flex flex-col gap-1" });
    const meta = ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" });
    const selectAll = ui.el("input", { type: "checkbox", class: "accent-secondary h-4 w-4" });
    selectAll.checked = true;

    function refreshMeta() {
      meta.textContent = `已选 ${checked.size} / ${importing.chapters.length} 章 · 全书约 ${ui.fmtWords(importing.total_words)} 字`;
      selectAll.checked = checked.size === importing.chapters.length;
    }

    for (const c of importing.chapters) {
      const cb = ui.el("input", { type: "checkbox", class: "accent-secondary h-4 w-4 shrink-0" });
      cb.checked = true;
      cb.addEventListener("change", () => { cb.checked ? checked.add(c.id) : checked.delete(c.id); refreshMeta(); });
      listBox.append(ui.el("label", { class: "flex items-center gap-2 p-2 rounded-lg bg-surface-container-lowest cursor-pointer" },
        cb,
        ui.el("div", { class: "flex flex-col min-w-0 flex-1" },
          ui.el("span", { class: "font-label-md text-label-md text-primary font-semibold truncate" }, c.title),
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant truncate" }, c.preview || "（空）")),
        ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant shrink-0" }, `${ui.fmtWords(c.word_count)}字`)));
    }
    selectAll.addEventListener("change", () => {
      checked.clear();
      if (selectAll.checked) importing.chapters.forEach((c) => checked.add(c.id));
      listBox.querySelectorAll("input[type=checkbox]").forEach((cb) => { cb.checked = selectAll.checked; });
      refreshMeta();
    });

    const confirmBtn = ui.el("button", {
      class: "flex-1 py-space-sm px-space-md rounded-xl bg-secondary-container text-on-secondary-container font-label-md text-label-md font-semibold shadow-md hover:bg-secondary transition-all flex items-center justify-center gap-2 disabled:opacity-50",
      onclick: async () => {
        const title = titleInput.value.trim();
        if (!title) { ui.toast("请填写作品名", "err"); return; }
        if (!checked.size) { ui.toast("请至少勾选一章", "err"); return; }
        confirmBtn.disabled = true;
        try {
          const w = await api.post("/import/confirm", {
            file_token: importing.file_token,
            title,
            chapter_ids: checked.size === importing.chapters.length ? null : [...checked],
          });
          ui.toast(`《${w.title}》已导入（${w.chapter_count} 章）`, "ok");
          location.hash = "#/bookshelf";
        } catch (e) {
          ui.toast(e.message, "err");
          confirmBtn.disabled = false;
        }
      },
    }, ui.icon("rule_folder", "text-[18px]"), "确认拆分并导入书架");

    importRight.append(ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-lg shadow-sm flex flex-col gap-space-md" },
      ui.el("div", { class: "flex items-center justify-between" },
        ui.el("span", { class: "font-headline-sm text-headline-sm text-primary font-semibold flex items-center gap-space-xs" },
          ui.icon("account_tree", "text-secondary text-[22px]"), "章节拆分预览"),
        ui.el("span", { class: "font-label-sm text-label-sm text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full font-semibold" },
          `已识别 ${importing.chapters.length} 章`)),
      ui.el("div", { class: "flex flex-col gap-1.5" },
        ui.el("label", { class: "font-label-md text-label-md text-on-surface-variant font-medium" }, "导入为作品名"),
        titleInput),
      ui.el("div", { class: "flex items-center justify-between" },
        ui.el("label", { class: "flex items-center gap-2 font-label-md text-label-md text-primary cursor-pointer" },
          selectAll, "全选"),
        meta),
      listBox,
      confirmBtn));
    refreshMeta();
  }

  renderImportIdle();

  /* ---------- 初始化 ---------- */
  renderFmtCards();
  try { works = await api.get("/works"); } catch (e) { ui.toast(e.message, "err"); }
  workSelect.innerHTML = "";
  if (works.length) {
    for (const w of works) {
      workSelect.append(ui.el("option", { value: String(w.id) }, `《${w.title}》 · ${ui.fmtWords(w.total_words)}字`));
    }
    await loadWork(works[0].id);
  } else {
    renderPreview();
  }
  await loadHistory();
});
