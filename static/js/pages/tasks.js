/* AI 任务台账页 */
registerPage("tasks", async (view) => {
  ui.setCrumb("AI 任务记录");

  let works = [];
  try { works = await api.get("/works"); } catch (e) { ui.toast(e.message, "err"); }

  const workSel = ui.el("select", { class: "px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-md text-body-md" });
  workSel.append(ui.el("option", { value: "" }, "全部作品"));
  for (const w of works) workSel.append(ui.el("option", { value: w.id }, w.title));

  const typeSel = ui.el("select", { class: "px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-md text-body-md" });
  typeSel.append(ui.el("option", { value: "" }, "全部类型"));
  for (const t of [["continue", "续写"], ["expand", "扩写"], ["condense", "缩写"], ["polish", "润色"], ["analyze", "分析"], ["audit", "一键审查"], ["img_cover", "封面出图"], ["img_illustration", "插图出图"], ["alchemy_analyze", "拆书蒸馏"], ["alchemy_extract_lore", "资料融汇"], ["alchemy_brew", "开炉推演"]]) {
    typeSel.append(ui.el("option", { value: t[0] }, t[1]));
  }

  const listBox = ui.el("div", { class: "flex flex-col gap-space-sm" });

  const refreshBtn = ui.el("button", {
    class: "flex items-center gap-1 px-space-sm py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface transition-all",
    onclick: load,
  }, ui.icon("refresh", "text-[18px]"), "刷新");

  view.append(
    ui.el("div", { class: "flex flex-col gap-space-lg" },
      ui.el("div", { class: "flex flex-col gap-1" },
        ui.el("span", { class: "font-label-sm text-label-sm text-secondary tracking-widest uppercase" }, "AI TASK LEDGER"),
        ui.el("h1", { class: "font-display text-display text-primary tracking-tight" }, "AI 任务记录")),
      ui.el("div", { class: "flex flex-wrap items-center gap-2" }, workSel, typeSel, refreshBtn),
      listBox));

  async function load() {
    listBox.innerHTML = "";
    const params = new URLSearchParams();
    if (workSel.value) params.set("work_id", workSel.value);
    if (typeSel.value) params.set("task_type", typeSel.value);
    let tasks;
    try { tasks = await api.get("/tasks?" + params.toString()); }
    catch (e) { ui.toast(e.message, "err"); return; }
    if (!tasks.length) {
      listBox.append(ui.el("div", { class: "text-center py-space-xl text-on-surface-variant font-body-md" }, "暂无 AI 任务记录"));
      return;
    }
    for (const t of tasks) listBox.append(taskCard(t));
  }

  function taskCard(t) {
    const STATUS = {
      pending: { label: "排队中", cls: "bg-surface-container text-on-surface-variant" },
      running: { label: "运行中", cls: "bg-secondary-fixed text-on-secondary-fixed" },
      done: { label: "已完成", cls: "bg-primary-fixed text-on-primary-fixed" },
      failed: { label: "失败", cls: "bg-error-container text-on-error-container" },
      cancelled: { label: "已取消", cls: "bg-surface-container-high text-on-surface-variant" },
    };
    const st = STATUS[t.status] || STATUS.pending;
    const work = works.find((w) => w.id === t.work_id);
    let outputPreview = "";
    try {
      const out = JSON.parse(t.output_json || "{}");
      if (out.candidates && out.candidates.length) outputPreview = out.candidates[0].slice(0, 120);
      else if (out.issues) outputPreview = `发现 ${out.issues.length} 个问题`;
      else if (out.prompt) outputPreview = out.prompt.slice(0, 120);
    } catch (_) { outputPreview = t.output_json ? t.output_json.slice(0, 120) : ""; }

    return ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-md shadow-[0_4px_20px_rgba(6,21,35,0.03)] flex flex-col gap-space-sm" },
      ui.el("div", { class: "flex items-center justify-between" },
        ui.el("div", { class: "flex items-center gap-2" },
          ui.el("span", { class: `px-2 py-0.5 rounded-full font-label-sm text-label-sm ${st.cls}` }, st.label),
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, t.task_type),
          work && ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, `《${work.title}》`)),
        ui.el("span", { class: "font-label-sm text-label-sm text-outline" }, (t.created_at || "").slice(5, 16))),
      ui.el("div", { class: "font-body-sm text-body-sm text-on-surface" }, t.input_summary || "（无输入摘要）"),
      outputPreview && ui.el("div", { class: "font-body-sm text-body-sm text-on-surface-variant bg-surface-container-low rounded-lg px-space-sm py-space-xs truncate" }, outputPreview),
      t.error_msg && ui.el("div", { class: "font-body-sm text-body-sm text-error bg-error-container/30 rounded-lg px-space-sm py-space-xs" }, t.error_msg),
      ui.el("div", { class: "flex items-center gap-3 font-label-sm text-label-sm text-on-surface-variant" },
        t.elapsed_ms ? `耗时 ${Math.round(t.elapsed_ms / 1000)}s` : null,
        t.token_used ? `Token ${t.token_used}` : null),
      ui.el("div", { class: "flex items-center gap-2" },
        t.status === "failed" && ui.el("button", {
          class: "px-3 py-1.5 rounded-lg bg-secondary-container text-on-secondary-container font-label-sm text-label-sm hover:bg-secondary transition-colors",
          onclick: async () => {
            try {
              await api.post(`/tasks/${t.id}/retry`);
              ui.toast("已创建重试任务", "ok");
              load();
            } catch (e) { ui.toast(e.message, "err"); }
          },
        }, "重试"),
        (t.status === "pending" || t.status === "running") && ui.el("button", {
          class: "px-3 py-1.5 rounded-lg bg-surface-container text-on-surface-variant font-label-sm text-label-sm hover:bg-error-container hover:text-on-error-container transition-colors",
          onclick: async () => {
            try {
              await api.post(`/tasks/${t.id}/cancel`);
              ui.toast("已取消", "ok");
              load();
            } catch (e) { ui.toast(e.message, "err"); }
          },
        }, "取消")));
  }

  workSel.addEventListener("change", load);
  typeSel.addEventListener("change", load);
  await load();
});
