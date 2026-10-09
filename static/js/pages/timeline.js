/* 剧情时间线页：纵向时间轴 + 事件 CRUD + AI 从章节提取（预览后入库） */
registerPage("timeline", async (view, { segs }) => {
  const workId = Number(segs[0]) || null;
  if (!workId) return timelinePickWork(view);

  let work, works, events, tree, outlineTree = [];
  try {
    [work, works, tree, outlineTree] = await Promise.all([
      api.get(`/works/${workId}`),
      api.get("/works"),
      api.get(`/works/${workId}/tree`),
      api.get(`/works/${workId}/outline`).catch(() => []),
    ]);
    events = await api.get(`/works/${workId}/timeline`);
  } catch (e) { ui.toast(e.message, "err"); return; }

  const chapters = tree.flatMap((v) => v.chapters.map((c) => ({ ...c, volume_title: v.title })));
  const outlineNodes = [];
  (function flattenOutline(nodes) {
    if (!Array.isArray(nodes)) return;
    for (const n of nodes) {
      outlineNodes.push({ id: n.id, title: n.title });
      if (n.children) flattenOutline(n.children);
    }
  })(outlineTree);
  const chapterName = (id) => {
    const c = chapters.find((x) => x.id === id);
    return c ? `${c.volume_title} · ${c.title}` : null;
  };

  ui.setCrumb("剧情时间线", work.title);
  ui.setActions(
    ui.el("button", {
      class: "flex items-center gap-1 px-space-sm py-1.5 rounded-full bg-surface-container hover:bg-surface-container-high text-on-surface transition-all",
      onclick: () => extractFlow(),
    }, ui.icon("auto_awesome", "text-[18px]"), ui.el("span", { class: "font-label-md text-label-md" }, "AI 从章节提取")),
    ui.el("button", {
      class: "flex items-center gap-1 px-space-sm py-1.5 rounded-full bg-primary text-on-primary shadow-[0_2px_12px_rgba(6,21,35,0.2)] hover:bg-primary-container transition-all",
      onclick: () => editEvent(null),
    }, ui.icon("add", "text-[18px]"), ui.el("span", { class: "font-label-md text-label-md" }, "手动添加事件")),
  );

  let onlyUnbound = false;
  const selectedEventIds = new Set();

  const workSelect = ui.el("select", {
    class: "px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-md text-body-md min-w-[200px]",
    onchange: () => { if (Number(workSelect.value) !== workId) location.hash = `#/timeline/${workSelect.value}`; },
  });
  for (const w of works) workSelect.append(ui.el("option", { value: w.id, selected: w.id === workId ? "" : null }, w.title));

  const unboundFilter = ui.el("label", {
    class: "flex items-center gap-1.5 font-label-sm text-label-sm text-on-surface-variant z-10 cursor-pointer select-none ml-2",
  },
    ui.el("input", {
      type: "checkbox",
      class: "rounded border-outline text-primary",
      onchange: (e) => {
        onlyUnbound = e.target.checked;
        selectedEventIds.clear();
        render();
      },
    }),
    "仅看未归属");

  const timelineBox = ui.el("div", { class: "flex flex-col" });

  view.append(
    ui.el("div", { class: "flex flex-col gap-space-lg" },
      ui.el("div", { class: "relative overflow-hidden rounded-xl bg-surface-container-lowest shadow-[0_4px_20px_rgba(6,21,35,0.03)] p-space-lg flex flex-col gap-space-xs" },
        ui.el("div", { class: "absolute -right-12 -top-12 w-64 h-64 rounded-full bg-secondary-fixed/30 blur-3xl pointer-events-none" }),
        ui.el("div", { class: "flex items-center gap-space-xs z-10" },
          ui.el("span", { class: "inline-flex items-center justify-center w-6 h-6 rounded-full bg-secondary text-on-secondary shadow-sm" },
            ui.icon("timeline", "text-[15px]")),
          ui.el("span", { class: "font-label-sm text-label-sm text-secondary tracking-widest uppercase" }, "STORY TIMELINE"),
          ui.el("span", { class: "text-outline-variant font-body-sm text-body-sm" }, "•"),
          ui.el("span", { class: "font-body-sm text-body-sm text-on-surface-variant" }, "剧情脉络梳理")),
        ui.el("h1", { class: "font-headline-lg text-headline-lg text-primary tracking-tight z-10" }, "剧情时间线"),
        ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant z-10" },
          "按故事内时间排列关键剧情事件，可手动记录，也可让 AI 从章节正文中提取。"),
        ui.el("div", { class: "flex items-center gap-4 flex-wrap z-10 mt-1" },
          ui.el("label", { class: "flex items-center gap-2 font-label-sm text-label-sm text-on-surface-variant" }, "当前作品", workSelect),
          unboundFilter)),
      timelineBox));

  if (window.store && window.store.events) {
    window.store.events.onPage("timeline", "plot:changed", (ev) => {
      if (ev && ev.workId === workId) reload();
    });
  }

  async function reload() {
    try { events = await api.get(`/works/${workId}/timeline`); }
    catch (e) { ui.toast(e.message, "err"); return; }
    render();
  }

  /* ---------- 时间轴渲染 ---------- */

  function render() {
    timelineBox.innerHTML = "";
    const displayEvents = onlyUnbound
      ? events.filter((e) => e.chapter_id == null && e.outline_node_id == null)
      : events;

    if (onlyUnbound) {
      const rebindBar = ui.el("div", {
        class: "mb-4 p-3 rounded-xl bg-surface-container-low border border-outline-variant/60 flex items-center justify-between flex-wrap gap-2 shadow-xs",
      });
      const targetChapSelect = ui.el("select", {
        class: "px-2.5 py-1.5 rounded-lg bg-surface border border-outline-variant font-label-sm text-label-sm text-on-surface outline-none",
      }, ui.el("option", { value: "" }, "（选择目标章节）"));
      for (const c of chapters) {
        targetChapSelect.append(ui.el("option", { value: String(c.id) }, `${c.volume_title} · ${c.title}`));
      }

      const targetNodeSelect = ui.el("select", {
        class: "px-2.5 py-1.5 rounded-lg bg-surface border border-outline-variant font-label-sm text-label-sm text-on-surface outline-none",
      }, ui.el("option", { value: "" }, "（选择目标大纲节点）"));
      for (const n of outlineNodes) {
        targetNodeSelect.append(ui.el("option", { value: String(n.id) }, n.title));
      }

      const countBadge = ui.el("span", { class: "font-label-sm text-label-sm text-primary font-semibold" }, `已选 ${selectedEventIds.size} 项`);
      const rebindBtn = ui.el("button", {
        class: "px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-sm text-label-sm font-medium hover:opacity-90 flex items-center gap-1 transition-opacity",
        onclick: async () => {
          if (!selectedEventIds.size) {
            ui.toast("请勾选需要重绑的时间线事件", "warn");
            return;
          }
          const chVal = targetChapSelect.value ? Number(targetChapSelect.value) : null;
          const nodeVal = targetNodeSelect.value ? Number(targetNodeSelect.value) : null;
          if (!chVal && !nodeVal) {
            ui.toast("请选择目标章节或大纲节点", "warn");
            return;
          }
          try {
            await api.post(`/works/${workId}/unbound-assets/rebind`, {
              timeline_event_ids: Array.from(selectedEventIds),
              chapter_id: chVal,
              outline_node_id: nodeVal,
            });
            ui.toast("重绑成功", "ok");
            selectedEventIds.clear();
            await reload();
          } catch (err) {
            ui.toast(err.message, "err");
          }
        },
      }, ui.icon("link", "text-[16px]"), "重绑到…");

      rebindBar.append(
        ui.el("div", { class: "flex items-center gap-2" },
          ui.icon("filter_list", "text-[18px] text-secondary"),
          ui.el("span", { class: "font-label-sm text-label-sm font-medium text-on-surface" }, `未归属事件 (${displayEvents.length})`),
          countBadge),
        ui.el("div", { class: "flex items-center gap-2 flex-wrap" },
          targetChapSelect,
          targetNodeSelect,
          rebindBtn));
      timelineBox.append(rebindBar);
    }

    if (!displayEvents.length) {
      timelineBox.append(ui.el("div", { class: "rounded-xl bg-surface-container-lowest shadow-[0_4px_20px_rgba(6,21,35,0.03)] p-space-xl flex flex-col items-center gap-space-md text-center" },
        ui.icon("timeline", "text-[48px] text-outline-variant"),
        ui.el("p", { class: "font-headline-sm text-headline-sm text-primary" }, onlyUnbound ? "当前没有未归属事件" : "还没有任何剧情事件"),
        ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant" },
          onlyUnbound ? "所有时间线事件均已绑定所属章节或大纲节点。" : "手动记录故事里的关键节点，或让 AI 从已写章节中自动提取。"),
        !onlyUnbound ? ui.el("div", { class: "flex items-center gap-space-sm" },
          ui.el("button", {
            class: "flex items-center gap-1 px-space-md py-2 rounded-xl bg-primary text-on-primary font-label-md text-label-md",
            onclick: () => editEvent(null),
          }, ui.icon("add", "text-[18px]"), "手动添加事件"),
          ui.el("button", {
            class: "flex items-center gap-1 px-space-md py-2 rounded-xl bg-surface-container hover:bg-surface-container-high font-label-md text-label-md",
            onclick: () => extractFlow(),
          }, ui.icon("auto_awesome", "text-[18px]"), "AI 从章节提取")) : null));
      return;
    }
    displayEvents.forEach((ev, i) => timelineBox.append(timelineRow(ev, i === displayEvents.length - 1)));
  }

  function timelineRow(ev, isLast) {
    const chars = (ev.characters || "").split(/[、,，\s]+/).map((s) => s.trim()).filter(Boolean);
    const chTitle = ev.chapter_id ? (ev.chapter_title || chapterName(ev.chapter_id)) : null;
    const isUnbound = !chTitle && ev.outline_node_id == null;

    const rowCb = onlyUnbound ? ui.el("input", {
      type: "checkbox",
      checked: selectedEventIds.has(ev.id),
      class: "rounded border-outline text-primary mr-2 cursor-pointer",
      onchange: (e) => {
        if (e.target.checked) selectedEventIds.add(ev.id);
        else selectedEventIds.delete(ev.id);
        render();
      },
    }) : null;

    return ui.el("div", { class: "flex gap-space-md items-stretch" },
      /* 左侧：节点 + 竖线 */
      ui.el("div", { class: "flex flex-col items-center w-6 shrink-0 pt-5" },
        ui.el("span", { class: "w-3 h-3 rounded-full bg-secondary ring-4 ring-secondary-fixed/60 shrink-0" }),
        !isLast && ui.el("span", { class: "w-px flex-1 bg-outline-variant/50 mt-1" })),
      /* 右侧：事件卡 */
      ui.el("div", { class: "flex-1 min-w-0 pb-space-md" },
        ui.el("div", { class: "rounded-xl bg-surface-container-lowest shadow-[0_4px_20px_rgba(6,21,35,0.03)] p-space-md flex flex-col gap-space-xs hover:shadow-[0_8px_28px_rgba(6,21,35,0.08)] transition-shadow" },
          ui.el("div", { class: "flex items-center gap-2 flex-wrap" },
            rowCb,
            ui.el("span", { class: "px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed font-label-sm text-label-sm font-semibold" },
              ev.time_label || "时间未定"),
            isUnbound ? ui.el("span", {
              class: "inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-tertiary-fixed text-on-tertiary-fixed font-label-sm text-label-sm",
            }, ui.icon("link_off", "text-[12px]"), "未归属") : null,
            ev.created_at && ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" },
              "记录于 " + String(ev.created_at).slice(0, 16)),
            ui.el("span", { class: "ml-auto flex items-center gap-1" },
              ui.el("button", {
                class: "p-1.5 rounded-lg text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors",
                title: "编辑", onclick: () => editEvent(ev),
              }, ui.icon("edit", "text-[16px]")),
              ui.el("button", {
                class: "p-1.5 rounded-lg text-on-surface-variant hover:bg-error-container hover:text-error transition-colors",
                title: "删除", onclick: () => removeEvent(ev),
              }, ui.icon("delete", "text-[16px]")))),
          ui.el("p", { class: "font-body-md text-body-md text-on-surface whitespace-pre-wrap" }, ev.event),
          (chars.length || chTitle || ev.outline_node_id) && ui.el("div", { class: "flex items-center gap-1.5 flex-wrap pt-0.5" },
            chars.map((c) => ui.el("span", {
              class: "inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant font-label-sm text-label-sm",
            }, ui.icon("person", "text-[13px]"), c)),
            chTitle && ui.el("a", {
              class: "inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary-fixed text-on-primary-fixed font-label-sm text-label-sm hover:bg-primary-container hover:text-on-primary transition-colors cursor-pointer",
              onclick: () => { location.hash = `#/workbench/${workId}?chapter=${ev.chapter_id}`; },
            }, ui.icon("menu_book", "text-[13px]"), chTitle),
            ev.outline_node_id && ui.el("a", {
              class: "inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed font-label-sm text-label-sm hover:bg-secondary hover:text-on-secondary transition-colors cursor-pointer",
              title: "点击跳转至关联的大纲节点",
              onclick: () => { location.hash = `#/outline/${workId}?node_id=${ev.outline_node_id}`; },
            }, ui.icon("account_tree", "text-[13px]"), ev.outline_node_title || ("大纲 #" + ev.outline_node_id))))));
  }

  /* ---------- 事件表单弹窗（新建 / 编辑） ---------- */

  function eventFormModal(title, initial) {
    return new Promise((resolve) => {
      const inputCls = "w-full px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-md text-body-md";
      const labelCls = "flex flex-col gap-1 font-label-sm text-label-sm text-on-surface-variant";
      const timeInput = ui.el("input", { class: inputCls, placeholder: "如：开宗第三年·春", value: initial.time_label || "" });
      const eventInput = ui.el("textarea", { class: inputCls + " resize-y min-h-[96px]", placeholder: "发生了什么？谁做了什么，结果如何？" }, initial.event || "");
      const charsInput = ui.el("input", { class: inputCls, placeholder: "涉及人物，用顿号分隔（可留空）", value: initial.characters || "" });
      const chSelect = ui.el("select", { class: inputCls },
        ui.el("option", { value: "" }, "（不关联章节）"));
      for (const c of chapters) {
        chSelect.append(ui.el("option", {
          value: c.id, selected: initial.chapter_id === c.id ? "" : null,
        }, `${c.volume_title} · ${c.title}`));
      }
      const outlineSelect = ui.el("select", { class: inputCls },
        ui.el("option", { value: "" }, "（不关联大纲节点）"));
      for (const n of outlineNodes) {
        outlineSelect.append(ui.el("option", {
          value: String(n.id), selected: initial.outline_node_id === n.id ? "" : null,
        }, n.title));
      }
      const close = (val) => { overlay.remove(); resolve(val); };
      const overlay = ui.el("div", {
        class: "fixed inset-0 z-[90] bg-ink-black/40 backdrop-blur-sm flex items-center justify-center",
        onclick: (e) => { if (e.target === overlay) close(null); },
      },
        ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-lg w-[480px] max-w-[calc(100vw-2rem)] mx-2 sm:mx-0 shadow-[0_12px_32px_rgba(27,42,56,0.12)] flex flex-col gap-space-md" },
          ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, title),
          ui.el("label", { class: labelCls }, "时间标签（故事内时间）", timeInput),
          ui.el("label", { class: labelCls }, "事件描述", eventInput),
          ui.el("label", { class: labelCls }, "涉及人物", charsInput),
          ui.el("label", { class: labelCls }, "关联章节", chSelect),
          ui.el("label", { class: labelCls }, "关联大纲节点", outlineSelect),
          ui.el("div", { class: "flex justify-end gap-2" },
            ui.el("button", {
              class: "px-4 py-2 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md",
              onclick: () => close(null),
            }, "取消"),
            ui.el("button", {
              class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md",
              onclick: () => {
                if (!eventInput.value.trim()) { ui.toast("事件描述不能为空", "err"); return; }
                close({
                  time_label: timeInput.value.trim(),
                  event: eventInput.value.trim(),
                  characters: charsInput.value.trim(),
                  chapter_id: chSelect.value ? Number(chSelect.value) : null,
                  outline_node_id: outlineSelect.value ? Number(outlineSelect.value) : null,
                });
              },
            }, "保存"))));
      document.getElementById("modal-root").append(overlay);
      timeInput.focus();
    });
  }

  async function editEvent(ev) {
    const data = await eventFormModal(ev ? "编辑事件" : "手动添加事件", ev || {});
    if (!data) return;
    try {
      if (ev) {
        await api.patch(`/timeline/${ev.id}`, data);
        ui.toast("事件已更新", "ok");
      } else {
        await api.post(`/works/${workId}/timeline`, data);
        ui.toast("事件已添加", "ok");
      }
      reload();
    } catch (e) { ui.toast(e.message, "err"); }
  }

  async function removeEvent(ev) {
    const ok = await ui.confirm("删除事件",
      `将删除这条事件记录：\n「${(ev.event || "").slice(0, 60)}」\n该操作不可恢复。`, "删除", true);
    if (!ok) return;
    try {
      await api.del(`/timeline/${ev.id}`);
      ui.toast("已删除", "ok");
      reload();
    } catch (e) { ui.toast(e.message, "err"); }
  }

  /* ---------- AI 提取流程：选章节 → 预览 → 确认入库 ---------- */

  function aiGuide(msg) {
    ui.confirm("尚未配置 AI", msg + "\n\n是否现在前往系统设置？", "前往设置").then((ok) => {
      if (ok) location.hash = "#/settings";
    });
  }

  function extractFlow() {
    if (!chapters.length) { ui.toast("该作品还没有章节，无法提取", "err"); return; }
    const inputCls = "px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-sm text-body-sm";
    const body = ui.el("div", { class: "flex flex-col gap-space-md min-h-[120px]" });
    const footer = ui.el("div", { class: "flex justify-end items-center gap-2" });
    const statusLine = ui.el("span", { class: "mr-auto font-label-sm text-label-sm text-on-surface-variant" });
    const overlay = ui.el("div", {
      class: "fixed inset-0 z-[90] bg-ink-black/40 backdrop-blur-sm flex items-center justify-center",
      onclick: (e) => { if (e.target === overlay) overlay.remove(); },
    },
      ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-lg w-[560px] max-w-[calc(100vw-2rem)] mx-2 sm:mx-0 max-h-[86vh] overflow-y-auto shadow-[0_12px_32px_rgba(27,42,56,0.12)] flex flex-col gap-space-md" },
        ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, "AI 从章节提取事件"),
        body, footer));
    document.getElementById("modal-root").append(overlay);

    /* 第一步：勾选章节 */
    const chapterBox = ui.el("div", { class: "flex flex-col gap-1 max-h-72 overflow-y-auto pr-1" });
    for (const ch of chapters) {
      const cb = ui.el("input", { type: "checkbox", class: "accent-secondary shrink-0", value: ch.id, checked: "" });
      chapterBox.append(ui.el("label", {
        class: "flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-surface-container-low cursor-pointer font-body-sm text-body-sm text-on-surface",
      }, cb, ui.el("span", { class: "truncate" }, `${ch.volume_title} · ${ch.title}`),
        ui.el("span", { class: "ml-auto font-label-sm text-label-sm text-on-surface-variant shrink-0" }, ui.fmtWords(ch.word_count) + " 字")));
    }
    const extractBtn = ui.el("button", {
      class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md disabled:opacity-50",
      onclick: runExtract,
    }, "开始提取");
    body.append(
      ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant" }, "选择要分析的章节（每章取前 3000 字），AI 会提取关键剧情事件供你确认后再入库。"),
      chapterBox);
    footer.append(statusLine,
      ui.el("button", {
        class: "px-4 py-2 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md",
        onclick: () => overlay.remove(),
      }, "取消"),
      extractBtn);

    let preview = [];

    async function runExtract() {
      const ids = [...chapterBox.querySelectorAll("input:checked")].map((c) => Number(c.value));
      if (!ids.length) { ui.toast("请至少勾选一个章节", "err"); return; }
      extractBtn.disabled = true;
      statusLine.textContent = `正在分析 ${ids.length} 个章节…`;
      try {
        const data = await api.post("/timeline/extract", { work_id: workId, chapter_ids: ids });
        preview = data.events || [];
        renderPreview(data.usage);
      } catch (e) {
        statusLine.textContent = "";
        if (e.message && e.message.includes("尚未配置")) { overlay.remove(); aiGuide(e.message); }
        else ui.toast(e.message, "err");
      } finally {
        extractBtn.disabled = false;
      }
    }

    /* 第二步：预览（可勾选、可编辑） */
    function renderPreview(usage) {
      body.innerHTML = "";
      footer.innerHTML = "";
      if (!preview.length) {
        body.append(ui.el("div", { class: "flex flex-col items-center gap-space-sm py-space-lg text-center" },
          ui.icon("task_alt", "text-[40px] text-secondary"),
          ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" }, "AI 没有从所选章节中提取到事件")));
        footer.append(ui.el("button", {
          class: "px-4 py-2 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md",
          onclick: () => overlay.remove(),
        }, "关闭"));
        return;
      }
      const rows = preview.map((ev) => {
        const cb = ui.el("input", { type: "checkbox", class: "accent-secondary shrink-0 mt-1", checked: "" });
        const ta = ui.el("textarea", {
          class: "w-full px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-sm text-body-sm resize-y min-h-[56px]",
        }, ev.event);
        const timeIn = ui.el("input", { class: inputCls + " w-40 shrink-0", value: ev.time_label || "", placeholder: "时间标签" });
        const charsIn = ui.el("input", { class: inputCls + " flex-1 min-w-0", value: ev.characters || "", placeholder: "涉及人物" });
        ev._row = { cb, ta, timeIn, charsIn };
        return ui.el("div", { class: "flex items-start gap-2 rounded-xl bg-surface-container-low/60 p-space-sm" },
          cb,
          ui.el("div", { class: "flex-1 min-w-0 flex flex-col gap-1.5" },
            ui.el("div", { class: "flex items-center gap-2 flex-wrap" }, timeIn, charsIn,
              ev.chapter_id && ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" },
                "· " + (chapterName(ev.chapter_id) || ""))),
            ta));
      });
      body.append(
        ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant" },
          `AI 提取到 ${preview.length} 条候选事件，请勾选需要入库的条目（可直接修改文本）。`),
        ui.el("div", { class: "flex flex-col gap-space-sm max-h-[46vh] overflow-y-auto pr-1" }, rows));
      const importBtn = ui.el("button", {
        class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md disabled:opacity-50",
        onclick: runImport,
      }, "确认入库");
      footer.append(
        statusLine,
        ui.el("button", {
          class: "px-4 py-2 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md",
          onclick: () => overlay.remove(),
        }, "取消"),
        importBtn);
      statusLine.textContent = usage && usage.total_tokens
        ? `消耗约 ${Number(usage.total_tokens).toLocaleString()} tokens` : "";
    }

    /* 第三步：入库 */
    async function runImport() {
      const picked = preview
        .filter((ev) => ev._row.cb.checked)
        .map((ev) => ({
          time_label: ev._row.timeIn.value.trim(),
          event: ev._row.ta.value.trim(),
          characters: ev._row.charsIn.value.trim(),
          chapter_id: ev.chapter_id || null,
        }))
        .filter((ev) => ev.event);
      if (!picked.length) { ui.toast("请至少勾选一条事件", "err"); return; }
      try {
        const saved = await api.post("/timeline/import", { work_id: workId, events: picked });
        ui.toast(`已入库 ${saved.length} 条事件`, "ok");
        overlay.remove();
        reload();
      } catch (e) { ui.toast(e.message, "err"); }
    }
  }

  render();
});

/* 无 workId 时：作品选择列表 */
async function timelinePickWork(view) {
  ui.setCrumb("剧情时间线");
  let works = [];
  try { works = await api.get("/works"); } catch (e) { ui.toast(e.message, "err"); }
  const list = ui.el("div", { class: "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-space-md" });
  view.append(
    ui.el("div", { class: "flex flex-col gap-space-lg" },
      ui.el("div", { class: "flex flex-col gap-1" },
        ui.el("span", { class: "font-label-sm text-label-sm text-secondary tracking-widest uppercase" }, "STORY TIMELINE · 剧情时间线"),
        ui.el("h1", { class: "font-display text-display text-primary tracking-tight" }, "选择一部作品"),
        ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" }, "选择要查看或梳理剧情时间线的作品。")),
      list));
  if (!works.length) {
    list.append(ui.el("div", { class: "col-span-full flex flex-col items-center gap-space-md py-space-xl text-center" },
      ui.icon("timeline", "text-[48px] text-outline-variant"),
      ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" }, "书架还是空的，先去创建一部作品吧"),
      ui.el("button", {
        class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md",
        onclick: () => { location.hash = "#/bookshelf"; },
      }, "前往书架")));
    return;
  }
  for (const w of works) {
    list.append(ui.el("div", {
      class: "bg-surface-container-lowest rounded-xl p-space-md shadow-[0_4px_20px_rgba(6,21,35,0.03)] flex items-center gap-space-sm cursor-pointer hover:shadow-[0_8px_28px_rgba(6,21,35,0.08)] transition-shadow",
      onclick: () => { location.hash = `#/timeline/${w.id}`; },
    },
      ui.el("div", {
        class: "w-12 h-16 rounded-lg shrink-0 flex items-center justify-center text-on-primary font-headline-sm text-headline-sm font-bold",
        style: `background:linear-gradient(135deg, ${w.cover_color}, #1B2A38)`,
      }, (w.title || "书")[0]),
      ui.el("div", { class: "flex flex-col min-w-0" },
        ui.el("span", { class: "font-headline-sm text-headline-sm text-primary font-semibold truncate" }, w.title),
        ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" },
          `${w.genre || "未分类"} · ${ui.fmtWords(w.total_words)} 字`))));
  }
}
