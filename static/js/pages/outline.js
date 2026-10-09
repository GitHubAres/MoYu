/* 故事大纲页（对应设计稿 _3）：左卷轴拓扑树 + 节点详情 + AI 剧构推演 */
const _ol = { collapsed: new Set(), selected: {} };

registerPage("outline", async (view, { segs, query }) => {
  const workId = Number(segs[0]) || null;
  if (!workId) return outlinePickWork(view);

  let work, tree, volumes;
  try {
    [work, tree, volumes] = await Promise.all([
      api.get(`/works/${workId}`),
      api.get(`/works/${workId}/outline`),
      api.get(`/works/${workId}/tree`),
    ]);
  } catch (e) { ui.toast(e.message, "err"); return; }

  ui.setCrumb("故事大纲", work.title);
  ui.setActions(
    ui.el("button", {
      class: "flex items-center gap-1 px-space-sm py-1.5 rounded-full bg-surface-container hover:bg-surface-container-high text-on-surface transition-all",
      onclick: () => createNode(null),
    }, ui.icon("add", "text-[18px]"), ui.el("span", { class: "font-label-md text-label-md" }, "新增大纲节点")),
  );

  const STATUS = {
    pending: { label: "草稿", icon: "schedule", cls: "bg-surface-container text-on-surface-variant" },
    focus: { label: "聚焦中", icon: "adjust", cls: "bg-secondary-fixed text-on-secondary-fixed" },
    done: { label: "已完成", icon: "check_circle", cls: "bg-primary-fixed text-on-primary-fixed" },
  };

  const flat = [];
  (function walk(nodes, depth, parent) {
    for (const n of nodes) { flat.push({ node: n, depth, parent }); walk(n.children, depth + 1, n); }
  })(tree, 0, null);

  const total = flat.length;
  const qNodeId = query && query.node_id ? Number(query.node_id) : null;
  if (qNodeId && flat.some((f) => f.node.id === qNodeId)) {
    _ol.selected[workId] = qNodeId;
  } else if (!_ol.selected[workId] || !flat.some((f) => f.node.id === _ol.selected[workId])) {
    _ol.selected[workId] = flat.length ? flat[0].node.id : null;
  }

  const treeBox = ui.el("div", { class: "flex flex-col gap-1 max-h-[70vh] overflow-y-auto pr-1" });
  const detailBox = ui.el("div", { class: "flex flex-col gap-space-lg" });
  let chapterAreaEl = null;

  view.append(
    ui.el("div", { class: "flex flex-col gap-space-lg" },
      ui.el("div", { class: "flex flex-col gap-1" },
        ui.el("span", { class: "font-label-sm text-label-sm text-secondary tracking-widest uppercase" }, "STORY OUTLINE · 故事大纲"),
        ui.el("h1", { class: "font-display text-display text-primary tracking-tight" }, work.title),
        ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" },
          work.intro || "树形大纲节点：卷 / 章层级组织，支持关联章节与 AI 剧构推演。")),
      ui.el("div", { class: "grid grid-cols-12 gap-space-lg items-start" },
        ui.el("aside", { class: "col-span-12 lg:col-span-4 xl:col-span-3 flex flex-col gap-space-md" },
          ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-md shadow-[0_4px_20px_rgba(6,21,35,0.03)] flex flex-col gap-space-md" },
            ui.el("div", { class: "flex items-center justify-between" },
              ui.el("div", { class: "flex items-center gap-1.5" },
                ui.icon("menu_book", "text-[20px] text-on-surface-variant"),
                ui.el("span", { class: "font-headline-sm text-headline-sm text-primary" }, "卷轴拓扑")),
              ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, `共 ${total} 节点`)),
            treeBox)),
        ui.el("main", { class: "col-span-12 lg:col-span-8 xl:col-span-9" }, detailBox))));

  /* ---------- 左侧拓扑树 ---------- */

  function renderTree() {
    treeBox.innerHTML = "";
    if (!tree.length) {
      treeBox.append(ui.el("div", { class: "flex flex-col items-center gap-space-sm py-space-lg text-center" },
        ui.icon("account_tree", "text-[36px] text-outline-variant"),
        ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant" }, "还没有大纲节点"),
        ui.el("button", {
          class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md",
          onclick: () => createNode(null),
        }, "创建第一个节点")));
      return;
    }
    for (const n of tree) treeBox.append(treeNode(n, 0));
  }

  function treeNode(n, depth) {
    const hasKids = n.children && n.children.length;
    const collapsed = _ol.collapsed.has(n.id);
    const selected = n.id === _ol.selected[workId];
    const st = STATUS[n.status] || STATUS.pending;

    const head = ui.el("div", {
      class: selected
        ? "flex items-center justify-between p-2.5 rounded-lg bg-primary-container text-on-primary shadow-xs cursor-pointer"
        : "flex items-center justify-between p-2 rounded-lg hover:bg-surface-container-high transition-colors cursor-pointer text-on-surface-variant",
      style: depth ? `margin-left:${depth * 12}px` : "",
      onclick: () => { _ol.selected[workId] = n.id; renderTree(); renderDetail(); },
    },
      ui.el("div", { class: "flex items-center gap-2 min-w-0" },
        hasKids
          ? ui.el("span", {
              class: "material-symbols-outlined text-[18px] " + (selected ? "text-on-primary-container" : "text-outline"),
              onclick: (e) => {
                e.stopPropagation();
                collapsed ? _ol.collapsed.delete(n.id) : _ol.collapsed.add(n.id);
                renderTree();
              },
            }, collapsed ? "chevron_right" : "expand_more")
          : ui.el("span", { class: "w-[18px] shrink-0" }),
        ui.el("div", { class: "flex flex-col min-w-0" },
          ui.el("div", { class: "flex items-center gap-1 min-w-0" },
            ui.el("span", {
              class: (depth === 0 ? "font-body-md text-body-md font-semibold " : "font-body-sm text-body-sm ") +
                (selected ? "text-on-primary" : depth === 0 ? "text-on-surface" : "") + " truncate",
            }, n.title),
            n.timeline_count > 0 ? ui.el("span", {
              class: "inline-flex items-center gap-0.5 px-1 py-0.2 rounded text-[10px] bg-secondary/15 text-secondary font-mono shrink-0",
              title: "关联 " + n.timeline_count + " 个时间线事件",
            }, ui.icon("timeline", "text-[11px]"), String(n.timeline_count)) : null,
            n.foreshadow_count > 0 ? ui.el("span", {
              class: "inline-flex items-center gap-0.5 px-1 py-0.2 rounded text-[10px] bg-amber-500/15 text-amber-700 dark:text-amber-300 font-mono shrink-0",
              title: "关联 " + n.foreshadow_count + " 条伏笔",
            }, ui.icon("bookmark", "text-[11px]"), String(n.foreshadow_count)) : null),
          depth === 0 && n.synopsis
            ? ui.el("span", { class: "font-label-sm text-label-sm truncate " + (selected ? "text-on-primary-container" : "text-on-surface-variant") },
                n.synopsis.slice(0, 24))
            : null)),
      n.status === "focus"
        ? ui.el("span", { class: "flex h-2 w-2 rounded-full bg-cinnabar-accent shrink-0" })
        : ui.icon(st.icon, "text-[16px] shrink-0 " + (selected ? "text-on-primary-container" : n.status === "done" ? "text-secondary" : "text-outline")));

    const wrap = ui.el("div", { class: "flex flex-col gap-1" }, head);
    if (hasKids && !collapsed) {
      const kids = ui.el("div", { class: "flex flex-col gap-1" });
      for (const c of n.children) kids.append(treeNode(c, depth + 1));
      wrap.append(kids);
    }
    return wrap;
  }

  /* ---------- 中间节点详情 ---------- */

  function findNode(id) {
    const f = flat.find((x) => x.node.id === id);
    return f || null;
  }

  function nodePath(n) {
    const names = [];
    let cur = findNode(n.id);
    while (cur) { names.unshift(cur.node.title); cur = cur.parent ? findNode(cur.parent.id) : null; }
    return names;
  }

  function renderDetail() {
    detailBox.innerHTML = "";
    const f = findNode(_ol.selected[workId]);
    if (!f) {
      detailBox.append(ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-xl flex flex-col items-center gap-space-md text-center shadow-[0_4px_20px_rgba(6,21,35,0.03)]" },
        ui.icon("account_tree", "text-[48px] text-outline-variant"),
        ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" }, "从左侧选择一个节点，或新建大纲节点开始规划剧情")));
      return;
    }
    const node = f.node;
    const st = STATUS[node.status] || STATUS.pending;

    /* 状态切换 pills */
    const statusPills = ui.el("div", { class: "flex items-center gap-1 bg-surface-container-low rounded-full p-1" });
    for (const [k, meta] of Object.entries(STATUS)) {
      statusPills.append(ui.el("button", {
        class: "px-3 py-1 rounded-full font-label-sm text-label-sm transition-all " +
          (node.status === k ? "bg-surface-container-lowest text-primary shadow-xs font-semibold" : "text-on-surface-variant hover:text-on-surface"),
        onclick: async () => {
          try {
            await api.patch(`/outline/${node.id}`, { status: k });
            node.status = k;
            renderTree(); renderDetail();
          } catch (e) { ui.toast(e.message, "err"); }
        },
      }, meta.label));
    }

    /* 梗概编辑 */
    const synInput = ui.el("textarea", {
      class: "w-full bg-transparent outline-none font-serif-content text-body-lg text-body-lg leading-relaxed resize-y min-h-[120px]",
      placeholder: "用几句话概括该节点的核心剧情…",
    }, node.synopsis || "");

    /* 章节关联区 */
    chapterAreaEl = ui.el("div", { class: "flex flex-col gap-space-sm" });

    const card = ui.el("article", {
      class: "bg-surface-container-lowest rounded-xl p-space-xl shadow-[0_4px_20px_rgba(6,21,35,0.03)] flex flex-col gap-space-lg relative overflow-hidden",
    },
      ui.el("div", { class: "absolute -right-20 -top-20 w-80 h-80 rounded-full bg-secondary-fixed/30 blur-3xl pointer-events-none" }),
      /* 头部：路径 + 状态 + 章节映射 */
      ui.el("div", { class: "flex flex-col md:flex-row md:items-center justify-between gap-space-md relative" },
        ui.el("div", { class: "flex flex-col gap-1 min-w-0" },
          ui.el("div", { class: "flex items-center gap-space-xs flex-wrap" },
            ui.el("span", { class: "font-label-sm text-label-sm bg-primary-container text-on-primary px-2.5 py-0.5 rounded-full font-medium" },
              nodePath(node).join(" / ")),
            ui.el("span", { class: `font-label-sm text-label-sm px-2 py-0.5 rounded-full ${st.cls}` }, st.label)),
          ui.el("div", { class: "flex items-center gap-2" },
            ui.el("h1", { class: "font-headline-lg text-headline-lg text-primary tracking-tight font-bold" }, node.title),
            ui.el("button", {
              class: "p-1.5 rounded-lg text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors",
              title: "重命名",
              onclick: () => renameNode(node),
            }, ui.icon("edit", "text-[18px]")))),
        chapterAreaEl),
      /* 梗概卡 */
      ui.el("div", { class: "flex flex-col gap-space-xs bg-surface-container-low/70 p-space-lg rounded-xl relative" },
        ui.el("div", { class: "flex items-center justify-between" },
          ui.el("div", { class: "flex items-center gap-2" },
            ui.icon("description", "text-[20px] text-secondary"),
            ui.el("h2", { class: "font-headline-sm text-headline-sm text-primary" }, "核心剧情梗概 (Synopsis)")),
          ui.el("div", { class: "flex items-center gap-2" }, statusPills,
            ui.el("button", {
              class: "flex items-center gap-0.5 font-label-sm text-label-sm text-secondary hover:underline",
              onclick: async () => {
                try {
                  const updated = await api.patch(`/outline/${node.id}`, { synopsis: synInput.value.trim() });
                  node.synopsis = updated.synopsis;
                  ui.toast("梗概已保存", "ok");
                  renderTree();
                } catch (e) { ui.toast(e.message, "err"); }
              },
            }, ui.icon("save", "text-[16px]"), "保存梗概"))),
        synInput),
      /* 剧情脉络 (Plot Triad: 时间线与伏笔) */
      renderPlotTriadSection(node),
      /* 节点操作 */
      ui.el("div", { class: "flex items-center gap-2 flex-wrap relative" },
        ui.el("button", {
          class: "flex items-center gap-1 px-3 py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md transition-colors",
          onclick: () => createNode(node.id),
        }, ui.icon("add", "text-[16px]"), "新建子节点"),
        !node.chapter_id && ui.el("button", {
          class: "flex items-center gap-1 px-3 py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md transition-colors",
          onclick: () => createChapter(node),
        }, ui.icon("note_add", "text-[16px]"), "从节点创建章节"),
        ui.el("button", {
          class: "flex items-center gap-1 px-3 py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md transition-colors",
          onclick: () => aiDraft(node),
        }, ui.icon("edit_document", "text-[16px]"), "AI 生成章节草稿"),
        ui.el("button", {
          class: "flex items-center gap-1 px-3 py-1.5 rounded-lg text-error hover:bg-error-container font-label-md text-label-md transition-colors ml-auto",
          onclick: () => removeNode(node),
        }, ui.icon("delete", "text-[16px]"), "删除节点")),
      /* AI 章节草稿预览区 */
      ui.el("div", { id: "ai-draft-slot", class: "flex flex-col gap-space-md relative" }),
      /* AI 生成子节点 */
      aiGenerateChildrenSection(node),
      /* AI 剧构推演 */
      aiTwistSection(node));

    detailBox.append(card);
    renderChapterArea();
  }

  function renderChapterArea() {
    const f = findNode(_ol.selected[workId]);
    if (!f || !chapterAreaEl) return;
    const node = f.node;
    chapterAreaEl.innerHTML = "";
    if (node.chapter_id) {
      chapterAreaEl.append(
        ui.el("div", { class: "bg-surface-container-low px-4 py-2 rounded-xl flex items-center gap-space-xs shrink-0 self-start md:self-auto" },
          ui.icon("link", "text-[20px] text-secondary"),
          ui.el("div", { class: "flex flex-col" },
            ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "正文映射关联"),
            ui.el("span", { class: "font-label-md text-label-md font-semibold text-primary" },
              `已映射 · ${node.chapter_title || "章节 " + node.chapter_id}（${ui.fmtWords(node.chapter_words)} 字）`)),
          ui.el("button", {
            class: "p-1.5 rounded-lg text-on-surface-variant hover:text-primary hover:bg-surface-container-high transition-colors",
            title: "打开工作台",
            onclick: () => { location.hash = `#/workbench/${workId}?chapter=${node.chapter_id}`; },
          }, ui.icon("edit_note", "text-[18px]")),
          ui.el("button", {
            class: "p-1.5 rounded-lg text-on-surface-variant hover:text-error hover:bg-error-container transition-colors",
            title: "解除关联",
            onclick: async () => {
              try {
                await api.post(`/outline/${node.id}/link-chapter`, { chapter_id: null });
                node.chapter_id = null; node.chapter_title = null; node.chapter_words = null;
                ui.toast("已解除章节关联", "ok");
                renderTree(); renderDetail();
              } catch (e) { ui.toast(e.message, "err"); }
            },
          }, ui.icon("link_off", "text-[18px]"))));
    } else {
      chapterAreaEl.append(
        ui.el("div", { class: "bg-surface-container-low px-4 py-2 rounded-xl flex items-center gap-space-xs shrink-0 self-start md:self-auto" },
          ui.icon("link_off", "text-[20px] text-on-surface-variant"),
          ui.el("div", { class: "flex flex-col" },
            ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "正文映射关联"),
            ui.el("span", { class: "font-label-md text-label-md text-on-surface-variant" }, "未关联章节")),
          ui.el("button", {
            class: "p-1.5 rounded-lg text-on-surface-variant hover:text-primary hover:bg-surface-container-high transition-colors",
            title: "关联已有章节",
            onclick: () => linkChapter(node),
          }, ui.icon("add_link", "text-[18px]"))));
    }
  }

  /* ---------- 节点操作 ---------- */

  async function createNode(parentId) {
    const title = await ui.prompt(
      parentId ? "新建子节点" : "新建大纲节点",
      parentId ? `在「${findNode(parentId)?.node.title || ""}」下新建，输入节点标题` : "输入节点标题（如 卷一：凡尘问道）");
    if (!title) return;
    try {
      const n = await api.post(`/works/${workId}/outline`, { title, parent_id: parentId });
      await reload(n.id);
      ui.toast("节点已创建", "ok");
    } catch (e) { ui.toast(e.message, "err"); }
  }

  async function renameNode(node) {
    const title = await ui.prompt("重命名节点", "节点标题", node.title);
    if (!title || title === node.title) return;
    try {
      await api.patch(`/outline/${node.id}`, { title });
      await reload(node.id);
    } catch (e) { ui.toast(e.message, "err"); }
  }

  async function removeNode(node) {
    const ok = await ui.confirm(
      "删除大纲节点",
      `将删除「${node.title}」及其全部子节点（约 ${node.children.length} 个直接子节点）。\n关联的章节正文不会被删除，仅解除映射关系。确定继续？`,
      "删除", true);
    if (!ok) return;
    try {
      await api.del(`/outline/${node.id}`);
      ui.toast("节点已删除", "ok");
      await reload(null);
    } catch (e) { ui.toast(e.message, "err"); }
  }

  async function createChapter(node) {
    try {
      const ch = await api.post(`/outline/${node.id}/create-chapter`);
      ui.toast(`已创建章节「${ch.title}」并关联`, "ok");
      await reload(node.id);
    } catch (e) { ui.toast(e.message, "err"); }
  }

  async function linkChapter(node) {
    const chapters = [];
    for (const v of volumes) for (const c of v.chapters) chapters.push({ ...c, volume_title: v.title });
    if (!chapters.length) { ui.toast("该作品还没有章节，请先创建或使用「从节点创建章节」", "info"); return; }
    const picked = await pickChapterDialog(chapters);
    if (!picked) return;
    try {
      await api.post(`/outline/${node.id}/link-chapter`, { chapter_id: picked });
      await reload(node.id);
      ui.toast("已关联章节", "ok");
    } catch (e) { ui.toast(e.message, "err"); }
  }

  function pickChapterDialog(chapters) {
    return new Promise((resolve) => {
      const root = document.getElementById("modal-root");
      const sel = ui.el("select", {
        class: "w-full px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-md text-body-md",
      });
      for (const c of chapters) {
        sel.append(ui.el("option", { value: c.id }, `${c.volume_title} · ${c.title}（${ui.fmtWords(c.word_count)} 字）`));
      }
      const close = (val) => { overlay.remove(); resolve(val); };
      const overlay = ui.el("div", {
        class: "fixed inset-0 z-[90] bg-ink-black/40 backdrop-blur-sm flex items-center justify-center",
        onclick: (e) => { if (e.target === overlay) close(null); },
      },
        ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-lg w-[420px] max-w-[calc(100vw-2rem)] mx-2 sm:mx-0 shadow-[0_12px_32px_rgba(27,42,56,0.12)] flex flex-col gap-space-md" },
          ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, "关联已有章节"),
          sel,
          ui.el("div", { class: "flex justify-end gap-2" },
            ui.el("button", { class: "px-4 py-2 rounded-lg bg-surface-container font-label-md text-label-md", onclick: () => close(null) }, "取消"),
            ui.el("button", { class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md", onclick: () => close(Number(sel.value)) }, "关联"))));
      root.append(overlay);
    });
  }

  /* ---------- AI 生成章节草稿 ---------- */

  async function aiDraft(node) {
    const slot = detailBox.querySelector("#ai-draft-slot");
    slot.innerHTML = "";
    const card = ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-lg ai-glow flex flex-col gap-space-sm" },
      ui.el("div", { class: "flex items-center gap-2" },
        ui.icon("edit_document", "text-[20px] text-secondary"),
        ui.el("span", { class: "font-headline-sm text-headline-sm text-primary" }, "AI 章节草稿（预览）"),
        ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "生成中…")));
    slot.append(card);
    let res;
    try {
      res = await api.post("/ai/generate", {
        task: "outline_draft",
        instruction: "根据大纲节点梗概生成一版章节正文草稿，保持网文叙事节奏，800-1500 字。",
        context: `作品：《${work.title}》${work.genre ? "（" + work.genre + "）" : ""}\n节点：${nodePath(node).join(" / ")}\n梗概：${node.synopsis || "（暂无梗概，请根据节点标题合理展开）"}`,
        selection: "",
        length: "long",
        candidates: 1,
        stream: false,
      });
    } catch (e) {
      card.remove();
      ui.toast(e.message, "err");
      return;
    }
    const draft = (res.candidates && res.candidates[0]) || "";
    card.innerHTML = "";
    card.append(
      ui.el("div", { class: "flex items-center justify-between" },
        ui.el("div", { class: "flex items-center gap-2" },
          ui.icon("edit_document", "text-[20px] text-secondary"),
          ui.el("span", { class: "font-headline-sm text-headline-sm text-primary" }, "AI 章节草稿（预览）"),
          ui.el("span", { class: "font-label-sm text-label-sm px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed" }, "暂存态 · 采纳后写入")),
        ui.el("div", { class: "flex items-center gap-2" },
          ui.el("button", {
            class: "px-3 py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md",
            onclick: () => aiDraft(node),
          }, "重试"),
          ui.el("button", {
            class: "px-3 py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md",
            onclick: () => card.remove(),
          }, "放弃"),
          ui.el("button", {
            class: "px-4 py-1.5 rounded-lg bg-secondary text-on-secondary font-label-md text-label-md shadow-sm hover:opacity-90",
            onclick: () => adoptDraft(node, draft, card),
          }, "采纳写入章节"))),
      ui.el("p", { class: "font-serif-content text-body-md text-body-md leading-relaxed whitespace-pre-wrap max-h-[320px] overflow-y-auto" }, draft));
  }

  async function adoptDraft(node, draft, card) {
    try {
      let chapterId = node.chapter_id;
      if (!chapterId) {
        const ch = await api.post(`/outline/${node.id}/create-chapter`);
        chapterId = ch.id;
        ui.toast(`已创建章节「${ch.title}」`, "ok");
      }
      const ch = await api.get(`/chapters/${chapterId}`);
      let content = draft;
      if (ch.content && ch.content.trim()) {
        const ok = await ui.confirm("章节已有正文",
          `「${ch.title}」已有 ${ui.fmtWords(ch.word_count)} 字正文，采纳后草稿将追加到章节末尾（不覆盖）。确定继续？`, "追加");
        if (!ok) return;
        content = ch.content.replace(/\s+$/, "") + "\n\n" + draft;
      }
      await api.patch(`/chapters/${chapterId}`, { content, snapshot_source: "ai_outline" });
      ui.toast("草稿已写入章节", "ok");
      card.remove();
      await reload(node.id);
    } catch (e) { ui.toast(e.message, "err"); }
  }

  /* ---------- AI 剧构推演 ---------- */

  function aiTwistSection(node) {
    const list = ui.el("div", { class: "grid grid-cols-1 md:grid-cols-3 gap-space-md" });
    const btnLabel = ui.el("span", {}, "AI 推演剧情走向");
    const runBtn = ui.el("button", {
      class: "flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-secondary text-on-secondary hover:opacity-90 font-label-md text-label-md shadow-sm transition-all",
      onclick: async () => {
        runBtn.disabled = true;
        btnLabel.textContent = "推演中…";
        list.innerHTML = "";
        try {
          const res = await api.post("/ai/generate", {
            task: "outline_twist",
            instruction: "基于该大纲节点生成 3 个方向各异的剧情转折建议（如情感悬念 / 战局博弈 / 暗线递进），每条 60-120 字，彼此独立。",
            context: `作品：《${work.title}》${work.genre ? "（" + work.genre + "）" : ""}\n节点：${nodePath(node).join(" / ")}\n梗概：${node.synopsis || "（暂无梗概）"}`,
            selection: "",
            length: "short",
            candidates: 3,
            stream: false,
          });
          renderTwists(res.candidates || []);
        } catch (e) {
          ui.toast(e.message, "err");
        } finally {
          runBtn.disabled = false;
          btnLabel.textContent = "AI 推演剧情走向";
        }
      },
    }, ui.icon("psychology", "text-[16px]"), btnLabel);

    list.append(ui.el("div", { class: "col-span-full font-body-sm text-body-sm text-on-surface-variant bg-surface-container-lowest/60 rounded-lg p-space-md text-center" },
      "点击「AI 推演剧情走向」，基于当前节点张力生成 3 个转折建议"));

    function renderTwists(cands) {
      list.innerHTML = "";
      cands.slice(0, 3).forEach((text, i) => {
        list.append(ui.el("div", { class: "bg-surface-container-lowest p-space-md rounded-xl shadow-xs ai-glow flex flex-col justify-between gap-space-sm hover:shadow-md transition-shadow" },
          ui.el("div", { class: "flex flex-col gap-1.5" },
            ui.el("div", { class: "flex items-center justify-between" },
              ui.el("span", { class: `font-label-sm text-label-sm px-2 py-0.5 rounded font-semibold ${i === 0 ? "bg-cinnabar-accent/10 text-cinnabar-accent" : "bg-secondary-fixed text-on-secondary-fixed"}` },
                `转折 0${i + 1}`),
              ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "AI 推演")),
            ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant leading-normal whitespace-pre-wrap" }, text)),
          ui.el("button", {
            class: "w-full py-1.5 rounded bg-surface-container-low hover:bg-surface-container text-primary font-label-sm text-label-sm font-medium transition-colors",
            onclick: async () => {
              const syn = detailBox.querySelector("textarea");
              const merged = ((syn ? syn.value : node.synopsis) || "").replace(/\s+$/, "") +
                "\n\n【转折】 " + text.trim();
              try {
                const updated = await api.patch(`/outline/${node.id}`, { synopsis: merged });
                node.synopsis = updated.synopsis;
                ui.toast("转折建议已并入梗概", "ok");
                renderTree(); renderDetail();
              } catch (e) { ui.toast(e.message, "err"); }
            },
          }, "采纳并并入梗概")));
      });
    }

    return ui.el("div", { class: "bg-surface-container-low rounded-xl p-space-lg flex flex-col gap-space-md relative" },
      ui.el("div", { class: "flex flex-col sm:flex-row sm:items-center justify-between gap-space-sm" },
        ui.el("div", { class: "flex items-center gap-2" },
          ui.icon("psychology", "text-[24px] text-secondary"),
          ui.el("div", {},
            ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary" }, "墨语MoYu AI 剧构推演"),
            ui.el("p", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "基于当前大纲张力与上下文生成剧情走向建议"))),
        runBtn),
      list);
  }

  /* ---------- AI 生成子节点 ---------- */

  function aiGenerateChildrenSection(node) {
    const list = ui.el("div", { class: "grid grid-cols-1 md:grid-cols-2 gap-space-md" });
    const hintInput = ui.el("textarea", {
      class: "w-full bg-surface-container-lowest rounded-lg px-3 py-2 font-body-md text-body-md leading-relaxed resize-y min-h-[72px] outline-none focus:ring-1 focus:ring-primary/30",
      placeholder: "补充要求，例如：生成 5 个情节点 / 侧重人物成长 / 包含一个反转…（可选）",
    });
    const btnLabel = ui.el("span", {}, "AI 生成子节点");
    const runBtn = ui.el("button", {
      class: "flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-secondary text-on-secondary hover:opacity-90 font-label-md text-label-md shadow-sm transition-all",
      onclick: async () => {
        runBtn.disabled = true;
        btnLabel.textContent = "生成中…";
        list.innerHTML = "";
        try {
          const res = await api.post("/ai/generate", {
            task: "outline",
            instruction: "请为当前大纲节点生成 3-6 个子节点标题，用于细化剧情结构。只输出子节点标题列表，每行一个标题，或返回 JSON 数组。标题应简洁、有张力。",
            context: `作品：《${work.title}》${work.genre ? "（" + work.genre + "）" : ""}\n当前节点：${nodePath(node).join(" / ")}\n梗概：${node.synopsis || "（暂无梗概）"}\n${hintInput.value.trim() ? "补充要求：" + hintInput.value.trim() : ""}`,
            selection: "",
            length: "short",
            candidates: 1,
            stream: false,
            work_id: workId,
          });
          renderChildren(res.candidates && res.candidates[0] ? res.candidates[0] : "");
        } catch (e) {
          ui.toast(e.message, "err");
        } finally {
          runBtn.disabled = false;
          btnLabel.textContent = "AI 生成子节点";
        }
      },
    }, ui.icon("account_tree", "text-[16px]"), btnLabel);

    function parseChildTitles(text) {
      const t = text.trim();
      try {
        const parsed = JSON.parse(t);
        if (Array.isArray(parsed)) return parsed.map(x => String(x).trim()).filter(Boolean);
      } catch {}
      return t.split("\n")
        .map(l => l.replace(/^(\s*[\d一二三四五六七八九十]+[\.\、）\]\[]\s*|\s*[-*•]\s*|\s*[（(]\d+[)）]\s*)/, "").trim())
        .filter(l => l.length > 0 && l.length < 120);
    }

    async function createChild(title) {
      if (!title.trim()) return;
      try {
        const n = await api.post(`/works/${workId}/outline`, { title: title.trim(), parent_id: node.id });
        return n.id;
      } catch (e) { ui.toast(e.message, "err"); return null; }
    }

    function renderChildren(rawText) {
      list.innerHTML = "";
      const titles = parseChildTitles(rawText);
      if (!titles.length) {
        list.append(ui.el("div", { class: "col-span-full font-body-sm text-body-sm text-on-surface-variant bg-surface-container-lowest/60 rounded-lg p-space-md text-center" },
          "AI 未返回可识别的子节点标题，请调整要求后重试"));
        return;
      }
      const editors = titles.map((t) => ui.el("input", {
        type: "text",
        class: "w-full bg-transparent outline-none font-body-md text-body-md",
        value: t,
      }));
      const createAllBtn = ui.el("button", {
        class: "col-span-full w-full py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md shadow-sm hover:opacity-90 transition-all",
        onclick: async () => {
          createAllBtn.disabled = true;
          createAllBtn.textContent = "创建中…";
          let count = 0;
          for (const input of editors) {
            if (await createChild(input.value)) count++;
          }
          createAllBtn.disabled = false;
          createAllBtn.textContent = "全部创建";
          if (count) {
            ui.toast(`已创建 ${count} 个子节点`, "ok");
            await reload(node.id);
          }
        },
      }, "全部创建");
      list.append(createAllBtn);
      editors.forEach((input, i) => {
        list.append(ui.el("div", { class: "bg-surface-container-lowest p-space-md rounded-xl shadow-xs ai-glow flex items-center gap-space-sm" },
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant shrink-0" }, `0${i + 1}`),
          input,
          ui.el("button", {
            class: "px-3 py-1.5 rounded-lg bg-surface-container-low hover:bg-surface-container text-primary font-label-sm text-label-sm font-medium shrink-0",
            onclick: async () => {
              if (await createChild(input.value)) {
                ui.toast(`已创建子节点「${input.value.trim()}」`, "ok");
                await reload(node.id);
              }
            },
          }, "创建")));
      });
    }

    list.append(ui.el("div", { class: "col-span-full font-body-sm text-body-sm text-on-surface-variant bg-surface-container-lowest/60 rounded-lg p-space-md text-center" },
      "输入补充要求后点击「AI 生成子节点」，基于当前节点生成下一层大纲结构"));

    return ui.el("div", { class: "bg-surface-container-low rounded-xl p-space-lg flex flex-col gap-space-md relative" },
      ui.el("div", { class: "flex flex-col sm:flex-row sm:items-center justify-between gap-space-sm" },
        ui.el("div", { class: "flex items-center gap-2" },
          ui.icon("account_tree", "text-[24px] text-secondary"),
          ui.el("div", {},
            ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary" }, "墨语MoYu AI 生成子节点"),
            ui.el("p", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "基于当前节点主题自动规划下一层大纲节点"))),
        runBtn),
      hintInput,
      list);
  }

  
  /* ---------- 剧情脉络三位一体 (Plot Triad) ---------- */

  function renderPlotTriadSection(node) {
    const section = ui.el("div", {
      class: "flex flex-col gap-space-sm bg-surface-container-low/50 p-space-md rounded-xl border border-border-feather relative",
    });

    const header = ui.el("div", { class: "flex items-center justify-between flex-wrap gap-2" },
      ui.el("div", { class: "flex items-center gap-2" },
        ui.icon("account_tree", "text-[20px] text-secondary"),
        ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, "剧情脉络 · 三位一体关联"),
        ui.el("span", { class: "font-label-sm text-[11px] text-on-surface-variant" }, "时间线事件与伏笔追踪")),
      ui.el("div", { class: "flex items-center gap-2" },
        ui.el("button", {
          class: "flex items-center gap-1 px-2.5 py-1 rounded-lg bg-surface-container hover:bg-surface-container-high text-primary font-label-sm text-label-sm transition-colors cursor-pointer",
          onclick: () => addTimelineEventModal(node),
        }, ui.icon("timeline", "text-[14px]"), "添加事件"),
        ui.el("button", {
          class: "flex items-center gap-1 px-2.5 py-1 rounded-lg bg-surface-container hover:bg-surface-container-high text-amber-700 dark:text-amber-300 font-label-sm text-label-sm transition-colors cursor-pointer",
          onclick: () => addForeshadowModal(node),
        }, ui.icon("bookmark", "text-[14px]"), "埋下伏笔")));

    const contentBox = ui.el("div", { class: "flex flex-col gap-3 pt-1" });
    section.append(header, contentBox);

    (async () => {
      try {
        const data = await api.get(`/works/${workId}/outline/nodes/${node.id}/plot-items`);
        contentBox.innerHTML = "";
        const events = data.timeline_events || [];
        const foreshadows = data.foreshadows || [];

        if (!events.length && !foreshadows.length) {
          contentBox.append(ui.el("div", { class: "text-center py-3 text-on-surface-variant text-body-sm font-label-sm" },
            "当前大纲节点暂无关联的时间线事件或伏笔，点击右上角快速关联"));
          return;
        }

        const grid = ui.el("div", { class: "grid grid-cols-1 md:grid-cols-2 gap-3" });

        const evCol = ui.el("div", { class: "flex flex-col gap-2" },
          ui.el("div", { class: "flex items-center justify-between font-label-sm text-on-surface-variant pb-1 border-b border-border-feather" },
            ui.el("span", { class: "font-semibold flex items-center gap-1" }, ui.icon("timeline", "text-[15px] text-secondary"), `时间线事件 (${events.length})`),
            ui.el("a", { class: "hover:text-primary cursor-pointer text-[11px]", onclick: () => { location.hash = `#/timeline/${workId}`; } }, "前往时间线 →")));
        if (!events.length) {
          evCol.append(ui.el("div", { class: "text-[12px] text-on-surface-variant/70 italic py-1" }, "无关联事件"));
        } else {
          for (const ev of events) {
            evCol.append(ui.el("div", {
              class: "p-2 rounded-lg bg-surface-container-lowest border border-border-feather shadow-xs flex flex-col gap-1 hover:border-primary/40 transition-colors",
            },
              ui.el("div", { class: "flex items-center justify-between gap-1 text-[12px]" },
                ui.el("span", { class: "font-semibold text-primary truncate" }, ev.time_label || "未定时间"),
                ui.el("a", {
                  class: "text-secondary hover:underline text-[11px] cursor-pointer",
                  onclick: () => { location.hash = `#/timeline/${workId}`; },
                }, "查看")),
              ui.el("p", { class: "text-[12px] text-on-surface line-clamp-2" }, ev.event || "")));
          }
        }

        const fsCol = ui.el("div", { class: "flex flex-col gap-2" },
          ui.el("div", { class: "flex items-center justify-between font-label-sm text-on-surface-variant pb-1 border-b border-border-feather" },
            ui.el("span", { class: "font-semibold flex items-center gap-1" }, ui.icon("bookmark", "text-[15px] text-amber-600"), `伏笔记录 (${foreshadows.length})`),
            ui.el("a", { class: "hover:text-primary cursor-pointer text-[11px]", onclick: () => { location.hash = `#/board/${workId}`; } }, "前往伏笔看板 →")));
        if (!foreshadows.length) {
          fsCol.append(ui.el("div", { class: "text-[12px] text-on-surface-variant/70 italic py-1" }, "无关联伏笔"));
        } else {
          for (const fsItem of foreshadows) {
            const stLabel = fsItem.status === "resolved" ? "已回收" : "埋设中";
            const stCls = fsItem.status === "resolved" ? "bg-emerald-500/10 text-emerald-600" : "bg-amber-500/10 text-amber-700";
            fsCol.append(ui.el("div", {
              class: "p-2 rounded-lg bg-surface-container-lowest border border-border-feather shadow-xs flex flex-col gap-1 hover:border-primary/40 transition-colors",
            },
              ui.el("div", { class: "flex items-center justify-between gap-1 text-[12px]" },
                ui.el("span", { class: "font-semibold text-primary truncate" }, fsItem.title),
                ui.el("span", { class: `px-1.5 py-0.2 rounded text-[10px] ${stCls}` }, stLabel)),
              fsItem.content ? ui.el("p", { class: "text-[12px] text-on-surface-variant line-clamp-2" }, fsItem.content) : null));
          }
        }

        grid.append(evCol, fsCol);
        contentBox.append(grid);
      } catch (err) {
        contentBox.innerHTML = `<span class="text-error text-body-sm">加载剧情脉络失败: ${err.message}</span>`;
      }
    })();

    return section;
  }

  function addTimelineEventModal(node) {
    const inputCls = "w-full px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-md text-body-md";
    const labelCls = "flex flex-col gap-1 font-label-sm text-label-sm text-on-surface-variant";
    const timeInput = ui.el("input", { class: inputCls, placeholder: "如：第10章·秘境试炼" });
    const eventInput = ui.el("textarea", { class: inputCls + " resize-y min-h-[80px]", placeholder: "记录该大纲节点发生的剧情事件…" });
    const charsInput = ui.el("input", { class: inputCls, placeholder: "涉及人物（顿号分隔，可留空）" });

    const overlay = ui.el("div", {
      class: "fixed inset-0 z-[90] bg-ink-black/40 backdrop-blur-sm flex items-center justify-center",
      onclick: (e) => { if (e.target === overlay) overlay.remove(); },
    },
      ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-lg w-[460px] max-w-[calc(100vw-2rem)] mx-2 shadow-xl flex flex-col gap-space-md" },
        ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, "为「" + node.title + "」添加时间线事件"),
        ui.el("label", { class: labelCls }, "时间标签", timeInput),
        ui.el("label", { class: labelCls }, "事件内容", eventInput),
        ui.el("label", { class: labelCls }, "涉及人物", charsInput),
        ui.el("div", { class: "flex justify-end gap-2 pt-2" },
          ui.el("button", {
            class: "px-4 py-2 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md",
            onclick: () => overlay.remove(),
          }, "取消"),
          ui.el("button", {
            class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md",
            onclick: async () => {
              if (!eventInput.value.trim()) { ui.toast("事件内容不能为空", "err"); return; }
              try {
                await api.post(`/works/${workId}/timeline`, {
                  time_label: timeInput.value.trim(),
                  event: eventInput.value.trim(),
                  characters: charsInput.value.trim(),
                  chapter_id: node.chapter_id || null,
                  outline_node_id: node.id,
                });
                ui.toast("剧情事件已关联", "ok");
                overlay.remove();
                reload(node.id);
              } catch (err) { ui.toast(err.message, "err"); }
            },
          }, "保存并关联"))));
    document.getElementById("modal-root").append(overlay);
    timeInput.focus();
  }

  function addForeshadowModal(node) {
    const inputCls = "w-full px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-md text-body-md";
    const labelCls = "flex flex-col gap-1 font-label-sm text-label-sm text-on-surface-variant";
    const titleInput = ui.el("input", { class: inputCls, placeholder: "伏笔标题，如：秘境石壁断剑暗纹" });
    const contentInput = ui.el("textarea", { class: inputCls + " resize-y min-h-[80px]", placeholder: "伏笔线索、埋藏地点与预定回收走向…" });

    const overlay = ui.el("div", {
      class: "fixed inset-0 z-[90] bg-ink-black/40 backdrop-blur-sm flex items-center justify-center",
      onclick: (e) => { if (e.target === overlay) overlay.remove(); },
    },
      ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-lg w-[460px] max-w-[calc(100vw-2rem)] mx-2 shadow-xl flex flex-col gap-space-md" },
        ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, "为「" + node.title + "」埋下伏笔"),
        ui.el("label", { class: labelCls }, "伏笔标题", titleInput),
        ui.el("label", { class: labelCls }, "伏笔内容与暗线规划", contentInput),
        ui.el("div", { class: "flex justify-end gap-2 pt-2" },
          ui.el("button", {
            class: "px-4 py-2 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md",
            onclick: () => overlay.remove(),
          }, "取消"),
          ui.el("button", {
            class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md",
            onclick: async () => {
              if (!titleInput.value.trim()) { ui.toast("伏笔标题不能为空", "err"); return; }
              try {
                await api.post(`/works/${workId}/foreshadows`, {
                  title: titleInput.value.trim(),
                  content: contentInput.value.trim(),
                  chapter_id: node.chapter_id || null,
                  outline_node_id: node.id,
                });
                ui.toast("伏笔已成功埋下并关联", "ok");
                overlay.remove();
                reload(node.id);
              } catch (err) { ui.toast(err.message, "err"); }
            },
          }, "埋设伏笔"))));
    document.getElementById("modal-root").append(overlay);
    titleInput.focus();
  }

  /* ---------- 数据重载 ---------- */

  async function reload(selectId) {
    [tree, volumes] = await Promise.all([
      api.get(`/works/${workId}/outline`),
      api.get(`/works/${workId}/tree`),
    ]);
    flat.length = 0;
    (function walk(nodes, depth, parent) {
      for (const n of nodes) { flat.push({ node: n, depth, parent }); walk(n.children, depth + 1, n); }
    })(tree, 0, null);
    _ol.selected[workId] = (selectId && flat.some((f) => f.node.id === selectId))
      ? selectId
      : (flat.length ? flat[0].node.id : null);
    renderTree();
    renderDetail();
  }

  renderTree();
  renderDetail();

  if (window.store && window.store.events) {
    window.store.events.onPage("outline", "plot:changed", (ev) => {
      if (ev && ev.workId === workId) reload();
    });
  }
});

/* 无 workId 时：作品选择列表 */
async function outlinePickWork(view) {
  ui.setCrumb("故事大纲");
  let works = [];
  try { works = await api.get("/works"); } catch (e) { ui.toast(e.message, "err"); }
  const list = ui.el("div", { class: "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-space-md" });
  view.append(
    ui.el("div", { class: "flex flex-col gap-space-lg" },
      ui.el("div", { class: "flex flex-col gap-1" },
        ui.el("span", { class: "font-label-sm text-label-sm text-secondary tracking-widest uppercase" }, "STORY OUTLINE · 故事大纲"),
        ui.el("h1", { class: "font-display text-display text-primary tracking-tight" }, "选择一部作品"),
        ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" }, "选择要查看 / 编辑大纲的作品。")),
      list));
  if (!works.length) {
    list.append(ui.el("div", { class: "col-span-full flex flex-col items-center gap-space-md py-space-xl text-center" },
      ui.icon("account_tree", "text-[48px] text-outline-variant"),
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
      onclick: () => { location.hash = `#/outline/${w.id}`; },
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
