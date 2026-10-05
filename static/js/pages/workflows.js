/* 写作工作流（Skill 步骤序列编排：列表 / 编辑器 / 运行视图三态同页） */
registerPage("workflows", async (view, { segs }) => {
  const sub = segs[0] || "";
  if (sub === "edit") return renderEditor(view, segs[1] || "new");
  if (sub === "run") return renderRun(view, Number(segs[1]));
  return renderList(view);
});

/* ---------------- 共用 ---------------- */

const WF_LENGTH_OPTIONS = [
  ["short", "简（100~200字）"],
  ["medium", "中（300~500字）"],
  ["long", "长（800字以上）"],
  ["1000", "1000字"],
  ["2000", "2000字"],
  ["3000", "3000字"],
];

const WF_INPUT_MODES = [
  ["chapter", "本章正文"],
  ["prev_output", "前序步骤输出"],
  ["merge", "合并（正文+前序输出）"],
  ["none", "无"],
];

const WF_STEP_STATUS = {
  pending: { label: "等待", cls: "bg-surface-container-high text-on-surface-variant" },
  running: { label: "运行中", cls: "bg-primary-container text-on-primary-container" },
  awaiting_review: { label: "待确认", cls: "bg-error text-on-error" },
  approved: { label: "完成", cls: "bg-tertiary-fixed text-on-tertiary-fixed" },
  skipped: { label: "跳过", cls: "bg-surface-container-high text-on-surface-variant" },
  failed: { label: "失败", cls: "bg-error-container text-on-error-container" },
};

const WF_RUN_STATUS = {
  pending: "等待调度",
  running: "运行中",
  awaiting_review: "待确认",
  done: "已完成",
  failed: "已失败",
  cancelled: "已中止",
};

const WF_ICONS = ["alt_route", "hub", "account_tree", "auto_awesome", "edit_note", "lightbulb", "public", "group"];

function wfCard(cls, ...children) {
  return ui.el("div", { class: `rounded-2xl bg-surface-container-lowest border border-border-feather p-4 ${cls || ""}` }, ...children);
}

/* ---------------- 列表态 ---------------- */

async function renderList(view) {
  ui.setCrumb("写作工作流");

  const container = ui.el("div", { class: "max-w-6xl mx-auto px-4 py-6 space-y-6" });
  view.append(container);

  const grid = ui.el("div", { class: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" });
  const historyBox = ui.el("div", { class: "space-y-2" });

  const newBtn = ui.el("button", {
    class: "px-4 py-2 rounded-xl bg-primary text-on-primary font-label-sm text-label-sm hover:opacity-90 flex items-center gap-1",
    onclick: () => { location.hash = "#/workflows/edit/new"; },
  }, ui.icon("add", "text-[16px]"), "新建工作流");

  const head = ui.el("div", { class: "flex items-center justify-between pb-4 border-b border-outline-variant" },
    ui.el("div", { class: "font-body-sm text-body-sm text-on-surface-variant" },
      "把常用创作流程编排成步骤序列，一键运行；关键步骤可设人工确认闸，所有产出先预览再采纳。"),
    newBtn);
  container.append(head, grid,
    ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary pt-2" }, "最近运行"), historyBox);

  async function load() {
    let flows = [];
    try { flows = await api.get("/workflows"); } catch (e) { ui.toast("加载工作流失败：" + e.message, "err"); }
    grid.innerHTML = "";
    if (!flows.length) {
      grid.append(ui.el("div", { class: "col-span-full text-center py-12 text-on-surface-variant font-body-sm text-body-sm" },
        "暂无工作流，点击右上角「新建工作流」开始编排"));
    }
    flows.forEach((wf) => grid.append(renderFlowCard(wf)));

    let runs = [];
    try { runs = await api.get("/workflows/runs", { limit: 10 }); } catch (_) {}
    historyBox.innerHTML = "";
    if (!runs.length) {
      historyBox.append(ui.el("div", { class: "text-on-surface-variant font-body-sm text-body-sm py-2" }, "还没有运行记录"));
    }
    runs.forEach((r) => {
      const stLabel = WF_RUN_STATUS[r.status] || r.status;
      const row = ui.el("button", {
        class: "w-full flex items-center gap-3 px-4 py-2.5 rounded-xl bg-surface-container-lowest border border-border-feather hover:bg-surface-container-low transition-colors text-left",
        onclick: () => { location.hash = `#/workflows/run/${r.id}`; },
      },
        ui.icon(r.workflow_icon || "alt_route", "text-[18px] text-primary"),
        ui.el("span", { class: "font-body-sm text-body-sm text-on-surface" }, r.workflow_name || `工作流 #${r.workflow_id}`),
        ui.el("span", { class: `ml-auto px-2 py-0.5 rounded-full font-label-sm text-label-sm ${r.status === "done" ? "bg-tertiary-fixed text-on-tertiary-fixed" : r.status === "failed" ? "bg-error-container text-on-error-container" : "bg-primary-container text-on-primary-container"}` }, stLabel),
        ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, r.created_at || ""));
      historyBox.append(row);
    });
  }

  function renderFlowCard(wf) {
    const toggle = ui.el("button", {
      class: `material-symbols-outlined text-[20px] ${wf.enabled ? "text-primary" : "text-on-surface-variant"}`,
      title: wf.enabled ? "点击停用" : "点击启用",
      onclick: async () => {
        try {
          await api.patch(`/workflows/${wf.id}`, { enabled: wf.enabled ? 0 : 1 });
          await load();
        } catch (e) { ui.toast(e.message, "err"); }
      },
    }, wf.enabled ? "toggle_on" : "toggle_off");

    const actions = ui.el("div", { class: "flex items-center gap-2 mt-3" },
      ui.el("button", {
        class: "px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-sm text-label-sm hover:opacity-90 flex items-center gap-1",
        onclick: () => openRunDialog(wf),
      }, ui.icon("arrow_forward", "text-[15px]"), "运行"),
      ui.el("button", {
        class: "px-3 py-1.5 rounded-lg bg-surface-container text-on-surface font-label-sm text-label-sm hover:bg-surface-container-high",
        onclick: () => { location.hash = `#/workflows/edit/${wf.id}`; },
      }, "编辑"),
      ui.el("button", {
        class: "px-3 py-1.5 rounded-lg bg-surface-container text-on-surface font-label-sm text-label-sm hover:bg-surface-container-high",
        onclick: async () => {
          try {
            await api.post(`/workflows/${wf.id}/duplicate`);
            ui.toast("已创建副本", "ok");
            await load();
          } catch (e) { ui.toast(e.message, "err"); }
        },
      }, "副本"));
    if (!wf.builtin) {
      actions.append(ui.el("button", {
        class: "ml-auto px-2 py-1.5 rounded-lg text-error hover:bg-error-container/40",
        title: "删除",
        onclick: async () => {
          const ok = await ui.confirm("删除工作流", `确定删除「${wf.name}」吗？其运行记录会保留。`, "删除", true);
          if (!ok) return;
          try {
            await api.del(`/workflows/${wf.id}`);
            ui.toast("已删除", "ok");
            await load();
          } catch (e) { ui.toast(e.message, "err"); }
        },
      }, ui.icon("delete", "text-[18px]")));
    }

    return wfCard("flex flex-col gap-1",
      ui.el("div", { class: "flex items-center gap-2" },
        ui.icon(wf.icon || "alt_route", "text-[22px] text-primary"),
        ui.el("span", { class: "font-headline-sm text-headline-sm text-on-surface" }, wf.name),
        wf.builtin ? ui.el("span", { class: "px-2 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant font-label-sm text-label-sm" }, "内置示例") : null,
        wf.running_count ? ui.el("span", { class: "px-2 py-0.5 rounded-full bg-primary-container text-on-primary-container font-label-sm text-label-sm" }, `${wf.running_count} 运行中`) : null,
        ui.el("span", { class: "ml-auto" }, toggle)),
      ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant leading-relaxed" }, wf.description || ""),
      ui.el("div", { class: "font-label-sm text-label-sm text-on-surface-variant" }, `${wf.step_count} 个步骤`),
      actions);
  }

  async function openRunDialog(wf) {
    let works = [];
    try { works = await api.get("/works"); } catch (e) { ui.toast(e.message, "err"); return; }
    if (!works.length) { ui.toast("请先在书架创建作品", "err"); return; }

    const workSel = ui.el("select", { class: "w-full px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather outline-none font-body-sm text-body-sm" });
    works.forEach((w) => workSel.append(ui.el("option", { value: w.id }, w.title)));
    const chSel = ui.el("select", { class: "w-full px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather outline-none font-body-sm text-body-sm" });

    async function fillChapters() {
      chSel.innerHTML = "";
      chSel.append(ui.el("option", { value: "" }, "（不指定章节）"));
      try {
        const tree = await api.get(`/works/${workSel.value}/tree`);
        (tree || []).forEach((vol) => (vol.chapters || []).forEach((ch) => {
          chSel.append(ui.el("option", { value: ch.id }, `${vol.title} / ${ch.title}`));
        }));
      } catch (_) {}
    }
    workSel.addEventListener("change", fillChapters);
    await fillChapters();

    const content = ui.el("div", { class: "flex flex-col gap-3" },
      ui.el("label", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "选择作品"), workSel,
      ui.el("label", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "选择章节（作为运行上下文）"), chSel);

    ui.modal(`运行 · ${wf.name}`, content, [
      ui.el("button", {
        class: "px-4 py-1.5 rounded-full bg-surface-container text-on-surface hover:bg-surface-container-high text-xs",
        onclick: () => document.getElementById("modal-root").innerHTML = "",
      }, "取消"),
      ui.el("button", {
        class: "px-5 py-1.5 rounded-full bg-primary text-on-primary font-medium hover:bg-primary-container text-xs shadow-sm",
        onclick: async () => {
          try {
            const res = await api.post(`/workflows/${wf.id}/runs`, {
              work_id: Number(workSel.value),
              chapter_id: chSel.value ? Number(chSel.value) : null,
            });
            document.getElementById("modal-root").innerHTML = "";
            location.hash = `#/workflows/run/${res.run_id}`;
          } catch (e) { ui.toast("启动失败：" + e.message, "err"); }
        },
      }, "开始运行"),
    ]);
  }

  await load();
}

/* ---------------- 编辑态 ---------------- */

async function renderEditor(view, idOrNew) {
  const isNew = idOrNew === "new";
  ui.setCrumb("写作工作流", isNew ? "新建" : "编辑");

  let skills = [];
  try { skills = await api.get("/skills", { enabled: 1 }); } catch (_) {}

  let meta = { name: "", description: "", icon: "alt_route", scope: "global" };
  let steps = [];
  if (!isNew) {
    try {
      const wf = await api.get(`/workflows/${idOrNew}`);
      meta = { name: wf.name, description: wf.description, icon: wf.icon, scope: wf.scope };
      steps = (wf.steps || []).map((s) => ({
        title: s.title, skill_id: s.skill_id, input_mode: s.input_mode,
        prev_step_seq: s.prev_step_seq, instruction: s.instruction || "",
        length: s.length || "medium", requires_review: s.requires_review ? 1 : 0,
        enabled: s.enabled ? 1 : 0,
      }));
    } catch (e) { ui.toast("加载工作流失败：" + e.message, "err"); location.hash = "#/workflows"; return; }
  }

  const container = ui.el("div", { class: "max-w-4xl mx-auto px-4 py-6 space-y-4" });
  view.append(container);

  const inputCls = "w-full px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-sm text-body-sm";

  const nameIn = ui.el("input", { class: inputCls, placeholder: "工作流名称，如：章节标准生产流", value: meta.name });
  const descIn = ui.el("textarea", { class: inputCls + " min-h-[60px] resize-y", placeholder: "说明这条流程做什么、适合什么时候用" }, meta.description);
  const iconSel = ui.el("select", { class: inputCls });
  WF_ICONS.forEach((ic) => iconSel.append(ui.el("option", { value: ic, selected: ic === meta.icon ? "" : undefined }, ic)));

  const metaCard = wfCard("grid grid-cols-1 md:grid-cols-2 gap-3",
    ui.el("div", {}, ui.el("label", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "名称"), nameIn),
    ui.el("div", {}, ui.el("label", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "图标"), iconSel),
    ui.el("div", { class: "md:col-span-2" }, ui.el("label", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "说明"), descIn));

  const stepsBox = ui.el("div", { class: "flex flex-col gap-3" });
  const addBtn = ui.el("button", {
    class: "px-4 py-2 rounded-xl bg-surface-container text-on-surface font-label-sm text-label-sm hover:bg-surface-container-high flex items-center gap-1 self-start",
    onclick: () => {
      steps.push({ title: `步骤 ${steps.length + 1}`, skill_id: skills[0] ? skills[0].id : null, input_mode: "chapter", prev_step_seq: null, instruction: "", length: "medium", requires_review: 1, enabled: 1 });
      renderSteps();
    },
  }, ui.icon("add", "text-[16px]"), "添加步骤");

  const saveBtn = ui.el("button", {
    class: "px-5 py-2 rounded-xl bg-primary text-on-primary font-label-sm text-label-sm hover:opacity-90",
    onclick: save,
  }, "保存工作流");
  const backBtn = ui.el("button", {
    class: "px-4 py-2 rounded-xl bg-surface-container text-on-surface font-label-sm text-label-sm hover:bg-surface-container-high",
    onclick: () => { location.hash = "#/workflows"; },
  }, "返回列表");

  container.append(metaCard,
    ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary pt-2" }, "步骤（可拖拽排序）"),
    stepsBox, addBtn,
    ui.el("div", { class: "flex gap-3 pt-2" }, saveBtn, backBtn));

  let dragIdx = null;

  function renderSteps() {
    stepsBox.innerHTML = "";
    if (!steps.length) {
      stepsBox.append(ui.el("div", { class: "text-center py-8 text-on-surface-variant font-body-sm text-body-sm rounded-2xl border border-dashed border-outline-variant" },
        "还没有步骤，点击下方「添加步骤」"));
    }
    steps.forEach((st, i) => stepsBox.append(renderStep(st, i)));
  }

  function renderStep(st, i) {
    const card = wfCard("flex flex-col gap-3");
    card.draggable = true;
    card.addEventListener("dragstart", () => { dragIdx = i; card.classList.add("opacity-50"); });
    card.addEventListener("dragend", () => { dragIdx = null; card.classList.remove("opacity-50"); });
    card.addEventListener("dragover", (e) => e.preventDefault());
    card.addEventListener("drop", (e) => {
      e.preventDefault();
      if (dragIdx === null || dragIdx === i) return;
      const [moved] = steps.splice(dragIdx, 1);
      steps.splice(i, 0, moved);
      renderSteps();
    });

    const titleIn = ui.el("input", { class: inputCls + " flex-1", value: st.title, placeholder: "步骤展示名，如：生成本章草稿" });
    titleIn.addEventListener("input", () => { st.title = titleIn.value; });

    const skillSel = ui.el("select", { class: inputCls });
    skills.forEach((sk) => skillSel.append(ui.el("option", { value: sk.id, selected: sk.id === st.skill_id ? "" : undefined },
      `${sk.title}（${sk.applies_to || "通用"}）`)));
    skillSel.addEventListener("change", () => { st.skill_id = skillSel.value ? Number(skillSel.value) : null; });

    const modeSel = ui.el("select", { class: inputCls });
    WF_INPUT_MODES.forEach(([v, l]) => modeSel.append(ui.el("option", { value: v, selected: v === st.input_mode ? "" : undefined }, l)));
    modeSel.addEventListener("change", () => { st.input_mode = modeSel.value; prevWrap.style.display = (modeSel.value === "prev_output" || modeSel.value === "merge") ? "" : "none"; });

    const prevSel = ui.el("select", { class: inputCls });
    prevSel.append(ui.el("option", { value: "" }, "上一步（默认）"));
    steps.forEach((s2, j) => {
      if (j < i) prevSel.append(ui.el("option", { value: j, selected: j === st.prev_step_seq ? "" : undefined }, `第 ${j + 1} 步 · ${s2.title}`));
    });
    prevSel.addEventListener("change", () => { st.prev_step_seq = prevSel.value === "" ? null : Number(prevSel.value); });
    const prevWrap = ui.el("div", { style: `display:${(st.input_mode === "prev_output" || st.input_mode === "merge") ? "" : "none"}` },
      ui.el("label", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "引用哪一步的输出"), prevSel);

    const lenSel = ui.el("select", { class: inputCls });
    WF_LENGTH_OPTIONS.forEach(([v, l]) => lenSel.append(ui.el("option", { value: v, selected: v === st.length ? "" : undefined }, l)));
    lenSel.addEventListener("change", () => { st.length = lenSel.value; });

    const instIn = ui.el("textarea", { class: inputCls + " min-h-[56px] resize-y", placeholder: "固定补充指令（可引用 {{steps.0.output}} 这样的前序输出）" }, st.instruction);
    instIn.addEventListener("input", () => { st.instruction = instIn.value; });

    const reviewToggle = ui.el("button", {
      class: `flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-label-sm text-label-sm ${st.requires_review ? "bg-error/10 text-error border border-error/30" : "bg-surface-container text-on-surface-variant"}`,
      title: "开启后，该步骤完成会暂停等待你确认，未确认绝不推进",
      onclick: () => { st.requires_review = st.requires_review ? 0 : 1; renderSteps(); },
    }, ui.icon(st.requires_review ? "check_circle" : "radio_button_unchecked", "text-[15px]"), "完成后需我确认");

    const enabledToggle = ui.el("button", {
      class: `material-symbols-outlined text-[20px] ${st.enabled ? "text-primary" : "text-on-surface-variant"}`,
      title: st.enabled ? "点击停用该步骤" : "点击启用该步骤",
      onclick: () => { st.enabled = st.enabled ? 0 : 1; renderSteps(); },
    }, st.enabled ? "toggle_on" : "toggle_off");

    const delBtn = ui.el("button", {
      class: "px-2 py-1 rounded-lg text-error hover:bg-error-container/40",
      title: "删除该步骤",
      onclick: () => { steps.splice(i, 1); renderSteps(); },
    }, ui.icon("delete", "text-[18px]"));

    card.append(
      ui.el("div", { class: "flex items-center gap-2" },
        ui.el("span", { class: "w-6 h-6 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center font-label-sm text-label-sm shrink-0" }, String(i + 1)),
        titleIn, enabledToggle, delBtn),
      ui.el("div", { class: "grid grid-cols-1 md:grid-cols-3 gap-3" },
        ui.el("div", {}, ui.el("label", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "绑定 Skill"), skillSel),
        ui.el("div", {}, ui.el("label", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "输入来源"), modeSel),
        ui.el("div", {}, ui.el("label", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "长度档位"), lenSel)),
      prevWrap,
      ui.el("div", {}, ui.el("label", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "固定指令"), instIn),
      ui.el("div", { class: "flex items-center gap-2" }, reviewToggle,
        ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "确认闸是安全红线：未确认的输出不会进入下一步")));
    return card;
  }

  async function save() {
    const name = nameIn.value.trim();
    if (!name) { ui.toast("请填写工作流名称", "err"); return; }
    const payloadSteps = steps.map((s, i) => ({
      title: (s.title || `步骤 ${i + 1}`).trim(),
      skill_id: s.skill_id,
      input_mode: s.input_mode,
      prev_step_seq: s.prev_step_seq,
      output_var: `step${i}`,
      instruction: s.instruction || "",
      length: s.length,
      candidates: 1,
      requires_review: s.requires_review ? 1 : 0,
      enabled: s.enabled ? 1 : 0,
    }));
    try {
      if (isNew) {
        await api.post("/workflows", {
          name, description: descIn.value.trim(), icon: iconSel.value, scope: "global", steps: payloadSteps,
        });
        ui.toast("工作流已创建", "ok");
      } else {
        await api.patch(`/workflows/${idOrNew}`, { name, description: descIn.value.trim(), icon: iconSel.value });
        await api.put(`/workflows/${idOrNew}/steps`, { steps: payloadSteps });
        ui.toast("工作流已保存", "ok");
      }
      location.hash = "#/workflows";
    } catch (e) { ui.toast("保存失败：" + e.message, "err"); }
  }

  renderSteps();
}

/* ---------------- 运行态 ---------------- */

async function renderRun(view, runId) {
  ui.setCrumb("写作工作流", `运行 #${runId}`);

  const container = ui.el("div", { class: "max-w-3xl mx-auto px-4 py-6 space-y-4" });
  view.append(container);

  const headCard = wfCard("flex flex-col gap-2");
  const stepsBox = ui.el("div", { class: "flex flex-col gap-3" });
  const backBtn = ui.el("button", {
    class: "px-4 py-2 rounded-xl bg-surface-container text-on-surface font-label-sm text-label-sm hover:bg-surface-container-high self-start",
    onclick: () => { location.hash = "#/workflows"; },
  }, "返回列表");
  container.append(headCard, stepsBox, backBtn);

  let pollTimer = null;
  let editingSeq = null;

  async function tick() {
    let run;
    try { run = await api.get(`/workflows/runs/${runId}`); }
    catch (e) { stopPoll(); headCard.innerHTML = ""; headCard.append(ui.el("div", { class: "text-error font-body-sm" }, "加载运行失败：" + e.message)); return; }
    render(run);
    if (["pending", "running", "awaiting_review"].includes(run.status)) {
      if (!pollTimer) pollTimer = setInterval(() => {
        if (!location.hash.startsWith(`#/workflows/run/${runId}`)) { stopPoll(); return; }
        tick();
      }, 1000);
    } else {
      stopPoll();
    }
  }

  function stopPoll() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null; } }

  function render(run) {
    headCard.innerHTML = "";
    const pct = run.total_steps ? Math.round((run.finished_steps / run.total_steps) * 100) : 0;
    const stLabel = WF_RUN_STATUS[run.status] || run.status;
    headCard.append(
      ui.el("div", { class: "flex items-center gap-2" },
        ui.icon(run.workflow_icon || "alt_route", "text-[22px] text-primary"),
        ui.el("span", { class: "font-headline-sm text-headline-sm text-on-surface" }, run.workflow_name || "工作流"),
        ui.el("span", { class: `px-2 py-0.5 rounded-full font-label-sm text-label-sm ${run.status === "done" ? "bg-tertiary-fixed text-on-tertiary-fixed" : run.status === "failed" ? "bg-error-container text-on-error-container" : "bg-primary-container text-on-primary-container"}` }, stLabel),
        run.token_used ? ui.el("span", { class: "ml-auto font-label-sm text-label-sm text-on-surface-variant" }, `累计 token ${run.token_used}`) : null),
      ui.el("div", { class: "flex items-center gap-3" },
        ui.el("div", { class: "flex-1 h-2 rounded-full bg-surface-container overflow-hidden" },
          ui.el("div", { class: "h-full bg-primary rounded-full transition-all", style: `width:${pct}%` })),
        ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant shrink-0" }, `${run.finished_steps}/${run.total_steps} 步`)),
      run.error_msg ? ui.el("div", { class: "font-body-sm text-body-sm text-error" }, run.error_msg) : null,
      ["running", "awaiting_review", "pending"].includes(run.status)
        ? ui.el("button", {
            class: "self-start px-3 py-1.5 rounded-lg bg-error-container text-on-error-container font-label-sm text-label-sm hover:opacity-90",
            onclick: async () => {
              const ok = await ui.confirm("中止运行", "确定中止本次运行吗？已确认步骤的输出会保留可回看。", "中止", true);
              if (!ok) return;
              try { await api.post(`/workflows/runs/${runId}/cancel`); tick(); } catch (e) { ui.toast(e.message, "err"); }
            },
          }, "中止运行")
        : null,
      ["failed", "cancelled"].includes(run.status)
        ? ui.el("button", {
            class: "self-start px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-sm text-label-sm hover:opacity-90",
            onclick: async () => {
              try { await api.post(`/workflows/runs/${runId}/retry`); tick(); } catch (e) { ui.toast("重跑失败：" + e.message, "err"); }
            },
          }, "从失败处重跑")
        : null);

    stepsBox.innerHTML = "";
    (run.steps || []).forEach((s) => stepsBox.append(renderRunStep(run, s)));
  }


  function parseWorkflowOptions(text) {
    if (!text || typeof text !== "string") return [];
    const lines = text.split("\n");
    const optionHeaders = [];
    const headerRe = /^\s*(?:[#*>\-\s]*【(?:方案|选项)\s*([0-9一二三四五六七八九十A-Za-z]+)】|[#*>\-\s]*(?:方案|选项|Option)\s*([0-9一二三四五六七八九十A-Za-z]+)[：:\s]|(?:\*{2}|#{2,4})\s*(?:方案|选项|Option)\s*([0-9一二三四五六七八九十A-Za-z]+).*)/;

    lines.forEach((line, idx) => {
      const m = line.match(headerRe);
      if (m) {
        optionHeaders.push({ index: idx, title: line.trim().replace(/^[#*>\-\s]+|[#*>\-\s]+$/g, "") });
      }
    });

    if (optionHeaders.length < 2) return [];

    const options = [];
    for (let i = 0; i < optionHeaders.length; i++) {
      const cur = optionHeaders[i];
      const next = optionHeaders[i + 1];
      const startIdx = cur.index;
      const endIdx = next ? next.index : lines.length;
      const optLines = lines.slice(startIdx, endIdx);
      const content = optLines.join("\n").trim();
      options.push({
        title: cur.title || `方案 ${i + 1}`,
        content,
      });
    }
    return options;
  }

  function renderRunStep(run, s) {
    const st = WF_STEP_STATUS[s.status] || { label: s.status, cls: "bg-surface-container-high text-on-surface-variant" };
    const waiting = s.status === "awaiting_review";

    const header = ui.el("div", { class: "flex items-center gap-2" },
      ui.el("span", { class: `w-6 h-6 rounded-full flex items-center justify-center font-label-sm text-label-sm shrink-0 ${waiting ? "bg-error text-on-error" : "bg-primary-container text-on-primary-container"}` }, String(s.step_seq + 1)),
      ui.el("span", { class: "font-body-sm text-body-sm text-on-surface font-medium" }, s.title),
      ui.el("span", { class: `px-2 py-0.5 rounded-full font-label-sm text-label-sm ${st.cls}` }, st.label),
      s.elapsed_ms ? ui.el("span", { class: "ml-auto font-label-sm text-label-sm text-on-surface-variant" }, `${(s.elapsed_ms / 1000).toFixed(1)}s · ${s.token_used || 0} token`) : null);

    const card = wfCard(`flex flex-col gap-3 ${waiting ? "border-error/50 ring-1 ring-error/30" : ""}`, header);

    if (s.review_note) {
      card.append(ui.el("div", { class: "font-label-sm text-label-sm text-on-surface-variant" }, `确认备注：${s.review_note}`));
    }

    if (s.output) {
      if (waiting && editingSeq === s.step_seq) {
        const ta = ui.el("textarea", { class: "w-full min-h-[200px] px-3 py-2 rounded-lg bg-surface-container-low border border-primary outline-none font-body-sm text-body-sm resize-y" }, s.output);
        card.append(ta,
          ui.el("div", { class: "flex gap-2" },
            ui.el("button", {
              class: "px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-sm text-label-sm hover:opacity-90",
              onclick: async () => {
                try {
                  await api.post(`/workflows/runs/${runId}/steps/${s.step_seq}/review`, { action: "edit", content: ta.value });
                  editingSeq = null; tick();
                } catch (e) { ui.toast(e.message, "err"); }
              },
            }, "以修改稿继续"),
            ui.el("button", {
              class: "px-3 py-1.5 rounded-lg bg-surface-container text-on-surface font-label-sm text-label-sm",
              onclick: () => { editingSeq = null; tick(); },
            }, "取消编辑")));
      } else {
        const pre = ui.el("pre", {
          class: `whitespace-pre-wrap font-body-sm text-body-sm text-on-surface bg-surface-container-low rounded-xl p-3 overflow-x-auto ${waiting ? "" : "max-h-64 overflow-y-auto"}`,
        }, s.output);
        card.append(pre);
      }
    }

    const detectedOptions = waiting ? parseWorkflowOptions(s.output) : [];
    if (waiting && editingSeq !== s.step_seq && detectedOptions.length >= 2) {
      const optContainer = ui.el("div", { class: "flex flex-col gap-2 p-3 rounded-xl bg-primary/5 border border-primary/20" },
        ui.el("div", { class: "flex items-center gap-1.5 font-label-md text-label-md text-primary font-semibold" },
          ui.icon("alt_route", "text-[18px]"), `检测到 AI 提供了 ${detectedOptions.length} 个备选方案，可一键采纳对应方案进入下一步：`));

      const optGrid = ui.el("div", { class: "grid grid-cols-1 md:grid-cols-2 gap-2" });
      detectedOptions.forEach((opt, oIdx) => {
        const optCard = ui.el("div", { class: "flex flex-col justify-between p-2.5 rounded-lg bg-surface border border-outline-variant/60 shadow-xs hover:border-primary transition-all" },
          ui.el("div", { class: "flex flex-col gap-1 mb-2" },
            ui.el("span", { class: "font-label-sm text-label-sm font-semibold text-primary" }, opt.title),
            ui.el("div", { class: "font-body-sm text-body-sm text-on-surface-variant line-clamp-3 whitespace-pre-wrap" }, opt.content)),
          ui.el("button", {
            class: "self-end flex items-center gap-1 px-2.5 py-1 rounded bg-primary text-on-primary font-label-sm text-label-sm hover:opacity-90 transition-opacity",
            onclick: async () => {
              try {
                await api.post(`/workflows/runs/${runId}/steps/${s.step_seq}/review`, {
                  action: "edit",
                  content: opt.content,
                  note: `选用「${opt.title}」`,
                });
                ui.toast(`已选用「${opt.title}」继续工作流`, "ok");
                tick();
              } catch (e) {
                ui.toast(e.message, "err");
              }
            },
          }, ui.icon("check", "text-[14px]"), "选用此方案继续"));
        optGrid.append(optCard);
      });
      optContainer.append(optGrid);
      card.append(optContainer);
    }

    if (waiting && editingSeq !== s.step_seq) {
      card.append(ui.el("div", { class: "flex flex-wrap gap-2" },
        ui.el("button", {
          class: "px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-sm text-label-sm hover:opacity-90",
          onclick: async () => {
            try { await api.post(`/workflows/runs/${runId}/steps/${s.step_seq}/review`, { action: "approve" }); tick(); }
            catch (e) { ui.toast(e.message, "err"); }
          },
        }, "采纳并继续"),
        ui.el("button", {
          class: "px-3 py-1.5 rounded-lg bg-surface-container text-on-surface font-label-sm text-label-sm hover:bg-surface-container-high",
          onclick: () => { editingSeq = s.step_seq; tick(); },
        }, "编辑后继续"),
        ui.el("button", {
          class: "px-3 py-1.5 rounded-lg bg-surface-container text-on-surface font-label-sm text-label-sm hover:bg-surface-container-high",
          onclick: async () => {
            try { await api.post(`/workflows/runs/${runId}/steps/${s.step_seq}/review`, { action: "skip" }); tick(); }
            catch (e) { ui.toast(e.message, "err"); }
          },
        }, "跳过"),
        ui.el("button", {
          class: "px-3 py-1.5 rounded-lg bg-error-container text-on-error-container font-label-sm text-label-sm hover:opacity-90",
          onclick: async () => {
            const ok = await ui.confirm("中止运行", "确定中止本次运行吗？已确认步骤的输出会保留可回看。", "中止", true);
            if (!ok) return;
            try { await api.post(`/workflows/runs/${runId}/steps/${s.step_seq}/review`, { action: "abort" }); tick(); }
            catch (e) { ui.toast(e.message, "err"); }
          },
        }, "中止运行")));
    }
    return card;
  }

  await tick();
}
