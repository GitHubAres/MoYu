/* 伏笔看板页（对应设计稿 _6）：已埋设 / 待回收 / 已回收 三栏 */
registerPage("board", async (view, { segs }) => {
  const workId = segs[0] ? Number(segs[0]) : null;

  const LANES = [
    { key: "planted", title: "已埋设 · 未回收", dot: "bg-secondary", tagCls: "bg-primary-fixed text-on-primary-fixed" },
    { key: "pending", title: "待回收 · 临界", dot: "bg-cinnabar-accent", tagCls: "bg-error-container text-on-error-container" },
    { key: "resolved", title: "已回收 · 已闭环", dot: "bg-outline", tagCls: "bg-surface-container-high text-on-surface-variant" },
  ];
  const NEXT = { planted: ["pending", "arrow_forward", "标记为待回收"], pending: ["resolved", "task_alt", "标记为已回收"], resolved: ["planted", "undo", "重新打开"] };

  if (!workId) return pickWork();
  if (window.store && window.store.events) {
    window.store.events.onPage('board', 'plot:changed', (ev) => {
      if (!ev || !ev.workId || ev.workId === workId) {
        router.dispatch();
      }
    });
  }
  return renderBoard();

  async function pickWork() {
    ui.setCrumb("伏笔看板");
    const works = await api.get("/works");
    view.append(
      ui.el("div", { class: "flex flex-col gap-1 mb-space-lg" },
        ui.el("span", { class: "font-label-sm text-label-sm text-secondary tracking-widest uppercase" }, "PLOT BOARD"),
        ui.el("h1", { class: "font-display text-display text-primary tracking-tight" }, "伏笔看板"),
        ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" }, "选择一部作品，追踪伏笔的埋设与回收。")),
      works.length
        ? ui.el("div", { class: "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-space-md" },
            works.map((w) => ui.el("button", {
              class: "text-left bg-surface-container-lowest rounded-xl p-space-md shadow-[0_4px_20px_rgba(6,21,35,0.03)] hover:shadow-[0_8px_28px_rgba(6,21,35,0.08)] transition-shadow flex flex-col gap-1",
              onclick: () => { location.hash = `#/board/${w.id}`; },
            },
              ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold truncate" }, w.title),
              ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" },
                `${w.genre || "未分类"} · ${ui.fmtWords(w.total_words)} 字`))))
        : emptyState("auto_stories", "书架还是空的，先去创建一部作品吧"));
  }

  async function renderBoard() {
    let outlineTree = [];
    const [work, items, tree, outlineTreeRes] = await Promise.all([
      api.get(`/works/${workId}`),
      api.get(`/works/${workId}/foreshadows`),
      api.get(`/works/${workId}/tree`),
      api.get(`/works/${workId}/outline`).catch(() => []),
    ]);
    outlineTree = Array.isArray(outlineTreeRes) ? outlineTreeRes : [];
    const chapters = [];
    for (const v of tree) for (const c of v.chapters) chapters.push({ id: c.id, title: `${v.title} · ${c.title}` });
    const outlineNodes = [];
    (function flattenOutline(nodes) {
      if (!Array.isArray(nodes)) return;
      for (const n of nodes) {
        outlineNodes.push({ id: n.id, title: n.title });
        if (n.children) flattenOutline(n.children);
      }
    })(outlineTree);

    ui.setCrumb("伏笔看板", `《${work.title}》`);
    ui.setActions(
      ui.el("button", {
        class: "flex items-center gap-1 px-space-sm py-1.5 rounded-full bg-primary text-on-primary shadow-[0_2px_12px_rgba(6,21,35,0.2)] hover:bg-primary-container transition-all",
        onclick: () => editDialog(null),
      }, ui.icon("add", "text-[18px]"), ui.el("span", { class: "font-label-md text-label-md" }, "新建伏笔")));

    const total = items.length;
    const resolved = items.filter((f) => f.status === "resolved").length;
    const rate = total ? Math.round((resolved / total) * 100) : 0;

    view.append(
      ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-md shadow-[0_2px_12px_rgba(6,21,35,0.03)] flex flex-wrap items-center gap-space-md mb-space-lg" },
        ui.el("div", { class: "flex items-center gap-space-xs" },
          ui.el("span", { class: "inline-flex items-center justify-center w-8 h-8 rounded-lg bg-surface-container text-primary" },
            ui.icon("view_kanban", "text-[20px]")),
          ui.el("div", { class: "flex flex-col" },
            ui.el("span", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, `《${work.title}》`),
            ui.el("span", { class: "font-label-sm text-label-sm text-outline" }, "全景脉络 · 伏笔追踪看板"))),
        ui.el("div", { class: "h-8 w-[1px] bg-surface-container-highest hidden sm:block" }),
        ui.el("div", { class: "flex items-center gap-2 font-body-sm text-body-sm" },
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "伏笔闭环率"),
          ui.el("div", { class: "w-40 h-2 rounded-full bg-surface-container overflow-hidden" },
            ui.el("div", { class: "h-full bg-secondary rounded-full transition-all", style: `width:${rate}%` })),
          ui.el("span", { class: "font-headline-sm text-headline-sm text-primary font-bold" }, `${rate}%`),
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, `（已回收 ${resolved} / 共 ${total} 条）`),
        ui.el("div", { class: "h-8 w-[1px] bg-surface-container-highest hidden sm:block" }),
        ui.el("label", { class: "flex items-center gap-1.5 font-label-sm text-label-sm text-on-surface-variant cursor-pointer select-none ml-auto" },
          ui.el("input", {
            type: "checkbox",
            class: "rounded border-outline text-primary",
            onchange: (e) => {
              onlyUnbound = e.target.checked;
              renderLanes();
            },
          }),
          "仅看未归属"))));

    let onlyUnbound = false;

    if (!total) {
      view.append(ui.el("div", { class: "flex flex-col items-center gap-space-md py-space-xl text-center" },
        ui.icon("view_kanban", "text-[48px] text-outline-variant"),
        ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" }, "还没有伏笔记录。埋下的每一条暗线，都值得被记住与回收。"),
        ui.el("button", {
          class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md",
          onclick: () => editDialog(null),
        }, "新建第一条伏笔")));
      return;
    }

    const lanes = ui.el("div", { class: "grid grid-cols-1 lg:grid-cols-3 gap-space-lg items-start" });
    let dragCard = null;   // 拖拽中的伏笔卡片数据
    const LANE_HL = ["ring-2", "ring-secondary", "bg-secondary-fixed/50"];

    function renderLanes() {
      lanes.innerHTML = "";
      const displayItems = onlyUnbound
        ? items.filter((f) => f.chapter_id == null && f.outline_node_id == null)
        : items;
      for (const lane of LANES) {
        const list = displayItems.filter((f) => f.status === lane.key);
      const sec = ui.el("section", { class: "flex flex-col gap-space-md rounded-2xl bg-surface-container-low/60 p-space-md transition-shadow" },
        ui.el("div", { class: "flex items-center justify-between px-space-xs" },
          ui.el("div", { class: "flex items-center gap-space-xs" },
            ui.el("span", { class: `w-2.5 h-2.5 rounded-full ${lane.dot}` }),
            ui.el("h2", { class: "font-headline-sm text-headline-sm text-primary tracking-tight font-semibold" }, lane.title),
            ui.el("span", { class: "px-2 py-0.5 rounded-full bg-surface-container-high text-on-surface font-label-sm text-label-sm" }, `${list.length} 条`))),
        list.length
          ? ui.el("div", { class: "flex flex-col gap-space-md" }, list.map((f) => card(f, lane)))
          : ui.el("div", { class: "border border-dashed border-outline-variant/40 rounded-xl p-space-md text-center font-label-sm text-label-sm text-outline" }, "暂无记录"));
      /* 栏目作为投放目标：整栏可 drop，dragover 时高亮 */
      sec.addEventListener("dragover", (e) => {
        if (!dragCard || dragCard.status === lane.key) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        sec.classList.add(...LANE_HL);
      });
      sec.addEventListener("dragleave", (e) => {
        if (!sec.contains(e.relatedTarget)) sec.classList.remove(...LANE_HL);
      });
      sec.addEventListener("drop", async (e) => {
        e.preventDefault();
        sec.classList.remove(...LANE_HL);
        const f = dragCard;
        if (!f || f.status === lane.key) return;
        try {
          await api.patch(`/foreshadows/${f.id}`, { status: lane.key });
          ui.toast(`已移至「${lane.title.split(" ")[0]}」`, "ok");
          router.dispatch();
        } catch (err) { ui.toast("移动失败：" + err.message, "err"); }
      });
        lanes.append(sec);
      }
    }
    renderLanes();
    view.append(lanes);

    function card(f, lane) {
      const [nextStatus, nextIcon, nextTip] = NEXT[f.status];
      const actionCls = "p-2 min-w-[36px] min-h-[36px] flex items-center justify-center rounded-lg bg-surface-container-low text-on-surface-variant transition-colors cursor-pointer";
      const el = ui.el("article", {
        class: "flex flex-col bg-surface-container-lowest rounded-xl p-space-md shadow-[0_2px_8px_rgba(6,21,35,0.03)] hover:shadow-[0_8px_24px_rgba(27,42,56,0.06)] transition-shadow cursor-grab",
        draggable: "true",
      },
        ui.el("div", { class: "flex items-center justify-between mb-space-xs gap-2" },
          ui.el("span", { class: `px-2 py-0.5 rounded-full font-label-sm text-label-sm ${lane.tagCls}` }, lane.title.split(" ")[0]),
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, (f.created_at || "").slice(0, 10))),
        ui.el("h3", { class: "font-headline-sm text-headline-sm text-on-surface font-semibold tracking-tight mb-1" }, f.title),
        f.content && ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant line-clamp-2 mb-space-sm" }, f.content),
        ui.el("div", { class: "flex items-center gap-1.5 mb-space-xs flex-wrap" },
          f.chapter_title
            ? ui.el("span", { class: "px-2 py-0.5 rounded bg-surface-container font-label-sm text-label-sm text-on-surface-variant" }, `关联：${f.chapter_title}`)
            : (f.outline_node_id == null
                ? ui.el("span", { class: "inline-flex items-center gap-1 px-2 py-0.5 rounded bg-tertiary-fixed text-on-tertiary-fixed font-label-sm text-label-sm font-medium" }, ui.icon("link_off", "text-[12px]"), "未归属")
                : ui.el("span", { class: "font-label-sm text-label-sm text-outline" }, "未关联章节")),
          f.outline_node_id
            ? ui.el("a", {
                class: "inline-flex items-center gap-1 px-2 py-0.5 rounded bg-secondary-fixed text-on-secondary-fixed font-label-sm text-label-sm hover:bg-secondary hover:text-on-secondary transition-colors cursor-pointer",
                title: "点击跳转至对应大纲节点",
                onclick: (e) => { e.stopPropagation(); location.hash = `#/outline/${workId}?node_id=${f.outline_node_id}`; },
              }, ui.icon("account_tree", "text-[12px]"), f.outline_node_title || ("大纲 #" + f.outline_node_id))
            : null),
        ui.el("div", { class: "flex items-center justify-end gap-1 pt-space-xs border-t border-surface-container" },
          ui.el("button", {
            class: `${actionCls} hover:text-secondary hover:bg-secondary-fixed`, title: nextTip,
            onclick: async () => {
              try {
                await api.patch(`/foreshadows/${f.id}`, { status: nextStatus });
                ui.toast(`已${nextTip.replace("标记为", "移至")}`, "ok");
                router.dispatch();
              } catch (e) { ui.toast(e.message, "err"); }
            },
          }, ui.icon(nextIcon, "text-[18px]")),
          ui.el("button", {
            class: `${actionCls} hover:text-on-surface hover:bg-surface-container-high`, title: "编辑",
            onclick: () => editDialog(f),
          }, ui.icon("edit", "text-[18px]")),
          ui.el("button", {
            class: `${actionCls} hover:text-error hover:bg-error-container`, title: "删除",
            onclick: async () => {
              const ok = await ui.confirm("删除伏笔", `将删除「${f.title}」，且不可恢复。确定继续？`, "删除", true);
              if (!ok) return;
              try {
                await api.del(`/foreshadows/${f.id}`);
                ui.toast("已删除", "ok");
                router.dispatch();
              } catch (e) { ui.toast(e.message, "err"); }
            },
          }, ui.icon("delete", "text-[18px]"))));
      el.addEventListener("dragstart", (e) => {
        dragCard = f;
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", String(f.id));
        el.classList.add("opacity-40");
      });
      el.addEventListener("dragend", () => {
        dragCard = null;
        el.classList.remove("opacity-40");
      });
      return el;
    }

    function editDialog(f) {
      const isNew = !f;
      const inputCls = "w-full px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-md text-body-md";
      const title = ui.el("input", { class: inputCls, placeholder: "伏笔标题，如：太虚残剑断刃之谜", value: f?.title || "" });
      const content = ui.el("textarea", { class: inputCls + " min-h-[120px] resize-y", placeholder: "伏笔内容：在哪里埋下、指向什么、预计何时回收…" }, f?.content || "");
      const chapterSel = ui.el("select", { class: inputCls },
        ui.el("option", { value: "" }, "（不关联章节）"),
        chapters.map((c) => ui.el("option", { value: String(c.id) }, c.title)));
      if (f?.chapter_id) chapterSel.value = String(f.chapter_id);

      const outlineSel = ui.el("select", { class: inputCls },
        ui.el("option", { value: "" }, "（不关联大纲节点）"),
        outlineNodes.map((n) => ui.el("option", { value: String(n.id) }, n.title)));
      if (f?.outline_node_id) outlineSel.value = String(f.outline_node_id);

      const close = (ok) => {
        overlay.remove();
        if (!ok) return;
        const body = {
          title: title.value.trim(),
          content: content.value.trim(),
          chapter_id: chapterSel.value ? Number(chapterSel.value) : null,
          outline_node_id: outlineSel.value ? Number(outlineSel.value) : null,
        };
        if (!body.title) { ui.toast("标题不能为空", "err"); return; }
        (async () => {
          try {
            if (isNew) await api.post(`/works/${workId}/foreshadows`, body);
            else await api.patch(`/foreshadows/${f.id}`, body);
            ui.toast(isNew ? "伏笔已创建" : "伏笔已更新", "ok");
            router.dispatch();
          } catch (e) { ui.toast(e.message, "err"); }
        })();
      };
      const field = (label, node) => ui.el("label", { class: "flex flex-col gap-1" },
        ui.el("span", { class: "font-label-md text-label-md text-on-surface-variant" }, label), node);
      const overlay = ui.el("div", {
        class: "fixed inset-0 z-[90] bg-ink-black/40 backdrop-blur-sm flex items-center justify-center",
        onclick: (e) => { if (e.target === overlay) close(false); },
      },
        ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-lg w-[480px] max-w-[calc(100vw-2rem)] mx-2 sm:mx-0 shadow-[0_12px_32px_rgba(27,42,56,0.12)] flex flex-col gap-space-md" },
          ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, isNew ? "新建伏笔" : "编辑伏笔"),
          field("标题", title),
          field("内容", content),
          field("关联章节", chapterSel),
          field("关联大纲节点", outlineSel),
          ui.el("div", { class: "flex justify-end gap-2" },
            ui.el("button", { class: "px-4 py-2 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md", onclick: () => close(false) }, "取消"),
            ui.el("button", { class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md", onclick: () => close(true) }, isNew ? "创建" : "保存"))));
      document.getElementById("modal-root").append(overlay);
      title.focus();
    }
  }

  function emptyState(icon, text) {
    return ui.el("div", { class: "flex flex-col items-center gap-space-md py-space-xl text-center" },
      ui.icon(icon, "text-[48px] text-outline-variant"),
      ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" }, text));
  }
});
