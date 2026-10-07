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

    const outlineSel = ui.el("select", { class: "w-full px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather outline-none font-body-sm text-body-sm" });

    async function fillContextTargets() {
      chSel.innerHTML = "";
      chSel.append(ui.el("option", { value: "" }, "（不指定章节）"));
      outlineSel.innerHTML = "";
      outlineSel.append(ui.el("option", { value: "" }, "（不指定大纲节点）"));
      try {
        const [tree, oTree] = await Promise.all([
          api.get(`/works/${workSel.value}/tree`).catch(() => []),
          api.get(`/works/${workSel.value}/outline`).catch(() => []),
        ]);
        (tree || []).forEach((vol) => (vol.chapters || []).forEach((ch) => {
          chSel.append(ui.el("option", { value: ch.id }, `${vol.title} / ${ch.title}`));
        }));
        (function walk(nodes, prefix) {
          (nodes || []).forEach((n) => {
            outlineSel.append(ui.el("option", { value: n.id }, `${prefix}${n.title}`));
            if (n.children) walk(n.children, prefix + "  └ ");
          });
        })(oTree, "");
      } catch (_) {}
    }
    workSel.addEventListener("change", fillContextTargets);
    await fillContextTargets();

    const content = ui.el("div", { class: "flex flex-col gap-3" },
      ui.el("label", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "选择作品"), workSel,
      ui.el("label", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "选择目标大纲节点（自动装载细纲与伏笔脉络）"), outlineSel,
      ui.el("label", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "选择章节正文（可选前情上下文）"), chSel);

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
              outline_node_id: outlineSel.value ? Number(outlineSel.value) : null,
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
      steps = (wf.steps || []).map((s) => {
        const refSeqs = Array.isArray(s.ref_step_seqs) ? s.ref_step_seqs : (s.prev_step_seq !== null && s.prev_step_seq !== undefined ? [s.prev_step_seq] : []);
        let ctxSources = Array.isArray(s.context_sources) && s.context_sources.length ? s.context_sources : null;
        if (!ctxSources) {
          if (s.input_mode === "chapter" || s.input_mode === "merge") ctxSources = ["chapter", "triad"];
          else ctxSources = [];
        }
        return {
          title: s.title,
          skill_id: s.skill_id,
          input_mode: s.input_mode || "chapter",
          prev_step_seq: s.prev_step_seq,
          ref_step_seqs: refSeqs,
          context_sources: ctxSources,
          instruction: s.instruction || "",
          length: s.length || "medium",
          requires_review: s.requires_review ? 1 : 0,
          enabled: s.enabled ? 1 : 0,
        };
      });
    } catch (e) { ui.toast("加载工作流失败：" + e.message, "err"); location.hash = "#/workflows"; return; }
  }

  const container = ui.el("div", { class: "max-w-4xl mx-auto px-4 py-6 space-y-4" });
  view.append(container);

  const inputCls = "w-full px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-sm text-body-sm";

  const nameIn = ui.el("input", { class: inputCls, placeholder: "工作流名称，例如：新章标准写作流", value: meta.name });
  const descIn = ui.el("textarea", { class: inputCls + " min-h-[60px] resize-y", placeholder: "说明（这是什么、适合什么时候用）" }, meta.description);
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
      steps.push({
        title: `步骤 ${steps.length + 1}`,
        skill_id: skills[0] ? skills[0].id : null,
        input_mode: "chapter",
        prev_step_seq: null,
        ref_step_seqs: [],
        context_sources: ["chapter", "triad"],
        instruction: "",
        length: "medium",
        requires_review: 1,
        enabled: 1
      });
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
        "暂无步骤，点击下方按钮添加步骤"));
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

    const titleIn = ui.el("input", { class: inputCls + " flex-1", value: st.title, placeholder: "步骤展示名称，例如：生成本章草稿" });
    titleIn.addEventListener("input", () => { st.title = titleIn.value; });

    const skillSel = ui.el("select", { class: inputCls });
    skills.forEach((sk) => skillSel.append(ui.el("option", { value: sk.id, selected: sk.id === st.skill_id ? "" : undefined },
      `${sk.title}（${sk.applies_to || "通用"}）`)));
    skillSel.addEventListener("change", () => { st.skill_id = skillSel.value ? Number(skillSel.value) : null; });

    const lenSel = ui.el("select", { class: inputCls });
    WF_LENGTH_OPTIONS.forEach(([v, l]) => lenSel.append(ui.el("option", { value: v, selected: v === st.length ? "" : undefined }, l)));
    lenSel.addEventListener("change", () => { st.length = lenSel.value; });

    // 辅助同步兼容字段
    function syncInputModeCompat() {
      const hasSteps = st.ref_step_seqs && st.ref_step_seqs.length > 0;
      const hasText = st.context_sources && (st.context_sources.includes("chapter") || st.context_sources.includes("triad"));
      if (hasSteps && hasText) {
        st.input_mode = "merge";
      } else if (hasSteps) {
        st.input_mode = "prev_output";
      } else if (hasText) {
        st.input_mode = "chapter";
      } else {
        st.input_mode = "none";
      }
      st.prev_step_seq = hasSteps ? st.ref_step_seqs[st.ref_step_seqs.length - 1] : null;
    }

    // --- 上下文装配源模块（整合基础上下文与前序多步骤勾选） ---
    const ctxBox = ui.el("div", { class: "p-3 rounded-xl bg-surface-container-low border border-border-feather flex flex-col gap-2.5" });

    ctxBox.append(ui.el("div", { class: "flex items-center justify-between" },
      ui.el("span", { class: "font-label-sm text-label-sm text-on-surface font-medium flex items-center gap-1.5" },
        ui.icon("tune", "text-[16px] text-primary"),
        "步骤上下文输入（动态装配）"
      ),
      ui.el("span", { class: "font-label-sm text-label-xs text-on-surface-variant" }, "自由组合注入给本步骤 AI 的信息")
    ));

    // 1. 基础源（章节正文、大纲三位一体）
    const baseSourcesRow = ui.el("div", { class: "flex flex-wrap items-center gap-4 pt-0.5" });

    const chkChapter = ui.el("input", { type: "checkbox", class: "accent-primary cursor-pointer w-4 h-4" });
    chkChapter.checked = st.context_sources.includes("chapter");
    const lblChapter = ui.el("label", { class: "flex items-center gap-1.5 cursor-pointer font-label-sm text-label-sm text-on-surface select-none" },
      chkChapter,
      ui.icon("article", "text-[16px] text-primary"),
      "当前章节正文"
    );

    const chkTriad = ui.el("input", { type: "checkbox", class: "accent-primary cursor-pointer w-4 h-4" });
    chkTriad.checked = st.context_sources.includes("triad");
    const lblTriad = ui.el("label", { class: "flex items-center gap-1.5 cursor-pointer font-label-sm text-label-sm text-on-surface select-none" },
      chkTriad,
      ui.icon("account_tree", "text-[16px] text-primary"),
      "目标大纲节点与三位一体剧情卡"
    );

    function syncBaseSources() {
      const src = [];
      if (chkChapter.checked) src.push("chapter");
      if (chkTriad.checked) src.push("triad");
      st.context_sources = src;
      syncInputModeCompat();
    }
    chkChapter.addEventListener("change", syncBaseSources);
    chkTriad.addEventListener("change", syncBaseSources);

    baseSourcesRow.append(lblChapter, lblTriad);
    ctxBox.append(baseSourcesRow);

    // 2. 前序步骤引用勾选
    const prevStepsRow = ui.el("div", { class: "flex flex-col gap-1.5 pt-2 border-t border-border-feather/60" });
    const prevHeader = ui.el("div", { class: "flex items-center justify-between" },
      ui.el("span", { class: "font-label-sm text-label-xs text-on-surface-variant flex items-center gap-1" },
        ui.icon("dynamic_feed", "text-[15px]"),
        "前序步骤产出参考（支持多选）"
      )
    );

    if (i > 1) {
      const toolActions = ui.el("div", { class: "flex items-center gap-2.5" },
        ui.el("button", {
          type: "button",
          class: "font-label-sm text-label-xs text-primary hover:underline",
          onclick: (e) => {
            e.preventDefault();
            st.ref_step_seqs = steps.slice(0, i).map((_, idx) => idx);
            syncInputModeCompat();
            renderSteps();
          }
        }, "全选前序"),
        ui.el("button", {
          type: "button",
          class: "font-label-sm text-label-xs text-on-surface-variant hover:underline",
          onclick: (e) => {
            e.preventDefault();
            st.ref_step_seqs = [];
            syncInputModeCompat();
            renderSteps();
          }
        }, "清空前序")
      );
      prevHeader.append(toolActions);
    }
    prevStepsRow.append(prevHeader);

    if (i === 0) {
      prevStepsRow.append(ui.el("span", { class: "font-label-sm text-label-xs text-on-surface-variant/80 italic py-1" }, "（第 1 步为流程起点，无前序步骤可引用）"));
    } else {
      const chipsWrap = ui.el("div", { class: "flex flex-wrap gap-2 pt-1" });
      for (let j = 0; j < i; j++) {
        const prevSt = steps[j];
        const isChecked = st.ref_step_seqs.includes(j);
        const chip = ui.el("button", {
          type: "button",
          class: `flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-label-xs font-label-sm transition-all ${
            isChecked
              ? "bg-primary-container text-on-primary-container border-primary/40 font-medium shadow-xs"
              : "bg-surface-container text-on-surface-variant border-border-feather hover:border-outline-variant"
          }`,
          onclick: (e) => {
            e.preventDefault();
            if (st.ref_step_seqs.includes(j)) {
              st.ref_step_seqs = st.ref_step_seqs.filter((x) => x !== j);
            } else {
              st.ref_step_seqs.push(j);
              st.ref_step_seqs.sort((a, b) => a - b);
            }
            syncInputModeCompat();
            renderSteps();
          }
        },
          ui.icon(isChecked ? "check_circle" : "add_circle_outline", "text-[14px]"),
          `步骤 ${j + 1}: ${prevSt.title || "未命名"}`
        );
        chipsWrap.append(chip);
      }
      prevStepsRow.append(chipsWrap);
    }
    ctxBox.append(prevStepsRow);

    const instIn = ui.el("textarea", { class: inputCls + " min-h-[56px] resize-y", placeholder: "固定补充指令（可引用 {{steps.0.output}} 注入指定前序输出）" }, st.instruction);
    instIn.addEventListener("input", () => { st.instruction = instIn.value; });

    const reviewToggle = ui.el("button", {
      class: `flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-label-sm text-label-sm ${st.requires_review ? "bg-error/10 text-error border border-error/30" : "bg-surface-container text-on-surface-variant"}`,
      title: "开启后，该步骤完成后暂停，等待人工确认；未确认绝不推进下一步",
      onclick: () => { st.requires_review = st.requires_review ? 0 : 1; renderSteps(); },
    }, ui.icon(st.requires_review ? "check_circle" : "radio_button_unchecked", "text-[15px]"), "完成后人工确认");

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
      ui.el("div", { class: "grid grid-cols-1 md:grid-cols-2 gap-3" },
        ui.el("div", {}, ui.el("label", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "绑定 Skill"), skillSel),
        ui.el("div", {}, ui.el("label", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "长度档位"), lenSel)),
      ctxBox,
      ui.el("div", {}, ui.el("label", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "固定指令"), instIn),
      ui.el("div", { class: "flex items-center gap-2" }, reviewToggle,
        ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "确认闸是安全底线：未确认的生成绝不进入下一步")));
    return card;
  }

  async function save() {
    const name = nameIn.value.trim();
    if (!name) { ui.toast("请填写工作流名称", "err"); return; }
    const payloadSteps = steps.map((s, i) => ({
      title: (s.title || `步骤 ${i + 1}`).trim(),
      skill_id: s.skill_id,
      input_mode: s.input_mode || "chapter",
      prev_step_seq: s.prev_step_seq,
      ref_step_seqs: s.ref_step_seqs || [],
      context_sources: s.context_sources || ["chapter", "triad"],
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
  let hasAutoOpenedSummary = false;

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

    if (run.status === "done") {
      if (!hasAutoOpenedSummary) {
        hasAutoOpenedSummary = true;
        setTimeout(async () => {
          try {
            const res = await api.get(`/workflows/runs/${runId}/summary-assets`);
            if (res && res.assets) {
              showAssetSyncModal(runId, 0, res.assets, null, "🎉 写作工作流全流程资产一键自动反哺看板");
            }
          } catch (e) {
            console.warn("自动提取全流程资产失败:", e);
          }
        }, 200);
      }
      const summaryBanner = ui.el("div", {
        class: "p-4 rounded-2xl bg-primary/10 border border-primary/30 flex flex-col md:flex-row items-center justify-between gap-3 mt-1",
      },
        ui.el("div", { class: "flex items-center gap-3" },
          ui.icon("verified", "text-primary text-[32px] shrink-0"),
          ui.el("div", {},
            ui.el("div", { class: "font-headline-sm text-headline-sm font-semibold text-primary" }, "🎉 写作工作流已圆满完成！"),
            ui.el("div", { class: "font-body-sm text-body-sm text-on-surface-variant mt-0.5" }, "全流程产出的故事立项、万相谱角色、关系网、分卷大纲、伏笔计划均可一键汇总导入。"))),
        ui.el("div", { class: "flex flex-wrap items-center gap-2 shrink-0" },
          ui.el("button", {
            class: "px-4 py-2 rounded-xl bg-primary text-on-primary font-label-md text-label-md font-medium shadow-md hover:opacity-90 flex items-center gap-1.5 transition-all",
            onclick: async () => {
              try {
                const res = await api.get(`/workflows/runs/${runId}/summary-assets`);
                showAssetSyncModal(runId, 0, res.assets, null, "🎉 全流程汇总资产规范同步");
              } catch (e) {
                ui.toast("获取汇总资产失败：" + e.message, "err");
              }
            },
          }, ui.icon("inventory_2", "text-[18px]"), "全功能一键同步至作品库"),
          run.work_id ? ui.el("a", {
            href: `#/entities/${run.work_id}`,
            class: "px-3 py-2 rounded-xl bg-surface-container text-on-surface font-label-sm text-label-sm hover:bg-surface-container-high flex items-center gap-1",
          }, ui.icon("group", "text-[16px]"), "查看万相谱") : null,
          run.work_id ? ui.el("a", {
            href: `#/outline/${run.work_id}`,
            class: "px-3 py-2 rounded-xl bg-surface-container text-on-surface font-label-sm text-label-sm hover:bg-surface-container-high flex items-center gap-1",
          }, ui.icon("format_list_bulleted", "text-[16px]"), "查看大纲") : null));
      headCard.append(summaryBanner);
    }

    stepsBox.innerHTML = "";
    (run.steps || []).forEach((s) => stepsBox.append(renderRunStep(run, s)));
  }



  async function showAssetSyncModal(runId, stepSeq, initialAssets, onDone, customTitle) {
    let assets = initialAssets;
    if (!assets) {
      try {
        const res = await api.get(`/workflows/runs/${runId}/steps/${stepSeq}/extracted-assets`);
        assets = res.assets || { work_info: {}, entities: [], relations: [], outline_nodes: [], foreshadows: [], notes: [] };
      } catch (e) {
        ui.toast("提取创作资产失败：" + e.message, "err");
        return;
      }
    }

    const workInfo = assets.work_info || {};
    const hasWorkInfo = !!(workInfo.title || workInfo.genre || workInfo.intro);
    const totalCount = (hasWorkInfo ? 1 : 0) +
                       (assets.entities || []).length +
                       (assets.relations || []).length +
                       (assets.outline_nodes || []).length +
                       (assets.foreshadows || []).length +
                       (assets.notes || []).length;

    const overlay = ui.el("div", {
      class: "fixed inset-0 bg-scrim/40 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-fade-in",
      onclick: (e) => { if (e.target === overlay) overlay.remove(); },
    });

    const box = ui.el("div", {
      class: "bg-surface text-on-surface rounded-2xl shadow-xl max-w-2xl w-full max-h-[88vh] flex flex-col overflow-hidden border border-outline-variant",
    });

    const header = ui.el("div", { class: "flex items-center justify-between p-4 border-b border-outline-variant bg-surface-container-low" },
      ui.el("div", { class: "flex items-center gap-2" },
        ui.icon("inventory_2", "text-primary text-[22px]"),
        ui.el("h3", { class: "font-headline-sm text-headline-sm font-semibold text-primary" }, customTitle || "规范同步至墨语资产库"),
        ui.el("span", { class: "px-2 py-0.5 rounded-full bg-primary/10 text-primary font-label-sm text-label-sm" }, `识别到 ${totalCount} 项`)),
      ui.el("button", {
        class: "p-1 rounded-lg hover:bg-surface-container text-on-surface-variant",
        onclick: () => overlay.remove(),
      }, ui.icon("close", "text-[20px]")));

    const body = ui.el("div", { class: "p-4 overflow-y-auto flex flex-col gap-4 font-body-sm text-body-sm" });

    if (totalCount === 0) {
      body.append(ui.el("div", { class: "text-center py-8 text-on-surface-variant font-label-md" }, "当前文本中未识别到明确的结构化资产（立项/人物/道具/地点/关系/大纲/伏笔/世界观）"));
    }

    // 0. 故事立项 (作品基础信息配置)
    let syncWorkInfoCb = null;
    let workTitleInput = null;
    let workGenreInput = null;
    let workIntroInput = null;
    if (hasWorkInfo || customTitle) {
      syncWorkInfoCb = ui.el("input", { type: "checkbox", checked: hasWorkInfo, class: "rounded border-outline text-primary mt-0.5" });
      workTitleInput = ui.el("input", {
        type: "text",
        class: "w-full px-2.5 py-1.5 rounded-lg bg-surface border border-outline-variant focus:border-primary text-body-sm text-on-surface outline-none",
        placeholder: "作品书名，如《逆命天尊》",
        value: workInfo.title || "",
      });
      workGenreInput = ui.el("input", {
        type: "text",
        class: "w-full px-2.5 py-1.5 rounded-lg bg-surface border border-outline-variant focus:border-primary text-body-sm text-on-surface outline-none",
        placeholder: "题材类型，如 古典仙侠 / 悬疑修真",
        value: workInfo.genre || "",
      });
      workIntroInput = ui.el("textarea", {
        class: "w-full px-2.5 py-1.5 rounded-lg bg-surface border border-outline-variant focus:border-primary text-body-sm text-on-surface outline-none min-h-[60px] resize-y",
        placeholder: "核心看点或故事简介...",
      }, workInfo.intro || "");

      const workInfoGroup = ui.el("div", { class: "flex flex-col gap-2.5 p-3 rounded-xl bg-surface-container-low border border-outline-variant/60" },
        ui.el("div", { class: "flex items-center justify-between" },
          ui.el("label", { class: "flex items-center gap-2 cursor-pointer font-label-sm text-label-sm font-semibold text-primary" },
            syncWorkInfoCb,
            ui.icon("auto_stories", "text-[16px]"),
            "故事立项 · 规范同步更新作品信息"),
          ui.el("span", { class: "text-[11px] text-on-surface-variant" }, "可编辑书名、题材与看点")),
        ui.el("div", { class: "grid grid-cols-1 sm:grid-cols-2 gap-2" },
          ui.el("div", { class: "flex flex-col gap-1" },
            ui.el("span", { class: "text-[12px] text-on-surface-variant" }, "作品书名"),
            workTitleInput),
          ui.el("div", { class: "flex flex-col gap-1" },
            ui.el("span", { class: "text-[12px] text-on-surface-variant" }, "题材定位"),
            workGenreInput)),
        ui.el("div", { class: "flex flex-col gap-1" },
          ui.el("span", { class: "text-[12px] text-on-surface-variant" }, "核心看点 / 故事简介"),
          workIntroInput));
      body.append(workInfoGroup);
    }

    // 0.5 章节登场与引用绑定选择器
    let chapterSelect = null;
    let availableChapters = [];
    try {
      const curWorkId = (assets && assets.run_meta && assets.run_meta.work_id) || (typeof run !== "undefined" && run && run.work_id);
      if (curWorkId) {
        const tree = await api.get(`/works/${curWorkId}/tree`);
        if (Array.isArray(tree)) {
          for (const v of tree) {
            for (const c of (v.chapters || [])) {
              availableChapters.push({ id: c.id, label: `${v.title} · ${c.title}` });
            }
          }
        }
      }
    } catch (_) {}

    if (availableChapters.length > 0) {
      const defaultChapId = (assets && assets.run_meta && assets.run_meta.chapter_id) || (typeof run !== "undefined" && run && run.chapter_id);
      chapterSelect = ui.el("select", {
        class: "px-2.5 py-1.5 rounded-lg bg-surface border border-outline-variant text-body-sm font-label-sm outline-none text-on-surface",
      },
        ui.el("option", { value: "" }, "（自动智能关联首章或默认章节）"),
        availableChapters.map(c => ui.el("option", { value: String(c.id), selected: c.id === defaultChapId }, `关联至本章: ${c.label}`))
      );

      const chapGroup = ui.el("div", {
        class: "flex items-center justify-between p-3 rounded-xl bg-surface-container-low border border-outline-variant/60 gap-2 flex-wrap"
      },
        ui.el("div", { class: "flex items-center gap-1.5 font-label-sm text-label-sm font-semibold text-primary" },
          ui.icon("bookmark", "text-[16px] text-secondary"),
          "章节登场与引用绑定：",
          ui.el("span", { class: "font-normal text-on-surface-variant text-[11px]" }, "本次同步的实体将自动添加至此章节登场记录")),
        chapterSelect
      );
      body.append(chapGroup);
    }

    // 1. 万相谱实体
    const entChecks = [];
    if ((assets.entities || []).length > 0) {
      const entGroup = ui.el("div", { class: "flex flex-col gap-2 p-3 rounded-xl bg-surface-container-low border border-outline-variant/60" },
        ui.el("div", { class: "flex items-center gap-1.5 font-label-sm text-label-sm font-semibold text-primary" },
          ui.icon("group", "text-[16px]"), `万相谱实体 (${assets.entities.length}个)`));
      const grid = ui.el("div", { class: "grid grid-cols-1 sm:grid-cols-2 gap-2" });
      assets.entities.forEach((ent) => {
        const cb = ui.el("input", { type: "checkbox", checked: true, class: "rounded border-outline text-primary mt-0.5" });
        entChecks.push({ cb, data: ent });
        const catMap = { character: "人物", item: "道具", location: "地点", faction: "势力", lore: "法则" };
        const label = ui.el("label", { class: "flex items-start gap-2 p-2 rounded-lg bg-surface border border-outline-variant/40 hover:border-primary/50 cursor-pointer" },
          cb,
          ui.el("div", { class: "flex flex-col min-w-0" },
            ui.el("div", { class: "flex items-center gap-1 font-label-sm text-label-sm font-medium" },
              ui.el("span", { class: "text-primary truncate font-semibold" }, ent.name),
              ui.el("span", { class: "px-1.5 py-0.2 rounded bg-surface-container-high text-on-surface-variant text-[11px] shrink-0" }, catMap[ent.category] || ent.category),
              ent.is_new !== undefined ? ui.el("span", {
                class: `px-1.5 py-0.2 rounded text-[10px] shrink-0 ${ent.is_new ? "bg-primary/10 text-primary font-semibold" : "bg-surface-container text-on-surface-variant"}`
              }, ent.is_new ? "✨ 全新收录" : "已有 · 补充") : null),
            ent.content ? ui.el("span", { class: "text-on-surface-variant text-[12px] line-clamp-2 mt-0.5" }, ent.content) : null));
        grid.append(label);
      });
      entGroup.append(grid);
      body.append(entGroup);
    }

    // 2. 万相图谱关系
    const relChecks = [];
    if ((assets.relations || []).length > 0) {
      const relGroup = ui.el("div", { class: "flex flex-col gap-2 p-3 rounded-xl bg-surface-container-low border border-outline-variant/60" },
        ui.el("div", { class: "flex items-center gap-1.5 font-label-sm text-label-sm font-semibold text-primary" },
          ui.icon("hub", "text-[16px]"), `万相图谱关系 (${assets.relations.length}条)`));
      const list = ui.el("div", { class: "flex flex-col gap-1.5" });
      assets.relations.forEach((rel) => {
        const cb = ui.el("input", { type: "checkbox", checked: true, class: "rounded border-outline text-primary mt-0.5" });
        relChecks.push({ cb, data: rel });
        const item = ui.el("label", { class: "flex items-center gap-2 p-2 rounded-lg bg-surface border border-outline-variant/40 hover:border-primary/50 cursor-pointer" },
          cb,
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface font-medium" }, rel.from_name),
          ui.icon("arrow_forward", "text-[14px] text-on-surface-variant"),
          ui.el("span", { class: "px-1.5 py-0.5 rounded bg-primary/10 text-primary font-label-sm text-label-sm font-medium" }, rel.label),
          ui.icon("arrow_forward", "text-[14px] text-on-surface-variant"),
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface font-medium" }, rel.to_name));
        list.append(item);
      });
      relGroup.append(list);
      body.append(relGroup);
    }

    // 3. 故事大纲节点
    const outlineChecks = [];
    if ((assets.outline_nodes || []).length > 0) {
      const outGroup = ui.el("div", { class: "flex flex-col gap-2 p-3 rounded-xl bg-surface-container-low border border-outline-variant/60" },
        ui.el("div", { class: "flex items-center gap-1.5 font-label-sm text-label-sm font-semibold text-primary" },
          ui.icon("format_list_bulleted", "text-[16px]"), `故事大纲 (${assets.outline_nodes.length}个节点)`));
      const list = ui.el("div", { class: "flex flex-col gap-1.5" });
      assets.outline_nodes.forEach((node) => {
        const cb = ui.el("input", { type: "checkbox", checked: true, class: "rounded border-outline text-primary mt-0.5" });
        outlineChecks.push({ cb, data: node });
        const item = ui.el("label", { class: "flex items-start gap-2 p-2 rounded-lg bg-surface border border-outline-variant/40 hover:border-primary/50 cursor-pointer" },
          cb,
          ui.el("div", { class: "flex flex-col min-w-0" },
            ui.el("div", { class: "flex items-center gap-1.5 font-label-sm text-label-sm font-medium" },
              ui.icon(node.is_volume ? "folder" : "description", "text-[14px] text-primary"),
              ui.el("span", { class: "text-on-surface font-semibold" }, node.title),
              node.is_new !== undefined ? ui.el("span", {
                class: `px-1.5 py-0.2 rounded text-[10px] shrink-0 ${node.is_new ? "bg-primary/10 text-primary font-semibold" : "bg-surface-container text-on-surface-variant"}`
              }, node.is_new ? "✨ 新节点" : "已有节点") : null),
            node.synopsis ? ui.el("span", { class: "text-on-surface-variant text-[12px] line-clamp-1 mt-0.5" }, node.synopsis) : null));
        list.append(item);
      });
      outGroup.append(list);
      body.append(outGroup);
    }

    // 3.5 剧情时间线事件 (三位一体)
    const timelineChecks = [];
    if ((assets.timeline_events || []).length > 0) {
      const teGroup = ui.el("div", { class: "flex flex-col gap-2 p-3 rounded-xl bg-surface-container-low border border-outline-variant/60" },
        ui.el("div", { class: "flex items-center gap-1.5 font-label-sm text-label-sm font-semibold text-primary" },
          ui.icon("timeline", "text-[16px] text-secondary"), `剧情时间线事件 (${assets.timeline_events.length}条)`));
      const list = ui.el("div", { class: "flex flex-col gap-1.5" });
      assets.timeline_events.forEach((ev) => {
        const cb = ui.el("input", { type: "checkbox", checked: true, class: "rounded border-outline text-primary mt-0.5" });
        timelineChecks.push({ cb, data: ev });
        const item = ui.el("label", { class: "flex items-start gap-2 p-2 rounded-lg bg-surface border border-outline-variant/40 hover:border-primary/50 cursor-pointer" },
          cb,
          ui.el("div", { class: "flex flex-col min-w-0" },
            ui.el("div", { class: "flex items-center gap-1.5 font-label-sm text-label-sm font-medium" },
              ui.icon("schedule", "text-[13px] text-secondary"),
              ui.el("span", { class: "text-secondary font-semibold" }, ev.time_label || "未定时间")),
            ui.el("span", { class: "text-on-surface text-[12px] line-clamp-2 mt-0.5" }, ev.event),
            ev.characters ? ui.el("span", { class: "text-on-surface-variant text-[11px]" }, "人物：" + ev.characters) : null));
        list.append(item);
      });
      teGroup.append(list);
      body.append(teGroup);
    }

    // 4. 伏笔计划表
    const foreshadowChecks = [];
    if ((assets.foreshadows || []).length > 0) {
      const fsGroup = ui.el("div", { class: "flex flex-col gap-2 p-3 rounded-xl bg-surface-container-low border border-outline-variant/60" },
        ui.el("div", { class: "flex items-center gap-1.5 font-label-sm text-label-sm font-semibold text-primary" },
          ui.icon("bookmark", "text-[16px]"), `伏笔计划表 (${assets.foreshadows.length}条)`));
      const list = ui.el("div", { class: "flex flex-col gap-1.5" });
      assets.foreshadows.forEach((fs) => {
        const cb = ui.el("input", { type: "checkbox", checked: true, class: "rounded border-outline text-primary mt-0.5" });
        foreshadowChecks.push({ cb, data: fs });
        const item = ui.el("label", { class: "flex items-start gap-2 p-2 rounded-lg bg-surface border border-outline-variant/40 hover:border-primary/50 cursor-pointer" },
          cb,
          ui.el("div", { class: "flex flex-col min-w-0" },
            ui.el("div", { class: "flex items-center gap-1.5 font-label-sm text-label-sm font-medium" },
              ui.icon("flag", "text-[13px] text-primary"),
              ui.el("span", { class: "text-primary font-semibold" }, fs.title),
              fs.is_new !== undefined ? ui.el("span", {
                class: `px-1.5 py-0.2 rounded text-[10px] shrink-0 ${fs.is_new ? "bg-primary/10 text-primary font-semibold" : "bg-surface-container text-on-surface-variant"}`
              }, fs.is_new ? "✨ 新伏笔" : "已有伏笔") : null),
            fs.content ? ui.el("span", { class: "text-on-surface-variant text-[12px] line-clamp-2 mt-0.5" }, fs.content) : null));
        list.append(item);
      });
      fsGroup.append(list);
      body.append(fsGroup);
    }

    // 5. 世界观与法则资料
    const noteChecks = [];
    if ((assets.notes || []).length > 0) {
      const noteGroup = ui.el("div", { class: "flex flex-col gap-2 p-3 rounded-xl bg-surface-container-low border border-outline-variant/60" },
        ui.el("div", { class: "flex items-center gap-1.5 font-label-sm text-label-sm font-semibold text-primary" },
          ui.icon("public", "text-[16px]"), `世界观与法则资料 (${assets.notes.length}条)`));
      const list = ui.el("div", { class: "flex flex-col gap-1.5" });
      assets.notes.forEach((note) => {
        const cb = ui.el("input", { type: "checkbox", checked: true, class: "rounded border-outline text-primary mt-0.5" });
        noteChecks.push({ cb, data: note });
        const item = ui.el("label", { class: "flex items-start gap-2 p-2 rounded-lg bg-surface border border-outline-variant/40 hover:border-primary/50 cursor-pointer" },
          cb,
          ui.el("div", { class: "flex flex-col min-w-0" },
            ui.el("span", { class: "font-label-sm text-label-sm font-semibold text-primary" }, note.title),
            ui.el("span", { class: "text-on-surface-variant text-[12px] line-clamp-2 whitespace-pre-wrap mt-0.5" }, note.content)));
        list.append(item);
      });
      noteGroup.append(list);
      body.append(noteGroup);
    }

    const allCheckboxes = [...entChecks, ...relChecks, ...outlineChecks, ...foreshadowChecks, ...noteChecks];

    const footer = ui.el("div", { class: "flex items-center justify-between p-4 border-t border-outline-variant bg-surface-container-low" },
      ui.el("div", { class: "flex gap-2" },
        ui.el("button", {
          class: "px-2.5 py-1 text-[13px] rounded text-on-surface-variant hover:bg-surface-container",
          onclick: () => {
            allCheckboxes.forEach(c => c.cb.checked = true);
            if (syncWorkInfoCb) syncWorkInfoCb.checked = true;
          },
        }, "全选"),
        ui.el("button", {
          class: "px-2.5 py-1 text-[13px] rounded text-on-surface-variant hover:bg-surface-container",
          onclick: () => {
            allCheckboxes.forEach(c => c.cb.checked = false);
            if (syncWorkInfoCb) syncWorkInfoCb.checked = false;
          },
        }, "反选")),
      ui.el("div", { class: "flex gap-2" },
        ui.el("button", {
          class: "px-4 py-2 rounded-lg bg-surface-container text-on-surface font-label-sm text-label-sm",
          onclick: () => overlay.remove(),
        }, "取消"),
        ui.el("button", {
          class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-sm text-label-sm font-medium hover:opacity-90 flex items-center gap-1.5 shadow-sm",
          onclick: async () => {
            const payload = {
              entities: entChecks.filter(c => c.cb.checked).map(c => c.data),
              relations: relChecks.filter(c => c.cb.checked).map(c => c.data),
              outline_nodes: outlineChecks.filter(c => c.cb.checked).map(c => c.data),
              timeline_events: timelineChecks.filter(c => c.cb.checked).map(c => c.data),
              foreshadows: foreshadowChecks.filter(c => c.cb.checked).map(c => c.data),
              notes: noteChecks.filter(c => c.cb.checked).map(c => c.data),
            };
            if (syncWorkInfoCb && syncWorkInfoCb.checked) {
              payload.work_info = {
                title: workTitleInput ? workTitleInput.value.trim() : "",
                genre: workGenreInput ? workGenreInput.value.trim() : "",
                intro: workIntroInput ? workIntroInput.value.trim() : "",
              };
            }
            if (chapterSelect && chapterSelect.value) {
              payload.chapter_id = Number(chapterSelect.value);
            }
            try {
              const res = await api.post(`/workflows/runs/${runId}/steps/${stepSeq}/sync-assets`, payload);
              const sm = res.summary || {};
              const tips = [];
              if (sm.work_info_updated) tips.push("作品立项已更新");
              if (sm.entities_added) tips.push(`万相谱实体+${sm.entities_added}`);
              if (sm.relations_added) tips.push(`关系+${sm.relations_added}`);
              if (sm.outlines_added) tips.push(`大纲+${sm.outlines_added}`);
              if (sm.timeline_events_added) tips.push(`时间线+${sm.timeline_events_added}`);
              if (sm.foreshadows_added) tips.push(`伏笔+${sm.foreshadows_added}`);
              if (sm.notes_added) tips.push(`设定+${sm.notes_added}`);
              const targetWorkId = res.work_id || (assets && assets.run_meta && assets.run_meta.work_id);
              if (window.store && targetWorkId) {
                if (window.store.plot) window.store.plot.notifyChanged(targetWorkId);
                if (window.store.events) window.store.events.emit("entity:changed", { workId: targetWorkId });
              }
              ui.toast("规范同步成功！" + (tips.join("，") || "已同步"), "ok");
              overlay.remove();
              if (onDone) await onDone();
            } catch (e) {
              ui.toast("同步失败：" + e.message, "err");
            }
          },
        }, ui.icon("check_circle", "text-[16px]"), "确认规范同步到作品库")));

    box.append(header, body, footer);
    overlay.append(box);
    document.body.append(overlay);
  }

  function parseWorkflowOptions(text) {
    if (!text || typeof text !== "string") return [];
    const lines = text.split("\n");
    const optionHeaders = [];
    // 覆盖：方案1/方向1/选项A/候选填法A/【方案一】/【方向1】等常见多方案输出
    const headerRe = /^\s*(?:[#*>\-\s]*【(?:方案|选项|方向|路线)\s*([0-9一二三四五六七八九十A-Za-z]+)】|[#*>\-\s]*(?:方案|选项|方向|路线|Option)\s*([0-9一二三四五六七八九十A-Za-z]+)[：:\s]|(?:\*{2}|#{2,4})\s*(?:方案|选项|方向|路线|Option)\s*([0-9一二三四五六七八九十A-Za-z]+).*|[-*]\s+\*\*([A-Za-z0-9一二三四五六七八九十]+)[\s\w（）()]*\*\*[：:])/;

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

    if (s.ref_step_seqs && s.ref_step_seqs.length > 0) {
      const refLabels = s.ref_step_seqs.map((idx) => `步骤 ${idx + 1}`).join("、");
      card.append(ui.el("div", { class: "flex items-center gap-1.5 font-label-sm text-label-xs text-on-surface-variant bg-surface-container-low px-2.5 py-1 rounded-md self-start border border-border-feather" },
        ui.icon("alt_route", "text-[14px] text-primary"),
        `前序上下文参考：${refLabels}`
      ));
    }

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
          ui.el("div", { class: "flex items-center gap-1.5 self-end" },
            ui.el("button", {
              class: "flex items-center gap-1 px-2.5 py-1 rounded bg-secondary-container text-on-secondary-container font-label-sm text-label-sm hover:opacity-90 transition-opacity",
              onclick: async () => {
                try {
                  const res = await api.post(`/workflows/runs/${runId}/steps/${s.step_seq}/extracted-assets`, { content: opt.content });
                  showAssetSyncModal(runId, s.step_seq, res.assets, async () => {
                    await api.post(`/workflows/runs/${runId}/steps/${s.step_seq}/review`, {
                      action: "edit",
                      content: opt.content,
                      note: `选用「${opt.title}」并同步资产`,
                    });
                    tick();
                  }, `选用「${opt.title}」· 前置配置导入`);
                } catch (e) {
                  ui.toast("提取方案资产失败：" + e.message, "err");
                }
              },
            }, ui.icon("inventory_2", "text-[14px]"), "选用并配置导入"),
            ui.el("button", {
              class: "flex items-center gap-1 px-2.5 py-1 rounded bg-primary text-on-primary font-label-sm text-label-sm hover:opacity-90 transition-opacity",
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
            }, ui.icon("check", "text-[14px]"), "选用此方案继续")));
        optGrid.append(optCard);
      });
      optContainer.append(optGrid);
      card.append(optContainer);
    }

    if (waiting && editingSeq !== s.step_seq) {
      // 资产规范同步入口栏
      card.append(ui.el("div", { class: "flex items-center justify-between p-2.5 rounded-lg bg-secondary-container/20 border border-secondary/30 mb-1" },
        ui.el("div", { class: "flex items-center gap-2 font-label-sm text-label-sm text-on-surface" },
          ui.icon("account_tree", "text-primary text-[18px]"),
          ui.el("span", { class: "font-semibold text-primary" }, "资产联动："),
          ui.el("span", { class: "text-on-surface-variant" }, "将本步骤生成的世界观、人物、道具、大纲等规范导入到各功能模块")),
        ui.el("button", {
          class: "flex items-center gap-1 px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-sm text-label-sm hover:opacity-90 transition-opacity",
          onclick: () => showAssetSyncModal(runId, s.step_seq, null, null),
        }, ui.icon("inventory_2", "text-[16px]"), "规范同步至作品库")));
      card.append(ui.el("div", { class: "flex flex-wrap gap-2" },
        ui.el("button", {
          class: "flex items-center gap-1 px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-sm text-label-sm hover:opacity-90 shadow-sm",
          onclick: () => {
            showAssetSyncModal(runId, s.step_seq, null, async () => {
              await api.post(`/workflows/runs/${runId}/steps/${s.step_seq}/review`, { action: "approve" });
              tick();
            }, "步骤产出 · 前置配置与规范导入");
          },
        }, ui.icon("inventory_2", "text-[16px]"), "采纳并配置导入 (推荐)"),
        ui.el("button", {
          class: "px-3 py-1.5 rounded-lg bg-surface-container text-on-surface font-label-sm text-label-sm hover:bg-surface-container-high",
          onclick: async () => {
            try { await api.post(`/workflows/runs/${runId}/steps/${s.step_seq}/review`, { action: "approve" }); tick(); }
            catch (e) { ui.toast(e.message, "err"); }
          },
        }, "仅采纳继续"),
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
