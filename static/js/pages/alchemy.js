/* 炼丹炉 · 创作前期工坊：拆书蒸馏 / 资料融汇 / 开炉炼丹 / 丹青阁 */
registerPage("alchemy", async (view) => {
  ui.setCrumb("创作实验室");

  const TABS = [
    { id: "distill", label: "拆书蒸馏", icon: "menu_book" },
    { id: "fuse", label: "资料融汇", icon: "merge" },
    { id: "gallery", label: "丹青阁", icon: "palette" },
  ];
  const CAT_META = {
    character: { label: "角色", icon: "person" },
    place: { label: "地点", icon: "location_on" },
    faction: { label: "势力", icon: "flag" },
    item: { label: "物品", icon: "diamond" },
    term: { label: "术语", icon: "book_2" },
  };


  let works = [];
  let active = "distill";

  /* ---------- 通用工具 ---------- */

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g,
      (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function mdInline(s) {
    return esc(s)
      .replace(/\*\*([^*]+)\*\*/g, '<strong class="text-primary font-semibold">$1</strong>')
      .replace(/`([^`]+)`/g, '<code class="px-1 rounded bg-surface-container-high font-label-sm">$1</code>');
  }
  /* 简单 Markdown 渲染：标题 / 列表 / 加粗 */
  function mdRender(md) {
    const box = ui.el("div", { class: "flex flex-col gap-space-sm font-body-md text-body-md text-on-surface" });
    let list = null;
    for (const raw of String(md || "").split("\n")) {
      const t = raw.trim();
      if (!t) { list = null; continue; }
      let m;
      if ((m = t.match(/^(#{1,4})\s+(.*)/))) {
        list = null;
        box.append(ui.el(m[1].length <= 2 ? "h3" : "h4", {
          class: (m[1].length <= 2
            ? "font-headline-sm text-headline-sm pt-space-xs"
            : "font-label-md text-label-md pt-1") + " text-primary font-semibold",
          html: mdInline(m[2]),
        }));
      } else if ((m = t.match(/^(?:[-·•*]|\d+[.、])\s+(.*)/))) {
        if (!list) {
          list = ui.el("ul", { class: "list-disc pl-5 flex flex-col gap-1" });
          box.append(list);
        }
        list.append(ui.el("li", { html: mdInline(m[1]) }));
      } else {
        list = null;
        box.append(ui.el("p", { html: mdInline(t) }));
      }
    }
    return box;
  }

  /* AI 类调用失败处理：未配置时引导去系统设置 */
  function aiFail(e) {
    const msg = (e && e.message) || String(e);
    ui.toast(msg, "err");
    if (/尚未配置 AI 接口/.test(msg)) {
      ui.confirm("尚未配置 AI 接口", msg + "\n\n是否现在前往「系统设置」填写 Base URL、API Key 与模型名？", "前往设置")
        .then((ok) => { if (ok) location.hash = "#/settings"; });
    }
  }

  async function loadWorks() {
    try { works = await api.get("/works"); }
    catch (e) { ui.toast(e.message, "err"); works = []; }
  }
  function workSelect(selectedId) {
    const sel = ui.el("select", {
      class: "px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-sm text-body-sm min-w-[180px]",
    });
    if (!works.length) sel.append(ui.el("option", { value: "" }, "（暂无作品）"));
    for (const w of works) sel.append(ui.el("option", { value: w.id }, w.title));
    if (selectedId) sel.value = String(selectedId);
    return sel;
  }
  function selectedWorkId(sel) {
    const v = Number(sel.value);
    return v > 0 ? v : null;
  }

  /* 复用导入管线上传文件（.md 自动改名 .txt 以通过校验） */
  async function uploadForImport(file) {
    let f = file;
    if (/\.md$/i.test(file.name)) {
      f = new File([file], file.name.replace(/\.md$/i, ".txt"), { type: "text/plain" });
    }
    const fd = new FormData();
    fd.append("file", f);
    const resp = await fetch("/api/import/preview", { method: "POST", body: fd });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || "上传解析失败");
    return data;
  }
  /* 文件选择按钮：透明 input 覆盖在样式化按钮上，点击即弹系统文件框 */
  function filePickerButton(accept, iconName, label, onFile) {
    const input = ui.el("input", {
      type: "file", accept,
      class: "absolute inset-0 w-full h-full opacity-0 cursor-pointer",
      "aria-label": label,
    });
    input.addEventListener("change", () => {
      if (input.files && input.files[0]) onFile(input.files[0]);
      input.value = "";
    });
    return ui.el("div", { class: "relative" },
      ui.el("div", {
        class: btnGhost + " w-full justify-center py-2 border border-dashed border-outline-variant bg-transparent pointer-events-none",
      }, ui.icon(iconName, "text-[18px]"), label),
      input);
  }

  const cardCls = "bg-surface-container-lowest rounded-xl p-space-lg shadow-[0_4px_20px_rgba(6,21,35,0.03)]";
  const btnPrimary = "flex items-center justify-center gap-space-xs px-space-md py-space-sm rounded-xl bg-primary text-on-primary hover:bg-primary-container transition-all duration-200 shadow-sm font-label-md text-label-md disabled:opacity-50";
  const btnGhost = "flex items-center gap-1 px-space-sm py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md transition-colors";
  const inputCls = "w-full px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-sm text-body-sm";

  async function pollTask(taskId, onProgress) {
    const start = Date.now();
    while (Date.now() - start < 180000) {
      await new Promise((r) => setTimeout(r, 1200));
      try {
        const t = await api.get(`/tasks/${taskId}`);
        if (onProgress) onProgress(t);
        if (t.status === "done") {
          return t.output_json ? JSON.parse(t.output_json) : {};
        }
        if (t.status === "failed") {
          throw new Error(t.error_msg || "任务执行失败");
        }
        if (t.status === "cancelled") {
          throw new Error("任务已被取消");
        }
      } catch (e) {
        if (e.message && (e.message.includes("失败") || e.message.includes("取消"))) throw e;
      }
    }
    throw new Error("任务处理超时，可至「AI 任务台账」查看历史结果");
  }

  function loadingCard(text) {
    return ui.el("div", { class: cardCls + " flex items-center gap-space-md" },
      ui.el("span", { class: "material-symbols-outlined text-[24px] text-secondary animate-spin" }, "progress_activity"),
      ui.el("div", { class: "flex flex-col gap-0.5" },
        ui.el("span", { class: "font-headline-sm text-headline-sm text-primary" }, text),
        ui.el("span", { class: "font-body-sm text-body-sm text-on-surface-variant" }, "AI 思考中，可能需要等待一两分钟…")));
  }

  /* 大纲按 parent 标题排成先序序列（含缩进深度） */
  function orderOutline(nodes) {
    const titles = new Set(nodes.map((n) => n.title));
    const out = [];
    const walk = (n, depth) => {
      out.push({ node: n, depth });
      nodes.filter((c) => c.parent === n.title).forEach((c) => walk(c, depth + 1));
    };
    nodes.filter((n) => !n.parent || !titles.has(n.parent)).forEach((n) => walk(n, 0));
    nodes.forEach((n) => { if (!out.some((o) => o.node === n)) out.push({ node: n, depth: 0 }); });
    return out;
  }

  /* ---------- 骨架 ---------- */
  const tabBar = ui.el("div", { class: "flex items-center gap-1 p-1 rounded-xl bg-surface-container-low w-fit" });
  const content = ui.el("div", { class: "flex flex-col gap-space-lg" });

  view.append(
    ui.el("div", { class: "flex flex-col gap-space-lg" },
      ui.el("div", { class: "relative overflow-hidden rounded-xl bg-surface-container-lowest shadow-[0_4px_20px_rgba(6,21,35,0.03)] p-space-lg flex flex-col gap-space-xs" },
        ui.el("div", { class: "absolute -right-12 -top-12 w-64 h-64 rounded-full bg-tertiary-fixed/40 blur-3xl pointer-events-none" }),
        ui.el("div", { class: "flex items-center gap-space-xs z-10" },
          ui.el("span", { class: "inline-flex items-center justify-center w-6 h-6 rounded-full bg-tertiary-container text-on-tertiary-container shadow-sm" },
            ui.icon("science", "text-[15px]")),
          ui.el("span", { class: "font-label-sm text-label-sm text-secondary tracking-widest uppercase" }, "CREATIVE LAB · PRE-WRITING WORKSHOP"),
          ui.el("span", { class: "text-outline-variant font-body-sm text-body-sm" }, "•"),
          ui.el("span", { class: "font-body-sm text-body-sm text-on-surface-variant" }, "拆书、融汇、绘卷，创意迸发")),
        ui.el("h1", { class: "font-headline-lg text-headline-lg text-primary tracking-tight z-10" }, "创作实验室 · 前期灵感工坊"),
        ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant z-10" },
          "拆解佳作提炼文风，融汇多源资料生成设定。全书立项与结构化开坑请使用写作工作流。")),
      ui.el("div", { class: "flex items-center justify-between p-space-md rounded-xl bg-primary-fixed/20 border border-primary/20 text-on-surface flex-wrap gap-space-sm" },
        ui.el("div", { class: "flex items-center gap-space-sm min-w-0" },
          ui.el("span", { class: "inline-flex items-center justify-center w-8 h-8 rounded-lg bg-primary text-on-primary shrink-0" },
            ui.icon("alt_route", "text-[18px]")),
          ui.el("div", { class: "flex flex-col min-w-0" },
            ui.el("span", { class: "font-label-md text-label-md font-semibold text-primary" }, "需要全书立项与生成？前往 [写作工作流 · 新书开坑]"),
            ui.el("span", { class: "font-body-sm text-body-sm text-on-surface-variant" }, "立项推演、世界观、人物谱、大纲到细纲，一键全自动资产入库。"))),
        ui.el("a", {
          href: "#/workflows",
          class: "flex items-center gap-1 px-space-md py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md hover:opacity-90 transition-opacity shrink-0 cursor-pointer"
        }, ui.icon("arrow_forward", "text-[16px]"), "前往写作工作流")),
      tabBar,
      content));

  function renderTabs() {
    tabBar.innerHTML = "";
    for (const t of TABS) {
      const on = t.id === active;
      tabBar.append(ui.el("button", {
        class: "flex items-center gap-space-xs px-space-md py-space-sm rounded-lg font-label-md text-label-md transition-all duration-200 " +
          (on ? "bg-primary text-on-primary shadow-sm" : "text-on-surface-variant hover:bg-surface-container-high"),
        onclick: () => { active = t.id; renderTabs(); renderContent(); },
      }, ui.icon(t.icon, "text-[18px]"), t.label));
    }
  }

  function renderContent() {
    content.innerHTML = "";
    if (active === "distill") renderDistill();
    else if (active === "fuse") renderFuse();
    else if (window.GalleryTab && window.GalleryTab.render) window.GalleryTab.render(content);
    else content.append(ui.el("div", { class: cardCls + " flex flex-col items-center gap-space-sm py-space-xl text-on-surface-variant" },
      ui.icon("palette", "text-[48px] text-outline-variant"),
      ui.el("p", { class: "font-body-md text-body-md" }, "丹青阁筹备中…")));
  }

  /* ================= Tab1 拆书蒸馏 ================= */

  const distill = { mode: "file", fileToken: null, fileName: "", report: "", sampleInfo: null, running: false };

  function renderDistill() {
    const leftBox = ui.el("div", { class: cardCls + " flex flex-col gap-space-sm" });
    const rightBox = ui.el("div", { class: "flex flex-col gap-space-md" });
    content.append(ui.el("div", { class: "grid grid-cols-12 gap-space-lg items-start" },
      ui.el("div", { class: "col-span-12 lg:col-span-4 xl:col-span-3 flex flex-col gap-space-md lg:sticky lg:top-20" }, leftBox),
      ui.el("div", { class: "col-span-12 lg:col-span-8 xl:col-span-9" }, rightBox)));
    renderDistillLeft(leftBox, rightBox);
    renderDistillRight(rightBox);
  }

  function renderDistillLeft(leftBox, rightBox) {
    leftBox.innerHTML = "";
    leftBox.append(ui.el("span", { class: "font-label-md text-label-md text-primary font-semibold tracking-wider" }, "拆解对象"));

    const modeRow = ui.el("div", { class: "flex gap-1 p-1 rounded-lg bg-surface-container-low" });
    const modes = [["file", "上传 TXT"], ["work", "库内作品"]];
    for (const [m, label] of modes) {
      modeRow.append(ui.el("button", {
        class: "flex-1 px-2 py-1.5 rounded-md font-label-sm text-label-sm transition-colors " +
          (distill.mode === m ? "bg-primary text-on-primary" : "text-on-surface-variant hover:bg-surface-container-high"),
        onclick: () => { distill.mode = m; renderDistillLeft(leftBox, rightBox); },
      }, label));
    }
    leftBox.append(modeRow);

    if (distill.mode === "file") {
      const upBtn = filePickerButton(".txt", "upload_file",
        distill.fileName ? "重新上传" : "选择 TXT 文件",
        async (file) => {
          try {
            const r = await uploadForImport(file);
            distill.fileToken = r.file_token;
            distill.fileName = file.name;
            ui.toast(`已上传《${file.name}》，共 ${ui.fmtWords(r.total_words)} 字`, "ok");
          } catch (e) { ui.toast(e.message, "err"); }
          renderDistillLeft(leftBox, rightBox);
        });
      leftBox.append(upBtn,
        distill.fileName
          ? ui.el("div", { class: "flex items-center gap-space-xs px-space-sm py-space-xs rounded-lg bg-secondary-fixed/50 text-on-secondary-fixed font-body-sm text-body-sm" },
              ui.icon("description", "text-[16px]"), ui.el("span", { class: "truncate" }, distill.fileName))
          : ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant" }, "上传整本小说 TXT，将按开头/中段/结尾取样拆解。"));
    } else {
      const sel = workSelect();
      distill.workId = selectedWorkId(sel);
      sel.addEventListener("change", () => { distill.workId = selectedWorkId(sel); });
      leftBox.append(ui.el("label", { class: "flex flex-col gap-1 font-label-sm text-label-sm text-on-surface-variant" }, "选择作品", sel),
        ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant" }, "取该作品首尾若干章正文取样拆解。"));
    }

    const runBtn = ui.el("button", {
      class: btnPrimary,
      disabled: distill.running ? "" : null,
      onclick: async () => {
        if (distill.running) return;
        const body = distill.mode === "file" ? { file_token: distill.fileToken } : { work_id: distill.workId };
        if (distill.mode === "file" && !distill.fileToken) { ui.toast("请先上传 TXT 文件", "err"); return; }
        if (distill.mode === "work" && !distill.workId) { ui.toast("请选择库内作品", "err"); return; }
        distill.running = true;
        rightBox.innerHTML = "";
        rightBox.append(loadingCard("正在拆解文本样本…"));
        renderDistillLeft(leftBox, rightBox);
        try {
          const task = await api.post("/alchemy/analyze?async_mode=true", body);
          const r = task.task_id ? await pollTask(task.task_id) : task;
          distill.report = r.report;
          distill.sampleInfo = r.sample_info;
        } catch (e) {
          distill.report = "";
          aiFail(e);
        } finally {
          distill.running = false;
          renderDistillLeft(leftBox, rightBox);
          renderDistillRight(rightBox);
        }
      },
    }, ui.icon("science", "text-[18px]"), distill.running ? "拆解中…" : "开始拆解");
    leftBox.append(runBtn);
  }

  function renderDistillRight(rightBox) {
    rightBox.innerHTML = "";
    if (!distill.report) {
      rightBox.append(ui.el("div", { class: cardCls + " flex flex-col items-center gap-space-sm py-space-xl text-center" },
        ui.icon("menu_book", "text-[48px] text-outline-variant"),
        ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" },
          "上传一本佳作或选择库内作品，点「开始拆解」生成文风拆解报告")));
      return;
    }
    const info = distill.sampleInfo || {};
    const infoText = info.source === "work"
      ? `样本：《${info.name}》 · 共 ${info.chapter_count} 章，取 ${((info.sampled_chapters || []).join("、"))} · 取样约 ${info.sampled_chars} 字`
      : `样本：《${info.name}》 · 全文约 ${ui.fmtWords(info.total_chars)} 字 · 取样约 ${info.sampled_chars} 字`;

    const saveSel = workSelect();
    const saveBtn = ui.el("button", {
      class: btnPrimary,
      onclick: async () => {
        const wid = selectedWorkId(saveSel);
        if (!wid) { ui.toast("请先选择目标作品", "err"); return; }
        saveBtn.disabled = true;
        try {
          await api.post("/alchemy/save-style", { work_id: wid, style_profile: distill.report });
          ui.toast("已存为该作品的文风档案，生成正文时将自动注入", "ok");
        } catch (e) { ui.toast(e.message, "err"); }
        saveBtn.disabled = false;
      },
    }, ui.icon("save", "text-[18px]"), "存为文风档案");

    rightBox.append(
      ui.el("div", { class: cardCls + " flex flex-col gap-space-md" },
        ui.el("div", { class: "flex items-center gap-space-xs font-label-sm text-label-sm text-on-surface-variant" },
          ui.icon("biotech", "text-[16px] text-secondary"), infoText),
        ui.el("div", { class: "border-t border-border-feather" }),
        mdRender(distill.report)),
      ui.el("div", { class: cardCls + " flex flex-wrap items-center gap-space-sm" },
        ui.el("span", { class: "font-label-md text-label-md text-primary font-semibold" }, "存为文风档案到"),
        saveSel, saveBtn));
  }

  /* ================= Tab2 资料融汇 ================= */

  const fuse = { fileToken: null, fileName: "", entities: null, outline: null, running: false, importing: false };

  function renderFuse() {
    const leftBox = ui.el("div", { class: cardCls + " flex flex-col gap-space-sm" });
    const rightBox = ui.el("div", { class: "flex flex-col gap-space-md" });
    content.append(ui.el("div", { class: "grid grid-cols-12 gap-space-lg items-start" },
      ui.el("div", { class: "col-span-12 lg:col-span-4 xl:col-span-3 flex flex-col gap-space-md lg:sticky lg:top-20" }, leftBox),
      ui.el("div", { class: "col-span-12 lg:col-span-8 xl:col-span-9" }, rightBox)));

    leftBox.append(
      ui.el("span", { class: "font-label-md text-label-md text-primary font-semibold tracking-wider" }, "上传资料"),
      ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant" },
        "资料融汇只抽取设定与大纲，不导入整本正文。支持 TXT / MD / DOCX，AI 会将资料中的设定与情节线索提炼为「设定条目 + 大纲节点」预览，确认后入库。"),
      ui.el("div", { class: "p-space-sm rounded-lg bg-surface-container-low flex flex-col gap-space-xs" },
        ui.el("div", { class: "flex items-center gap-1 font-label-sm text-label-sm text-secondary font-semibold" },
          ui.icon("info", "text-[16px]"), "边界说明"),
        ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant" },
          "如需将整本小说正文按章节导入书架，请使用「导入导出」的稿件导入功能。"),
        ui.el("button", {
          class: "self-start flex items-center gap-1 px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-md text-label-md",
          onclick: () => { location.hash = "#/io"; },
        }, ui.icon("file_download", "text-[16px]"), "前往稿件导入")));

    const upBtn = filePickerButton(".txt,.md,.docx", "upload_file",
      fuse.fileName ? "重新上传" : "选择文件",
      async (file) => {
        try {
          const r = await uploadForImport(file);
          fuse.fileToken = r.file_token;
          fuse.fileName = file.name;
          fuse.entities = null;
          fuse.outline = null;
          ui.toast(`已上传《${file.name}》`, "ok");
        } catch (e) { ui.toast(e.message, "err"); }
        renderContent();
      });
    leftBox.append(upBtn);
    if (fuse.fileName) {
      leftBox.append(ui.el("div", { class: "flex items-center gap-space-xs px-space-sm py-space-xs rounded-lg bg-secondary-fixed/50 text-on-secondary-fixed font-body-sm text-body-sm" },
        ui.icon("description", "text-[16px]"), ui.el("span", { class: "truncate" }, fuse.fileName)));
    }

    const runBtn = ui.el("button", {
      class: btnPrimary,
      disabled: (fuse.running || !fuse.fileToken) ? "" : null,
      onclick: async () => {
        if (fuse.running || !fuse.fileToken) return;
        fuse.running = true;
        rightBox.innerHTML = "";
        rightBox.append(loadingCard("正在智能分类资料…"));
        renderContent();
        try {
          const task = await api.post("/alchemy/extract-lore?async_mode=true", { file_token: fuse.fileToken });
          const r = task.task_id ? await pollTask(task.task_id) : task;
          fuse.entities = (r.entities || []).map((e) => ({ ...e, _checked: true }));
          fuse.outline = (r.outline || []).map((o) => ({ ...o, _checked: true }));
        } catch (e) {
          fuse.entities = null;
          aiFail(e);
        } finally {
          fuse.running = false;
          renderContent();
        }
      },
    }, ui.icon("auto_awesome", "text-[18px]"), fuse.running ? "分类中…" : "智能分类");
    leftBox.append(runBtn);

    renderFuseRight(rightBox);
  }

  function renderFuseRight(rightBox) {
    rightBox.innerHTML = "";
    if (fuse.running) return;
    if (!fuse.entities) {
      rightBox.append(ui.el("div", { class: cardCls + " flex flex-col items-center gap-space-sm py-space-xl text-center" },
        ui.icon("merge", "text-[48px] text-outline-variant"),
        ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" }, "上传资料后点「智能分类」，这里会显示可勾选的设定条目与大纲节点"),
        ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant" }, "提示：此功能不导入正文，整本稿件拆章请去「导入导出」页。")));
      return;
    }
    if (!fuse.entities.length && !fuse.outline.length) {
      rightBox.append(ui.el("div", { class: cardCls + " flex flex-col items-center gap-space-sm py-space-xl text-center" },
        ui.icon("search_off", "text-[48px] text-outline-variant"),
        ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" }, "AI 未能从资料中提炼出设定或大纲，可换一份资料重试")));
      return;
    }

    /* 设定条目：按分类分组卡 */
    const byCat = {};
    for (const e of fuse.entities) (byCat[e.category] = byCat[e.category] || []).push(e);
    for (const cat of Object.keys(CAT_META)) {
      const list = byCat[cat];
      if (!list || !list.length) continue;
      const meta = CAT_META[cat];
      rightBox.append(ui.el("div", { class: cardCls + " flex flex-col gap-space-sm" },
        ui.el("div", { class: "flex items-center gap-space-xs" },
          ui.icon(meta.icon, "text-[18px] text-secondary"),
          ui.el("span", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, meta.label),
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, `${list.length} 条`)),
        ...list.map((e) => fuseEntityRow(e))));
    }

    /* 大纲预览 */
    if (fuse.outline.length) {
      const rows = orderOutline(fuse.outline);
      rightBox.append(ui.el("div", { class: cardCls + " flex flex-col gap-space-sm" },
        ui.el("div", { class: "flex items-center gap-space-xs" },
          ui.icon("account_tree", "text-[18px] text-secondary"),
          ui.el("span", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, "大纲节点"),
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, `${fuse.outline.length} 个`)),
        ...rows.map(({ node, depth }) => {
          const cb = ui.el("input", { type: "checkbox", class: "accent-secondary shrink-0 mt-1" });
          cb.checked = node._checked;
          cb.addEventListener("change", () => { node._checked = cb.checked; });
          const titleIn = ui.el("input", { class: inputCls + " font-semibold", value: node.title });
          titleIn.addEventListener("input", () => { node.title = titleIn.value; });
          const synIn = ui.el("textarea", { class: inputCls, rows: "2" }, node.synopsis || "");
          synIn.value = node.synopsis || "";
          synIn.addEventListener("input", () => { node.synopsis = synIn.value; });
          return ui.el("div", {
            class: "flex items-start gap-space-xs rounded-lg bg-surface-container-low p-space-sm",
            style: `margin-left:${depth * 20}px`,
          }, cb,
            ui.el("div", { class: "flex-1 flex flex-col gap-1 min-w-0" },
              titleIn, synIn,
              node.parent ? ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "归属：" + node.parent) : null));
        })));
    }

    /* 入库操作 */
    const targetSel = workSelect();
    const importBtn = ui.el("button", {
      class: btnPrimary,
      disabled: fuse.importing ? "" : null,
      onclick: async () => {
        const wid = selectedWorkId(targetSel);
        if (!wid) { ui.toast("请先选择目标作品", "err"); return; }
        const entities = fuse.entities.filter((e) => e._checked)
          .map(({ category, name, content, tags }) => ({ category, name, content, tags }));
        const outline = fuse.outline.filter((o) => o._checked)
          .map(({ title, synopsis, parent }) => ({ title, synopsis, parent }));
        if (!entities.length && !outline.length) { ui.toast("请至少勾选一条内容", "err"); return; }
        fuse.importing = true;
        importBtn.disabled = true;
        try {
          const r = await api.post("/alchemy/import-lore", { work_id: wid, entities, outline });
          ui.toast(`入库设定 ${r.created.entities} 条、大纲节点 ${r.created.outline} 个，跳过重复 ${r.skipped} 条`, "ok");
          fuse.entities = null;
          fuse.outline = null;
          renderContent();
        } catch (e) { ui.toast(e.message, "err"); }
        fuse.importing = false;
        importBtn.disabled = false;
      },
    }, ui.icon("database", "text-[18px]"), "确认入库");
    rightBox.append(ui.el("div", { class: cardCls + " flex flex-wrap items-center gap-space-sm" },
      ui.el("span", { class: "font-label-md text-label-md text-primary font-semibold" }, "确认入库到"),
      targetSel, importBtn,
      ui.el("span", { class: "font-body-sm text-body-sm text-on-surface-variant" }, "同名同分类的已有设定会自动跳过")));
  }

  function fuseEntityRow(e) {
    const meta = CAT_META[e.category] || CAT_META.term;
    const cb = ui.el("input", { type: "checkbox", class: "accent-secondary shrink-0 mt-1" });
    cb.checked = e._checked;
    cb.addEventListener("change", () => { e._checked = cb.checked; });
    const nameIn = ui.el("input", { class: inputCls + " font-semibold", value: e.name });
    nameIn.addEventListener("input", () => { e.name = nameIn.value; });
    const tagsIn = ui.el("input", { class: inputCls, value: e.tags || "", placeholder: "标签（逗号分隔）" });
    tagsIn.addEventListener("input", () => { e.tags = tagsIn.value; });
    const contentIn = ui.el("textarea", { class: inputCls, rows: "2" });
    contentIn.value = e.content || "";
    contentIn.addEventListener("input", () => { e.content = contentIn.value; });
    return ui.el("div", { class: "flex items-start gap-space-xs rounded-lg bg-surface-container-low p-space-sm" },
      cb,
      ui.el("div", { class: "flex-1 flex flex-col gap-1 min-w-0" },
        ui.el("div", { class: "flex gap-space-xs" },
          ui.el("span", { class: "shrink-0 self-center px-2 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant font-label-sm text-label-sm" }, meta.label),
          nameIn),
        contentIn, tagsIn));
  }

  /* ---------- 启动 ---------- */
  await loadWorks();
  renderTabs();
  renderContent();
});
