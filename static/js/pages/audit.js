/* 一致性检查页（对应设计稿 _5，简版） */
registerPage("audit", async (view) => {
  ui.setCrumb("一致性检查");

  const SEV = {
    high: { label: "高", cls: "bg-cinnabar-accent/15 text-cinnabar-accent", bar: "bg-cinnabar-accent" },
    medium: { label: "中", cls: "bg-tertiary-fixed text-on-tertiary-fixed-variant", bar: "bg-tertiary-fixed-dim" },
    low: { label: "低", cls: "bg-surface-container-high text-on-surface-variant", bar: "bg-outline-variant" },
  };
  const TYPE_ICON = { "矛盾": "warning", "遗忘": "memory", "时间线": "schedule", "其他": "help" };

  let works = [];
  let tree = [];          // 当前作品的卷/章
  let workId = null;
  let issues = [];        // 最近一次检查结果
  let running = false;
  let abortCtl = null;

  /* ---------- 骨架 ---------- */
  const workSelect = ui.el("select", {
    class: "px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-md text-body-md min-w-[200px]",
    onchange: () => loadTree(Number(workSelect.value)),
  });
  const chapterBox = ui.el("div", { class: "flex flex-col gap-1 max-h-72 overflow-y-auto pr-1" });
  const runBtn = ui.el("button", {
    class: "flex items-center justify-center gap-space-xs px-space-md py-space-sm rounded-xl bg-primary text-on-primary hover:bg-primary-container transition-all duration-200 shadow-sm font-label-md text-label-md disabled:opacity-50",
    onclick: runAudit,
  }, ui.icon("fact_check", "text-[18px]"), "开始检查");
  const statusLine = ui.el("div", { class: "font-label-sm text-label-sm text-on-surface-variant" });
  const taskLinkEl = ui.el("a", {
    class: "hidden flex items-center gap-1 text-secondary hover:underline font-label-sm text-label-sm",
    href: "#/tasks",
    onclick: (e) => { e.preventDefault(); location.hash = "#/tasks"; },
  }, "查看任务记录");
  const resultBox = ui.el("div", { class: "flex flex-col gap-space-md" });

  view.append(
    ui.el("div", { class: "flex flex-col gap-space-lg" },
      ui.el("div", { class: "relative overflow-hidden rounded-xl bg-surface-container-lowest shadow-[0_4px_20px_rgba(6,21,35,0.03)] p-space-lg flex flex-col gap-space-xs" },
        ui.el("div", { class: "absolute -right-12 -top-12 w-64 h-64 rounded-full bg-secondary-fixed/30 blur-3xl pointer-events-none" }),
        ui.el("div", { class: "flex items-center gap-space-xs z-10" },
          ui.el("span", { class: "inline-flex items-center justify-center w-6 h-6 rounded-full bg-secondary text-on-secondary shadow-sm" },
            ui.icon("verified", "text-[15px]")),
          ui.el("span", { class: "font-label-sm text-label-sm text-secondary tracking-widest uppercase" }, "LORE & TEMPORAL CONSISTENCY ENGINE"),
          ui.el("span", { class: "text-outline-variant font-body-sm text-body-sm" }, "•"),
          ui.el("span", { class: "font-body-sm text-body-sm text-on-surface-variant" }, "全书设定与剧情脉络稽核")),
        ui.el("h1", { class: "font-headline-lg text-headline-lg text-primary tracking-tight z-10" }, "设定一致性检查"),
        ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant z-10" },
          "检查结果为 AI 建议，不会修改任何内容。逐条查看后可跳转定位，或忽略无关项。")),
      ui.el("div", { class: "grid grid-cols-12 gap-space-lg items-start" },
        ui.el("div", { class: "col-span-12 lg:col-span-4 xl:col-span-3 flex flex-col gap-space-md lg:sticky lg:top-20" },
          ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-md shadow-[0_4px_20px_rgba(6,21,35,0.03)] flex flex-col gap-space-sm" },
            ui.el("span", { class: "font-label-md text-label-md text-primary font-semibold tracking-wider" }, "检查范围"),
            ui.el("label", { class: "flex flex-col gap-1 font-label-sm text-label-sm text-on-surface-variant" }, "作品", workSelect),
            ui.el("div", { class: "flex items-center justify-between font-label-sm text-label-sm text-on-surface-variant" },
              "章节范围",
              ui.el("div", { class: "flex gap-2" },
                ui.el("button", { class: "text-secondary hover:underline", onclick: () => setAllChecked(true) }, "全选"),
                ui.el("button", { class: "text-secondary hover:underline", onclick: () => setAllChecked(false) }, "清空"))),
            chapterBox,
            runBtn,
            statusLine,
            taskLinkEl)),
        ui.el("div", { class: "col-span-12 lg:col-span-8 xl:col-span-9" }, resultBox))));

  /* ---------- 范围加载 ---------- */
  async function loadWorks() {
    try { works = await api.get("/works"); }
    catch (e) { ui.toast(e.message, "err"); return; }
    workSelect.innerHTML = "";
    if (!works.length) {
      workSelect.append(ui.el("option", { value: "" }, "（暂无作品）"));
      runBtn.disabled = true;
      return;
    }
    for (const w of works) workSelect.append(ui.el("option", { value: w.id }, w.title));
    await loadTree(works[0].id);
  }

  async function loadTree(id) {
    workId = id;
    chapterBox.innerHTML = "";
    statusLine.textContent = "";
    issues = [];
    renderResults();
    try { tree = await api.get(`/works/${id}/tree`); }
    catch (e) { ui.toast(e.message, "err"); return; }
    const chapters = tree.flatMap((v) => v.chapters);
    if (!chapters.length) {
      chapterBox.append(ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant py-2" }, "该作品还没有章节"));
      return;
    }
    for (const ch of chapters) {
      const cb = ui.el("input", { type: "checkbox", class: "accent-secondary shrink-0", value: ch.id, checked: "" });
      chapterBox.append(ui.el("label", {
        class: "flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-surface-container-low cursor-pointer font-body-sm text-body-sm text-on-surface",
      }, cb, ui.el("span", { class: "truncate" }, ch.title),
        ui.el("span", { class: "ml-auto font-label-sm text-label-sm text-on-surface-variant shrink-0" }, ui.fmtWords(ch.word_count) + " 字")));
    }
    statusLine.textContent = `共 ${chapters.length} 章，默认全选`;
  }

  function selectedChapterIds() {
    return [...chapterBox.querySelectorAll("input:checked")].map((c) => Number(c.value));
  }

  function setAllChecked(val) {
    chapterBox.querySelectorAll("input").forEach((c) => { c.checked = val; });
  }

  /* ---------- 运行检查 ---------- */
  async function runAudit() {
    if (running) return;
    const ids = selectedChapterIds();
    if (!ids.length) { ui.toast("请至少勾选一个章节", "err"); return; }
    running = true;
    abortCtl = new AbortController();
    runBtn.disabled = true;
    renderRunning(ids.length);
    try {
      const resp = await fetch("/api/audit/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ work_id: workId, chapter_ids: ids }),
        signal: abortCtl.signal,
      });
      if (!resp.ok) {
        let msg = resp.statusText;
        try { msg = (await resp.json()).detail || msg; } catch (e) {}
        if (resp.status === 400) { renderAiGuide(msg); return; }
        throw new Error(msg);
      }
      const data = await resp.json();
      issues = data.issues || [];
      statusLine.textContent = `已检查 ${data.checked_chapters} 章`;
      if (data.task_id) {
        taskLinkEl.textContent = `查看任务记录 #${data.task_id}`;
        taskLinkEl.classList.remove("hidden");
      }
      if (data.usage && data.usage.total_tokens) {
        statusLine.textContent += ` · 消耗约 ${Number(data.usage.total_tokens).toLocaleString()} tokens`;
      }
    } catch (e) {
      if (e.name === "AbortError") {
        statusLine.textContent = "已取消本次检查";
      } else {
        ui.toast(e.message, "err");
      }
    } finally {
      running = false;
      runBtn.disabled = false;
      renderResults();
    }
  }

  function renderRunning(n) {
    resultBox.innerHTML = "";
    resultBox.append(
      ui.el("div", { class: "rounded-xl bg-surface-container-lowest shadow-[0_4px_20px_rgba(6,21,35,0.03)] p-space-lg flex items-center gap-space-md" },
        ui.el("span", { class: "material-symbols-outlined text-[24px] text-secondary animate-spin" }, "progress_activity"),
        ui.el("div", { class: "flex flex-col gap-0.5 flex-1" },
          ui.el("span", { class: "font-headline-sm text-headline-sm text-primary" }, `正在稽核 ${n} 个章节的正文与设定库…`),
          ui.el("span", { class: "font-body-sm text-body-sm text-on-surface-variant" }, "章节较长时可能需要等待一两分钟")),
        ui.el("button", {
          class: "px-4 py-2 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md",
          onclick: () => abortCtl && abortCtl.abort(),
        }, "取消")),
      ...[0, 1].map(() => ui.el("div", { class: "rounded-xl bg-surface-container-lowest shadow-[0_4px_20px_rgba(6,21,35,0.03)] p-space-lg flex flex-col gap-space-sm animate-pulse" },
        ui.el("div", { class: "h-4 w-1/3 rounded bg-surface-container-high" }),
        ui.el("div", { class: "h-3 w-2/3 rounded bg-surface-container" }),
        ui.el("div", { class: "h-12 rounded-lg bg-surface-container-low" }))));
  }

  function renderAiGuide(msg) {
    resultBox.innerHTML = "";
    resultBox.append(ui.el("div", { class: "rounded-xl bg-surface-container-lowest shadow-[0_4px_20px_rgba(6,21,35,0.03)] p-space-xl flex flex-col items-center gap-space-md text-center" },
      ui.icon("key_off", "text-[48px] text-outline-variant"),
      ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" }, msg),
      ui.el("button", {
        class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md",
        onclick: () => { location.hash = "#/settings"; },
      }, "前往系统设置")));
  }

  /* ---------- 结果渲染 ---------- */
  function renderResults() {
    resultBox.innerHTML = "";
    if (running) return;  // 运行中由 renderRunning 负责渲染
    if (!issues.length) {
      if (statusLine.textContent) {
        resultBox.append(ui.el("div", { class: "rounded-xl bg-surface-container-lowest shadow-[0_4px_20px_rgba(6,21,35,0.03)] p-space-xl flex flex-col items-center gap-space-md text-center" },
          ui.icon("task_alt", "text-[48px] text-secondary"),
          ui.el("p", { class: "font-headline-sm text-headline-sm text-primary" }, "未发现明显矛盾"),
          ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant" }, "所选章节与设定库保持一致。")));
      }
      return;
    }

    const highCount = issues.filter((i) => i.severity === "high").length;
    const entityCount = new Set(issues.map((i) => i.entity).filter(Boolean)).size;

    resultBox.append(
      ui.el("div", { class: "grid grid-cols-1 sm:grid-cols-3 gap-2 sm:gap-space-md" },
        statCard("问题总数", issues.length, "text-primary"),
        statCard("高严重度", highCount, "text-cinnabar-accent"),
        statCard("涉及设定", entityCount, "text-secondary")),
      ui.el("div", { class: "flex items-center gap-space-xs rounded-lg bg-secondary-fixed/60 px-space-sm py-space-xs text-on-secondary-fixed font-body-sm text-body-sm" },
        ui.icon("info", "text-[16px] shrink-0"),
        "检查结果为 AI 建议，不会修改任何内容。请逐条核实后再决定是否修改正文或设定。"),
      ...issues.map((it) => issueCard(it)));
  }

  function statCard(label, value, colorCls) {
    return ui.el("div", { class: "rounded-xl bg-surface-container-lowest shadow-[0_4px_20px_rgba(6,21,35,0.03)] p-space-md flex flex-col items-center gap-0.5" },
      ui.el("span", { class: `font-headline-lg text-headline-lg font-semibold ${colorCls}` }, String(value)),
      ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, label));
  }

  function issueCard(it) {
    const sev = SEV[it.severity] || SEV.low;
    const card = ui.el("div", { class: "rounded-xl bg-surface-container-lowest shadow-[0_4px_20px_rgba(6,21,35,0.03)] flex overflow-hidden" },
      ui.el("div", { class: `w-1 shrink-0 ${sev.bar}` }),
      ui.el("div", { class: "flex flex-col gap-space-sm p-space-lg flex-1 min-w-0" },
        ui.el("div", { class: "flex items-center gap-2 flex-wrap" },
          ui.el("span", { class: `px-2 py-0.5 rounded-full font-label-sm text-label-sm font-semibold ${sev.cls}` }, sev.label + "严重度"),
          ui.el("span", { class: "flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant font-label-sm text-label-sm" },
            ui.icon(TYPE_ICON[it.type] || "help", "text-[13px]"), it.type || "其他"),
          it.entity && ui.el("span", { class: "px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed font-label-sm text-label-sm" },
            "设定 · " + it.entity)),
        ui.el("p", { class: "font-body-md text-body-md text-on-surface" }, it.issue),
        it.quote && ui.el("div", { class: "border-l-2 border-outline-variant bg-surface-container-low rounded-r-lg px-space-sm py-space-xs font-body-sm text-body-sm text-on-surface-variant italic" },
          "“" + it.quote + "”"),
        ui.el("div", { class: "flex items-center justify-between gap-2 flex-wrap pt-1" },
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" },
            it.chapter_title ? "所在章节：" + it.chapter_title : ""),
          ui.el("div", { class: "flex items-center gap-space-xs" },
            ui.el("button", {
              class: "flex items-center gap-1 px-space-sm py-1.5 rounded-lg bg-primary text-on-primary hover:bg-primary-container font-label-md text-label-md transition-colors",
              onclick: () => jumpToChapter(it),
            }, ui.icon("location_on", "text-[16px]"), "跳转章节"),
            ui.el("button", {
              class: "flex items-center gap-1 px-space-sm py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface-variant font-label-md text-label-md transition-colors",
              onclick: () => {
                issues = issues.filter((x) => x !== it);
                renderResults();
              },
            }, ui.icon("visibility_off", "text-[16px]"), "忽略")))));
    return card;
  }

  function jumpToChapter(it) {
    const chapters = tree.flatMap((v) => v.chapters);
    const ch = chapters.find((c) => c.title === it.chapter_title);
    if (ch) {
      location.hash = `#/workbench/${workId}?chapter=${ch.id}`;
    } else {
      ui.toast(it.chapter_title ? "未找到对应章节，可能标题不完全匹配" : "该问题未标注章节", "info");
    }
  }

  await loadWorks();
});
