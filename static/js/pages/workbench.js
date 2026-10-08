/* 阿拉伯数字 1~99 转中文数字 */
function toChineseNumber(n) {
  const nums = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"];
  if (n <= 0) return String(n);
  if (n < 10) return nums[n];
  if (n < 20) return "十" + (n % 10 ? nums[n % 10] : "");
  const tens = ["", "十", "二十", "三十", "四十", "五十", "六十", "七十", "八十", "九十"];
  return tens[Math.floor(n / 10)] + (n % 10 ? nums[n % 10] : "");
}
function chapterTitle(n) { return `第${toChineseNumber(n)}章`; }

/* 写作工作台（对应设计稿 _2）：左目录树 3 列 | 中编辑器 6 列 | 右 AI 侧栏 3 列 */
registerPage("workbench", async (view, { segs, params }) => {
  const workId = segs[0] ? Number(segs[0]) : null;
  if (!workId) return renderWorkPicker(view);

  /* ---------- 状态 ---------- */
  let work, tree;                 // 作品与目录树
  let chapter = null;             // 当前章节完整记录（含 content）
  let prevChapterText = "";       // 上一章末尾 500 字（前情摘要）
  let dirty = false, saveError = false, saveTimer = null;
  let prevWords = 0, todayAdded = 0;
  let selRange = null, selText = "";      // 编辑器内最近一次有效选区
  let abortCtrl = null, generating = false;
  let aiTask = "continue", aiLength = "2000", aiCandidates = 1;
  try {
    const savedLen = localStorage.getItem("moyu_ai_length");
    if (savedLen && /^\d+$/.test(savedLen) && Number(savedLen) > 0) aiLength = savedLen;
  } catch (_) { /* 忽略损坏的本地偏好 */ }
  // 每个任务标签各自绑定的 Skill（null=自动匹配内置技能），localStorage 持久化
  let aiSkillMap = {};
  try { aiSkillMap = JSON.parse(localStorage.getItem("moyu_task_skill_map") || "{}"); } catch (_) { aiSkillMap = {}; }
  let workbenchChatInstance = null;
  let skills = [];
  let currentTaskId = null;
  let outlineNodes = [];
  let recentInstructions = JSON.parse(localStorage.getItem("moyu_recent_instructions") || "[]");
  let taskBtns = {}, lenBtns = {}, candBtns = {};   // 分段按钮组（buildAiPanel 时赋值）
  let ctxItems = [];                                // 上下文 checkbox 项（renderContext 时填充）
  const collapsed = new Set();            // 折叠的分卷 id
  let treeStatsEl = null;                 // 目录树头部"总字数"文本节点（renderTree 时刷新）
  let dragInfo = null;                    // 拖拽中的章节 { chapterId, volId }
  let allEntities = [];                   // 当前作品全部设定条目（用于智能探测）
  let linkedEntities = [];                // 当前章节已持久化关联的设定
  let detectedEntities = [];              // 正文中智能探测到但未固定关联的设定
  let uncheckedEntityIds = new Set();     // 用户手动取消勾选的实体 id（跨刷新保持）
  let entityDetectTimer = null;           // 正文实体探测防抖定时器

  const ENTITY_CATS = {
    character: { label: "角色", icon: "person", badge: "bg-blue-50 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300" },
    place:     { label: "地点", icon: "location_on", badge: "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300" },
    faction:   { label: "势力", icon: "temple_buddhist", badge: "bg-amber-50 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300" },
    item:      { label: "物品", icon: "colorize", badge: "bg-purple-50 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300" },
    term:      { label: "术语", icon: "menu_book", badge: "bg-teal-50 text-teal-700 dark:bg-teal-900/40 dark:text-teal-300" },
    custom:    { label: "设定", icon: "bookmark", badge: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300" },
  };

  const TASK_SKILL_MAP = { condense: "shorten", polish: "rewrite", analyze: "analysis" };
  function skillIdForTask(task) {
    const id = aiSkillMap[task];
    return id ? Number(id) : null;
  }
  /* 供聊天面板技能菜单使用的桥接：列表/读取/绑定均按任务维度 */
  window.aiSkillBridge = {
    listForTask(task) {
      const skillTask = TASK_SKILL_MAP[task] || task;
      return skills.filter((s) => !s.applies_to || s.applies_to === skillTask);
    },
    get: (task) => skillIdForTask(task),
    set(task, id) {
      if (id) aiSkillMap[task] = Number(id); else delete aiSkillMap[task];
      localStorage.setItem("moyu_task_skill_map", JSON.stringify(aiSkillMap));
      if (task === aiTask) window.aiActiveSkillId = skillIdForTask(task);
    },
    syncWindow(task) { window.aiActiveSkillId = skillIdForTask(task); },
  };

  try {
    work = await api.get(`/works/${workId}`);
    tree = await api.get(`/works/${workId}/tree`);
    try { skills = await api.get("/skills", { enabled: 1 }); } catch (_) { skills = []; }
    try { outlineNodes = await api.get(`/works/${workId}/outline`); } catch (e) { outlineNodes = []; }
    try { allEntities = await api.get(`/works/${workId}/entities`); } catch (e) { allEntities = []; }
    window.aiSkillBridge.syncWindow(aiTask);
  } catch (e) {
    ui.toast(e.message, "err");
    location.hash = "#/bookshelf";
    return;
  }
    if (window.store && window.store.events) {
      window.store.events.onPage("workbench", "plot:changed", async (ev) => {
        if (!ev || !ev.workId || ev.workId === workId) {
          try { outlineNodes = await api.get(`/works/${workId}/outline`); } catch (_) {}
        }
      });
    }

  /* 作品没有任何章节时自动创建 卷一/第一章 */
  if (!tree.length) {
    const v = await api.post("/volumes", { work_id: workId, title: "卷一" });
    v.chapters = [];
    tree = [v];
  }
  if (!tree.some((v) => v.chapters.length)) {
    const vol = tree[tree.length - 1];
    const c = await api.post("/chapters", { volume_id: vol.id, title: chapterTitle(1) });
    vol.chapters.push({ id: c.id, title: c.title, status: "draft", word_count: 0 });
  }

  /* ---------- 骨架布局 ---------- */
  const treeBox = ui.el("div", { class: "flex flex-col gap-space-sm" });
  const titleInput = ui.el("input", {
    class: "w-full bg-transparent outline-none font-headline-md text-headline-md text-primary font-semibold",
    placeholder: "章节标题",
  });
  const countLine = ui.el("div", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "");
  const editor = ui.el("div", {
    class: "editor-area font-serif-content text-[17px] leading-[1.9] text-on-surface min-h-[58vh] outline-none",
    contenteditable: "true",
    spellcheck: "false",
    "data-placeholder": "开始写作…",
  });
  const findBar = buildFindBar();
  const candidatesBox = ui.el("div", { class: "flex flex-col gap-space-sm" });
  const ctxBox = ui.el("div", { class: "flex flex-col gap-1" });
  const relatedBox = ui.el("div", { class: "flex flex-col gap-1" });
  const recentBox = ui.el("div", { class: "hidden flex flex-col gap-1" });

  const taskStatusEl = ui.el("div", {
    class: "hidden bg-surface-container-lowest rounded-xl p-space-sm shadow-[0_4px_20px_rgba(6,21,35,0.03)] flex items-center gap-2 text-on-surface-variant font-label-sm text-label-sm",
  }, ui.icon("task", "text-[16px]"));
  function updateTaskStatus(id, text) {
    currentTaskId = id || currentTaskId;
    if (!currentTaskId) { taskStatusEl.classList.add("hidden"); return; }
    taskStatusEl.innerHTML = "";
    taskStatusEl.append(ui.icon("task", "text-[16px]"));
    taskStatusEl.append(ui.el("span", null, text || "任务已记录"));
    taskStatusEl.append(ui.el("a", {
      class: "ml-auto text-secondary hover:underline",
      href: "#/tasks",
      onclick: (e) => { e.preventDefault(); location.hash = "#/tasks"; },
    }, "查看任务记录"));
    taskStatusEl.classList.remove("hidden");
  }

  const instrInput = ui.el("textarea", {
    class: "w-full px-2 py-1.5 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-sm text-body-sm resize-none",
    rows: "2", placeholder: "自定义指令（可选），如：加强紧张感",
  });
  const genBtn = ui.el("button", {
    class: "w-full flex items-center justify-center gap-1 py-2 rounded-lg bg-secondary-container text-on-secondary-container font-label-md text-label-md hover:bg-secondary transition-colors",
    onclick: runGenerate,
  }, ui.icon("auto_awesome", "text-[18px]"), "生成");
  const stopBtn = ui.el("button", {
    class: "hidden w-full flex items-center justify-center gap-1 py-2 rounded-lg bg-error-container text-on-error-container font-label-md text-label-md",
    onclick: () => abortCtrl && abortCtrl.abort(),
  }, ui.icon("stop", "text-[18px]"), "停止");

  const workbenchBackdrop = ui.el("div", {
    class: "drawer-backdrop lg:hidden",
    onclick: () => closeMobileDrawers(),
  });

  function openMobileDrawer(side) {
    workbenchBackdrop.classList.add("active");
    if (side === "left") {
      leftCol.classList.remove("-translate-x-full");
      rightCol.classList.add("translate-x-full");
    } else {
      rightCol.classList.remove("translate-x-full");
      leftCol.classList.add("-translate-x-full");
    }
  }

  function closeMobileDrawers() {
    workbenchBackdrop.classList.remove("active");
    leftCol.classList.add("-translate-x-full");
    rightCol.classList.add("translate-x-full");
  }

  const leftColClose = ui.el("div", { class: "lg:hidden flex justify-between items-center pb-2 border-b border-border-feather mb-2" },
    ui.el("span", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, "卷章目录"),
    ui.el("button", {
      class: "w-8 h-8 rounded-lg flex items-center justify-center hover:bg-surface-container text-on-surface-variant cursor-pointer",
      onclick: () => closeMobileDrawers(),
    }, ui.icon("close", "text-[20px]"))
  );

  const rightColClose = ui.el("div", { class: "lg:hidden flex justify-between items-center pb-2 border-b border-border-feather mb-2" },
    ui.el("span", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, "AI 修撰使"),
    ui.el("button", {
      class: "w-8 h-8 rounded-lg flex items-center justify-center hover:bg-surface-container text-on-surface-variant cursor-pointer",
      onclick: () => closeMobileDrawers(),
    }, ui.icon("close", "text-[20px]"))
  );

  const mobileWorkbenchBar = ui.el("div", {
    class: "lg:hidden flex items-center justify-between gap-2 p-2 mb-1 bg-surface-container-lowest rounded-xl shadow-[0_2px_12px_rgba(6,21,35,0.03)] border border-border-feather"
  },
    ui.el("button", {
      class: "flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-surface-container text-on-surface font-label-md text-label-md cursor-pointer hover:bg-surface-container-high transition-colors",
      onclick: () => openMobileDrawer("left"),
    }, ui.icon("menu_book", "text-[18px]"), "卷章目录"),
    ui.el("button", {
      class: "flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-secondary-container text-on-secondary-container font-label-md text-label-md cursor-pointer hover:opacity-90 transition-opacity",
      onclick: () => openMobileDrawer("right"),
    }, ui.icon("auto_awesome", "text-[18px]"), "AI 修撰使")
  );

  const leftCol = ui.el("div", {
    class: "fixed inset-y-0 left-0 z-50 w-80 max-w-[85vw] bg-surface-container-low/95 backdrop-blur-xl p-4 shadow-2xl -translate-x-full transition-transform duration-300 overflow-y-auto lg:static lg:inset-auto lg:z-auto lg:w-auto lg:max-w-none lg:bg-transparent lg:p-0 lg:shadow-none lg:translate-x-0 lg:col-span-3 workbench-side flex flex-col gap-space-sm lg:sticky lg:top-20 lg:self-start lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto pr-1",
  }, leftColClose, treeBox);

  const centerCol = ui.el("div", { class: "col-span-12 lg:col-span-6 flex flex-col gap-space-sm min-w-0" },
    mobileWorkbenchBar,
    ui.el("div", { class: "bg-surface-container-lowest rounded-xl px-space-md sm:px-space-lg py-space-md shadow-[0_4px_20px_rgba(6,21,35,0.03)] flex flex-col gap-space-xs" },
      ui.el("div", { class: "flex items-center gap-space-sm" }, titleInput),
      countLine,
      findBar.box,
      ui.el("div", { class: "h-[1px] bg-border-feather my-1" }),
      editor));

  const rightCol = ui.el("div", {
    class: "fixed inset-y-0 right-0 z-50 w-84 max-w-[90vw] bg-surface-container-low/95 backdrop-blur-xl p-4 shadow-2xl translate-x-full transition-transform duration-300 overflow-y-auto lg:static lg:inset-auto lg:z-auto lg:w-auto lg:max-w-none lg:bg-transparent lg:p-0 lg:shadow-none lg:translate-x-0 lg:col-span-3 workbench-side flex flex-col gap-space-sm lg:sticky lg:top-20 lg:self-start lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto pr-1",
  }, rightColClose,
    buildAiPanel());

  view.append(ui.el("div", { class: "grid grid-cols-12 gap-space-lg items-start" }, leftCol, centerCol, rightCol), workbenchBackdrop);

  /* 顶栏：面包屑 + 专注模式 */
  const focusBtn = ui.el("button", {
    class: "flex items-center gap-1 px-space-sm py-1.5 rounded-full bg-surface-container hover:bg-surface-container-high text-on-surface transition-all",
    onclick: toggleFocus,
  }, ui.icon("center_focus_strong", "text-[18px]"), ui.el("span", { class: "font-label-md text-label-md" }, "专注模式"));
  ui.setActions(focusBtn);

  /* 保存失败时点击指示器重试 */
  document.getElementById("save-indicator").onclick = () => { if (saveError) saveContent(); };

  /* ---------- 编辑器事件 ---------- */
  editor.addEventListener("input", () => {
    dirty = true;
    scheduleCounts();
    if (chapter) saveLocalBackup(chapter.id, editorText());
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => saveContent(), 2000);
    clearTimeout(entityDetectTimer);
    entityDetectTimer = setTimeout(() => syncDetectedEntities(), 1200);
  });
  /* 粘贴强制纯文本 */
  editor.addEventListener("paste", (e) => {
    e.preventDefault();
    const text = (e.clipboardData || window.clipboardData).getData("text/plain");
    document.execCommand("insertText", false, text);
  });
  titleInput.addEventListener("keydown", (e) => { if (e.key === "Enter") titleInput.blur(); });
  titleInput.addEventListener("blur", renameChapter);

  /* Ctrl+F 查找替换（页面销毁后自清理） */
  function onKeydown(e) {
    if (!editor.isConnected) {
      document.removeEventListener("keydown", onKeydown, true);
      if (document.body.classList.contains("focus-mode")) toggleFocus();  // 离开页面时退出专注
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f") {
      e.preventDefault();
      findBar.toggle();
    }
    if (e.key === "Escape") {
      findBar.hide(); hideSelToolbar();
      if (document.body.classList.contains("focus-mode")) toggleFocus();
    }
  }
  document.addEventListener("keydown", onKeydown, true);

  /* 选区工具条 */
  const selToolbar = buildSelToolbar();
  document.body.append(selToolbar);
  document.addEventListener("selectionchange", onSelectionChange);

  /* 页面关闭/刷新防丢保护 */
  const onBeforeUnload = (e) => {
    if (!editor.isConnected) {
      window.removeEventListener("beforeunload", onBeforeUnload);
      return;
    }
    if (dirty) {
      if (chapter) saveLocalBackup(chapter.id, editorText());
      e.preventDefault();
      e.returnValue = "";
    }
  };
  window.addEventListener("beforeunload", onBeforeUnload);

  /* ---------- 初始加载章节 ---------- */
  const wanted = Number(params.get("chapter")) || null;
  const flat = tree.flatMap((v) => v.chapters);
  const first = (wanted && flat.find((c) => c.id === wanted)) || flat[0];
  await openChapter(first.id);

  /* ================= 函数 ================= */

  function editorText() {
    return editor.innerText.replace(/ /g, " ");
  }

  function debounce(fn, ms) {
    let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
  }

  /* ---------- 章节切换 / 保存 ---------- */

  /* 光标位置：以纯文本字符偏移量存取（contenteditable Range → offset） */
  function caretOffset() {
    const sel = window.getSelection();
    if (!sel.rangeCount || !editor.contains(sel.anchorNode)) return null;
    const r = sel.getRangeAt(0).cloneRange();
    r.selectNodeContents(editor);
    r.setEnd(sel.anchorNode, sel.anchorOffset);
    return r.toString().length;
  }

  function restoreCaret(offset) {
    if (!offset) return;
    const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT);
    let acc = 0, node;
    while ((node = walker.nextNode())) {
      if (acc + node.length >= offset) {
        const sel = window.getSelection();
        const r = document.createRange();
        r.setStart(node, Math.min(offset - acc, node.length));
        r.collapse(true);
        sel.removeAllRanges();
        sel.addRange(r);
        return;
      }
      acc += node.length + 0; /* textContent 模式下无额外换行节点 */
    }
  }

    /* ---------- 本地离线灾备暂存（防断网 / 崩溃丢稿） ---------- */
  function getLocalBackupKey(chapId) { return "moyu_backup_ch_" + chapId; }
  function saveLocalBackup(chapId, content) {
    if (!chapId) return;
    try {
      localStorage.setItem(getLocalBackupKey(chapId), JSON.stringify({
        content,
        time: Date.now(),
      }));
    } catch (_) {}
  }
  function clearLocalBackup(chapId) {
    if (!chapId) return;
    try { localStorage.removeItem(getLocalBackupKey(chapId)); } catch (_) {}
  }
  function getLocalBackup(chapId) {
    if (!chapId) return null;
    try {
      const raw = localStorage.getItem(getLocalBackupKey(chapId));
      return raw ? JSON.parse(raw) : null;
    } catch (_) { return null; }
  }

  async function openChapter(id) {
    if (chapter && chapter.id === id) return;
    clearTimeout(saveTimer);
    if (dirty && chapter) await saveContent();
    if (abortCtrl) { abortCtrl.abort(); generating = false; syncGenBtns(); }
    chapter = await api.get(`/chapters/${id}`);
    const backup = getLocalBackup(id);
    let useContent = chapter.content || "";
    if (backup && backup.content && backup.content !== useContent && (backup.time > new Date(chapter.updated_at || 0).getTime())) {
      const restore = await ui.confirm("发现离线未保存草稿", "检测到本地存有一份比数据库中更新的草稿（可能上次断网或异常关闭时保存），是否恢复？", "恢复本地草稿");
      if (restore) {
        useContent = backup.content;
        dirty = true;
        ui.toast("已恢复本地暂存草稿", "info");
      } else {
        clearLocalBackup(id);
      }
    }
    editor.textContent = useContent;
    titleInput.value = chapter.title;
    prevWords = chapter.word_count || 0;
    dirty = false; saveError = false;
    ui.setSaveIndicator(null);
    ui.setCrumb("连载作品", `《${work.title}》`, chapter.title);
    history.replaceState(null, "", `#/workbench/${workId}?chapter=${id}`);
    hideSelToolbar();
    selRange = null; selText = "";
    candidatesBox.innerHTML = "";
    await loadPrevSummary();
    renderTree();
    renderContext();
    updateCounts();
    if (workbenchChatInstance && workbenchChatInstance.loadChapter) {
      await workbenchChatInstance.loadChapter(id);
    }
    if (window.innerWidth < 1024) closeMobileDrawers();
    if (chapter.cursor_pos) restoreCaret(chapter.cursor_pos);
  }

  async function saveContent(source = "auto") {
    if (!chapter) return;
    ui.setSaveIndicator("saving");
    try {
      const caret = caretOffset();
      const updated = await api.patch(`/chapters/${chapter.id}`, {
        content: editorText(), snapshot_source: source,
        ...(caret !== null ? { cursor_pos: caret } : {}),
      });
      const delta = (updated.word_count || 0) - prevWords;
      if (delta > 0) { todayAdded += delta; }
      prevWords = updated.word_count || 0;
      chapter = updated;
      dirty = false; saveError = false;
      clearLocalBackup(chapter.id);
      ui.setSaveIndicator("saved");
      ui.refreshStats();
      updateCounts();
      syncTreeAfterSave(updated);
    } catch (e) {
      saveError = true;
      if (chapter) saveLocalBackup(chapter.id, editorText());
      ui.setSaveIndicator("error");
      ui.toast("保存失败：" + e.message + "（内容已自动暂存在本地，点击顶部状态可重试）", "err");
    }
  }

  let countsTimer = null;
  function updateCounts() {
    const wc = (editorText().match(/\S/g) || []).length;
    countLine.textContent = `本章 ${ui.fmtWords(wc)} 字 · 今日新增 +${ui.fmtWords(todayAdded)} 字`;
  }

  /* 字数统计节流：击键期间最多每 300ms 重算一次（万字长文 innerText 开销大） */
  function scheduleCounts() {
    if (countsTimer) return;
    countsTimer = setTimeout(() => { countsTimer = null; updateCounts(); }, 300);
  }

  /* 保存后的目录树最小更新：内容/字数变化在树中不可见，
     只同步本地数据与"总字数"文本，避免整树重绘；标题/状态变化走 renameChapter 等仍整树重绘 */
  function syncTreeAfterSave(updated) {
    const row = tree.flatMap((v) => v.chapters).find((c) => c.id === updated.id);
    if (!row) return;
    const visibleChange = row.title !== updated.title || row.status !== updated.status;
    row.word_count = updated.word_count || 0;
    if (visibleChange) { row.title = updated.title; row.status = updated.status; renderTree(); return; }
    if (treeStatsEl && treeStatsEl.isConnected)
      treeStatsEl.textContent = `总字数 ${ui.fmtWords(totalWords())}`;
  }

  async function renameChapter() {
    const t = titleInput.value.trim();
    if (!chapter || !t || t === chapter.title) { titleInput.value = chapter ? chapter.title : ""; return; }
    try {
      chapter = await api.patch(`/chapters/${chapter.id}`, { title: t });
      ui.setCrumb("连载作品", `《${work.title}》`, chapter.title);
      renderTree();
    } catch (e) { ui.toast(e.message, "err"); }
  }

  /* ---------- 左栏目录树 ---------- */

  function totalWords() {
    return tree.reduce((s, v) => s + v.chapters.reduce((a, c) => a + (c.word_count || 0), 0), 0);
  }

  function renderTree() {
    treeBox.innerHTML = "";
    treeBox.append(
      ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-md shadow-[0_4px_20px_rgba(6,21,35,0.03)] flex flex-col gap-space-xs" },
        ui.el("div", { class: "flex items-center gap-2" },
          ui.el("span", { class: "px-2 py-0.5 rounded-full bg-primary-fixed text-on-primary-fixed font-label-sm text-label-sm" }, work.status || "连载中"),
          (treeStatsEl = ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, `总字数 ${ui.fmtWords(totalWords())}`))),
        ui.el("h2", { class: "font-headline-sm text-headline-sm text-primary font-semibold truncate" }, `《${work.title}》`),
        ui.el("div", { class: "flex gap-2 pt-1" },
          ui.el("button", {
            class: "flex-1 flex items-center justify-center gap-1 py-1.5 rounded-lg bg-primary text-on-primary font-label-md text-label-md hover:bg-primary-container transition-colors",
            onclick: () => newChapter(),
          }, ui.icon("add", "text-[16px]"), "新建章节"),
          ui.el("button", {
            class: "flex-1 flex items-center justify-center gap-1 py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md transition-colors",
            onclick: newVolume,
          }, ui.icon("create_new_folder", "text-[16px]"), "新建分卷"))));

    for (const vol of tree) {
      const isCollapsed = collapsed.has(vol.id);
      const chapList = ui.el("div", { class: "flex flex-col gap-0.5 mt-1" });
      if (!isCollapsed) {
        for (const c of vol.chapters) chapList.append(chapterRow(vol, c));
        if (!vol.chapters.length)
          chapList.append(ui.el("div", { class: "px-space-sm py-1 font-label-sm text-label-sm text-on-surface-variant" }, "暂无章节"));
      }
      const volHead = ui.el("div", { class: "group flex items-center gap-1 px-1 py-1 rounded-lg hover:bg-surface-container-low cursor-pointer",
        "data-vol-head": String(vol.id),
        onclick: () => { isCollapsed ? collapsed.delete(vol.id) : collapsed.add(vol.id); renderTree(); },
      },
        ui.icon(isCollapsed ? "chevron_right" : "expand_more", "text-[18px] text-on-surface-variant"),
        ui.el("span", { class: "flex-1 font-body-sm text-body-sm text-on-surface font-medium truncate" }, vol.title),
        iconBtn("add", "本卷新建章节", async (e) => { e.stopPropagation(); await newChapter(vol); }),
        iconBtn("edit", "重命名分卷", async (e) => {
          e.stopPropagation();
          const t = await ui.prompt("重命名分卷", "分卷名", vol.title);
          if (!t) return;
          await api.patch(`/volumes/${vol.id}`, { title: t });
          vol.title = t;
          renderTree();
        }),
        iconBtn("delete", "删除分卷", async (e) => {
          e.stopPropagation();
          const ok = await ui.confirm("删除分卷",
            `将删除分卷「${vol.title}」及其下 ${vol.chapters.length} 个章节与全部版本快照，且不可恢复。确定继续？`, "删除", true);
          if (!ok) return;
          await api.del(`/volumes/${vol.id}`);
          tree = tree.filter((v) => v.id !== vol.id);
          if (chapter && !tree.some((v) => v.chapters.some((c) => c.id === chapter.id))) {
            chapter = null;
            await ensureAnyChapter();
            await openChapter(tree.flatMap((v) => v.chapters)[0].id);
          }
          renderTree();
        }));
      /* 卷头 / 卷区域作为跨卷投放目标：松开即移动到该卷末尾 */
      for (const target of [volHead, chapList]) {
        target.addEventListener("dragover", (e) => {
          if (!dragInfo) return;
          e.preventDefault();
          e.dataTransfer.dropEffect = "move";
          clearDropMarks();
          volHead.classList.add("bg-secondary-fixed");
        });
        target.addEventListener("drop", (e) => {
          if (!dragInfo) return;
          e.preventDefault();
          handleDrop(vol, null, false);
        });
      }
      treeBox.append(ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-sm shadow-[0_4px_20px_rgba(6,21,35,0.03)]" },
        volHead,
        chapList));
    }
  }

  function clearDropMarks() {
    treeBox.querySelectorAll("[data-chap-row]").forEach((n) => { n.style.boxShadow = ""; });
    treeBox.querySelectorAll("[data-vol-head]").forEach((n) => n.classList.remove("bg-secondary-fixed"));
  }

  /* 拖拽落点处理：targetChapter 为 null 表示投到 targetVol 末尾 */
  async function handleDrop(targetVol, targetChapter, before) {
    const info = dragInfo;
    if (!info) return;
    const srcVol = tree.find((v) => v.id === info.volId);
    const item = srcVol && srcVol.chapters.find((c) => c.id === info.chapterId);
    if (!item) return;
    const sameVol = srcVol.id === targetVol.id;
    const list = targetVol.chapters.filter((c) => c.id !== info.chapterId);
    let idx = targetChapter ? list.findIndex((c) => c.id === targetChapter.id) : list.length;
    if (idx < 0) idx = list.length;
    if (targetChapter && !before) idx += 1;
    list.splice(idx, 0, item);
    /* 同卷且顺序未变：直接跳过 */
    if (sameVol && list.every((c, i) => srcVol.chapters[i] && srcVol.chapters[i].id === c.id)) return;
    try {
      if (!sameVol) await api.post(`/chapters/${item.id}/move`, { volume_id: targetVol.id, sort_order: idx + 1 });
      for (let i = 0; i < list.length; i++)
        await api.patch(`/chapters/${list[i].id}`, { sort_order: i + 1 });
      tree = await api.get(`/works/${workId}/tree`);
      renderTree();
      ui.toast(sameVol ? "章节顺序已更新" : `已移动到「${targetVol.title}」`, "ok");
    } catch (e) {
      ui.toast("拖拽排序失败：" + e.message, "err");
      try { tree = await api.get(`/works/${workId}/tree`); renderTree(); } catch (_) { /* 忽略 */ }
    }
  }

  function chapterRow(vol, c) {
    const active = chapter && chapter.id === c.id;
    const row = ui.el("div", {
      class: `group flex items-center gap-1 pl-7 pr-1 py-1.5 rounded-lg cursor-pointer transition-colors ${
        active ? "bg-primary-fixed text-on-primary-fixed font-medium" : "hover:bg-surface-container-low text-on-surface-variant"}`,
      draggable: "true",
      "data-chap-row": String(c.id),
      onclick: () => openChapter(c.id),
    },
      ui.el("span", { class: "flex-1 font-body-sm text-body-sm truncate" }, c.title),
      ui.el("span", {
        class: `px-1.5 py-0.5 rounded-full font-label-sm text-label-sm ${
          c.status === "done" ? "bg-primary-fixed text-on-primary-fixed" : "bg-surface-container-high text-on-surface-variant"}`,
      }, c.status === "done" ? "已完成" : "草稿"),
      iconBtn("edit", "重命名章节", async (e) => {
        e.stopPropagation();
        const t = await ui.prompt("重命名章节", "章节名", c.title);
        if (!t) return;
        await api.patch(`/chapters/${c.id}`, { title: t });
        c.title = t;
        if (active) { chapter.title = t; titleInput.value = t; ui.setCrumb("连载作品", `《${work.title}》`, t); }
        renderTree();
      }),
      iconBtn("delete", "删除章节", async (e) => {
        e.stopPropagation();
        let bindMsg = "";
        try {
          const impact = await api.get(`/chapters/${c.id}/delete-impact`);
          if (impact && impact.total > 0) {
            bindMsg = `，将解除 ${impact.total} 条绑定`;
          }
        } catch (_) {}
        const ok = await ui.confirm("删除章节", `将删除章节「${c.title}」及其全部版本快照${bindMsg}，且不可恢复。确定继续？`, "删除", true);
        if (!ok) return;
        await api.del(`/chapters/${c.id}`);
        vol.chapters = vol.chapters.filter((x) => x.id !== c.id);
        if (active) {
          chapter = null;
          await ensureAnyChapter();
          await openChapter(tree.flatMap((v) => v.chapters)[0].id);
        }
        renderTree();
      }));
    /* HTML5 拖拽排序 */
    row.addEventListener("dragstart", (e) => {
      dragInfo = { chapterId: c.id, volId: vol.id };
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", String(c.id));
      row.classList.add("opacity-40");
    });
    row.addEventListener("dragend", () => {
      dragInfo = null;
      row.classList.remove("opacity-40");
      clearDropMarks();
    });
    row.addEventListener("dragover", (e) => {
      if (!dragInfo || dragInfo.chapterId === c.id) return;
      e.preventDefault();
      e.stopPropagation();
      e.dataTransfer.dropEffect = "move";
      const r = row.getBoundingClientRect();
      clearDropMarks();
      row.style.boxShadow = e.clientY < r.top + r.height / 2
        ? "inset 0 2px 0 0 #316bf3" : "inset 0 -2px 0 0 #316bf3";
    });
    row.addEventListener("drop", (e) => {
      if (!dragInfo || dragInfo.chapterId === c.id) return;
      e.preventDefault();
      e.stopPropagation();
      const r = row.getBoundingClientRect();
      handleDrop(vol, c, e.clientY < r.top + r.height / 2);
    });
    return row;
  }

  /* 删除后保证仍存在至少一卷一章 */
  async function ensureAnyChapter() {
    if (!tree.length) {
      const v = await api.post("/volumes", { work_id: workId, title: "卷一" });
      v.chapters = [];
      tree = [v];
    }
    if (!tree.some((v) => v.chapters.length)) {
      const vol = tree[tree.length - 1];
      const c = await api.post("/chapters", { volume_id: vol.id, title: chapterTitle(1) });
      vol.chapters.push({ id: c.id, title: c.title, status: "draft", word_count: 0 });
    }
  }

  async function newVolume() {
    const t = await ui.prompt("新建分卷", "分卷名", `卷${tree.length + 1}`);
    if (!t) return;
    const v = await api.post("/volumes", { work_id: workId, title: t });
    v.chapters = [];
    tree.push(v);
    renderTree();
  }

  async function newChapter(vol) {
    vol = vol || tree[tree.length - 1];
    if (!vol) return;
    const c = await api.post("/chapters", { volume_id: vol.id, title: chapterTitle(vol.chapters.length + 1) });
    vol.chapters.push({ id: c.id, title: c.title, status: c.status, word_count: 0 });
    collapsed.delete(vol.id);
    await openChapter(c.id);
  }

  function iconBtn(name, title, onclick) {
    return ui.el("button", {
      class: "flex lg:hidden lg:group-hover:flex p-1.5 min-w-[32px] min-h-[32px] items-center justify-center rounded text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high cursor-pointer",
      title, onclick,
    }, ui.icon(name, "text-[15px]"));
  }

  /* ---------- 查找替换 ---------- */

  function buildFindBar() {
    const findInput = ui.el("input", {
      class: "w-28 sm:w-36 px-2 py-1 rounded-lg bg-surface-container-low border border-border-feather outline-none font-body-sm text-[16px] sm:text-body-sm flex-1 sm:flex-initial",
      placeholder: "查找",
    });
    const repInput = ui.el("input", {
      class: "w-28 sm:w-36 px-2 py-1 rounded-lg bg-surface-container-low border border-border-feather outline-none font-body-sm text-[16px] sm:text-body-sm flex-1 sm:flex-initial",
      placeholder: "替换为",
    });
    const countEl = ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant w-14 text-center" }, "");
    const box = ui.el("div", {
      class: "hidden flex-wrap items-center gap-2 py-1 px-2 rounded-lg bg-surface-container-low border border-border-feather",
    },
      ui.icon("search", "text-[16px] text-on-surface-variant"), findInput, countEl,
      smallBtn("下一个", () => jump(findInput.value)),
      repInput,
      smallBtn("全部替换", () => replaceAll(findInput.value, repInput.value)),
      smallBtn("关闭", () => api_hide()));
    findInput.addEventListener("input", () => showCount(findInput.value));
    findInput.addEventListener("keydown", (e) => { if (e.key === "Enter") jump(findInput.value); });

    function smallBtn(label, onclick) {
      return ui.el("button", {
        class: "px-2 py-1 rounded-md bg-surface-container hover:bg-surface-container-high font-label-sm text-label-sm whitespace-nowrap",
        onclick,
      }, label);
    }
    function matches(q) {
      if (!q) return [];
      const out = [];
      const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walker.nextNode())) {
        let i = node.data.indexOf(q);
        while (i >= 0) { out.push({ node, offset: i }); i = node.data.indexOf(q, i + q.length); }
      }
      return out;
    }
    function showCount(q) {
      const n = matches(q).length;
      countEl.textContent = q ? `${n} 处` : "";
    }
    function jump(q) {
      const ms = matches(q);
      if (!ms.length) { showCount(q); return; }
      const sel = window.getSelection();
      let idx = 0;
      if (sel.rangeCount && editor.contains(sel.anchorNode)) {
        const cur = { node: sel.anchorNode, offset: sel.anchorOffset };
        idx = ms.findIndex((m) =>
          m.node === cur.node ? m.offset >= cur.offset : m.node.compareDocumentPosition(cur.node) & Node.DOCUMENT_POSITION_PRECEDING);
        if (idx < 0) idx = 0;
      }
      const m = ms[idx];
      const r = document.createRange();
      r.setStart(m.node, m.offset);
      r.setEnd(m.node, m.offset + q.length);
      sel.removeAllRanges(); sel.addRange(r);
      countEl.textContent = `${idx + 1} / ${ms.length}`;
    }
    function replaceAll(q, rep) {
      if (!q) return;
      const text = editorText();
      const n = text.split(q).length - 1;
      if (!n) { showCount(q); return; }
      editor.textContent = text.split(q).join(rep);
      dirty = true;
      editor.dispatchEvent(new Event("input"));
      ui.toast(`已替换 ${n} 处`, "ok");
      showCount(q);
    }
    function api_hide() { box.classList.add("hidden"); box.classList.remove("flex"); }
    return {
      box,
      toggle() {
        const show = box.classList.contains("hidden");
        box.classList.toggle("hidden", !show);
        box.classList.toggle("flex", show);
        if (show) { findInput.focus(); findInput.select(); }
      },
      hide: api_hide,
    };
  }

  /* ---------- 选区工具条 ---------- */

  function buildSelToolbar() {
    const bar = ui.el("div", {
      class: "hidden fixed z-[80] items-center gap-1 px-2 py-1.5 rounded-xl bg-primary text-on-primary shadow-[0_8px_24px_rgba(6,21,35,0.3)]",
    });
    for (const [task, label] of [["continue", "续写"], ["expand", "扩写"], ["condense", "缩写"], ["polish", "改写"]]) {
      bar.append(ui.el("button", {
        class: "px-2 py-1 rounded-lg hover:bg-primary-container font-label-sm text-label-sm",
        onclick: () => {
          aiTask = task;
          syncTaskBtns();
          hideSelToolbar();
          if (window.innerWidth < 1024) openMobileDrawer("right");
          if (workbenchChatInstance) {
            workbenchChatInstance.setActiveTask(task);
            workbenchChatInstance.sendQuickTask(task, selText);
          } else {
            runGenerate();
          }
        },
      }, label));
    }
    return bar;
  }

  function hideSelToolbar() {
    selToolbar.classList.add("hidden");
    selToolbar.classList.remove("flex");
  }

  const onSelChange = debounce(() => {
    if (!editor.isConnected) { document.removeEventListener("selectionchange", onSelectionChange); selToolbar.remove(); return; }
    const sel = window.getSelection();
    if (!sel.rangeCount || sel.isCollapsed) { hideSelToolbar(); return; }
    const range = sel.getRangeAt(0);
    if (!editor.contains(range.commonAncestorContainer)) { hideSelToolbar(); return; }
    const text = range.toString();
    if (!text.trim()) { hideSelToolbar(); return; }
    selRange = range.cloneRange();
    selText = text;
    if (workbenchChatInstance && workbenchChatInstance.updateSelectionQuote) {
      workbenchChatInstance.updateSelectionQuote();
    }
    const rect = range.getBoundingClientRect();
    selToolbar.style.left = Math.max(8, rect.left + rect.width / 2 - 120) + "px";
    selToolbar.style.top = Math.max(8, rect.top - 48) + "px";
    selToolbar.classList.remove("hidden");
    selToolbar.classList.add("flex");
  }, 200);
  function onSelectionChange() { onSelChange(); }

  /* ---------- 专注模式 ---------- */

  let focusExitBtn = null;
  function toggleFocus() {
    const on = document.body.classList.toggle("focus-mode");
    centerCol.classList.toggle("lg:col-span-6", !on);
    centerCol.classList.toggle("max-w-3xl", on);
    centerCol.classList.toggle("mx-auto", on);
    hideSelToolbar();
    if (window.innerWidth < 1024) closeMobileDrawers();
    /* 专注模式下顶栏被隐藏，提供浮动退出按钮 */
    if (on && !focusExitBtn) {
      focusExitBtn = ui.el("button", {
        class: "fixed top-4 right-4 z-[70] flex items-center gap-1 px-space-sm py-1.5 rounded-full bg-primary text-on-primary shadow-lg font-label-md text-label-md cursor-pointer",
        onclick: toggleFocus,
      }, ui.icon("close_fullscreen", "text-[18px]"), "退出专注 (Esc)");
      document.body.append(focusExitBtn);
    } else if (!on && focusExitBtn) {
      focusExitBtn.remove();
      focusExitBtn = null;
    }
  }

  /* ---------- AI 侧栏 ---------- */

  function seg(options, current, onPick) {
    const wrap = ui.el("div", { class: "flex gap-1 p-0.5 rounded-lg bg-surface-container" });
    const btns = {};
    for (const [val, label] of options) {
      btns[val] = ui.el("button", {
        class: "flex-1 px-1 py-1 rounded-md font-label-sm text-label-sm transition-colors",
        onclick: () => { onPick(val); sync(); },
      }, label);
      wrap.append(btns[val]);
    }
    function sync() {
      for (const [val, b] of Object.entries(btns)) {
        const on = String(val) === String(current());
        b.classList.toggle("bg-surface-container-lowest", on);
        b.classList.toggle("text-primary", on);
        b.classList.toggle("font-semibold", on);
        b.classList.toggle("text-on-surface-variant", !on);
      }
    }
    sync();
    return { wrap, sync };
  }





  function findCurrentOutlineNode() {
    const flat = [];
    (function walk(nodes) {
      for (const n of nodes) { flat.push(n); walk(n.children || []); }
    })(outlineNodes);
    return flat.find((n) => n.chapter_id === chapter.id) || null;
  }

  function saveRecentInstruction(text) {
    if (!text) return;
    recentInstructions = [text, ...recentInstructions.filter((t) => t !== text)].slice(0, 5);
    localStorage.setItem("moyu_recent_instructions", JSON.stringify(recentInstructions));
    renderRecentInstructions();
  }

  function renderRecentInstructions() {
    recentBox.innerHTML = "";
    recentBox.classList.toggle("hidden", !recentInstructions.length);
    if (!recentInstructions.length) return;
    recentBox.append(ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "最近指令"));
    for (const t of recentInstructions) {
      recentBox.append(ui.el("button", {
        class: "px-2 py-1 rounded-lg bg-surface-container-low hover:bg-surface-container text-on-surface-variant font-body-sm text-body-sm truncate max-w-full",
        title: t,
        onclick: () => { instrInput.value = t; },
      }, t));
    }
  }


  async function applyAdoptContent(text, msgId = null) {
    if (!text || !chapter) return { ok: false };
    const old = editorText();
    const useRange = rangeAlive();
    if (useRange) {
      const ok = await ui.confirm("采纳 AI 内容", "将用 AI 生成的内容替换当前选中的正文（替换前会自动留存一份版本快照）。", "替换");
      if (!ok) return { ok: false };
    }
    try {
      await api.patch(`/chapters/${chapter.id}`, {
        content: old,
        snapshot_source: "auto",
        snapshot_label: "采纳前自动留存"
      });
    } catch (e) {
      console.warn("采纳前自动快照留存失败:", e);
    }

    if (useRange) {
      selRange.deleteContents();
      selRange.insertNode(document.createTextNode(text));
      selRange = null; selText = "";
      hideSelToolbar();
    } else {
      editor.textContent = old ? old.replace(/\s+$/, "") + "\n\n" + text : text;
    }
    dirty = true;
    await saveContent("ai");

    if (msgId) {
      try {
        await api.patch(`/chat/messages/${msgId}`, { adopted: 1 });
      } catch (e) {
        console.warn("更新消息采纳状态失败:", e);
      }
    }

    ui.toast("已采纳并写入正文", "ok");
    return { ok: true, oldContent: old };
  }

  async function applyUndoAdopt(oldContent, msgId = null) {
    if (!chapter || oldContent === undefined) return;
    const ok = await ui.confirm("撤销采纳", "将正文恢复到采纳前的内容。", "撤销");
    if (!ok) return;
    editor.textContent = oldContent;
    dirty = true;
    await saveContent("ai");
    if (msgId) {
      try {
        await api.patch(`/chat/messages/${msgId}`, { adopted: 0 });
      } catch (e) {
        console.warn("更新消息撤销状态失败:", e);
      }
    }
    ui.toast("已撤销采纳", "ok");
  }

  function buildAiPanel() {
    window.aiLengthPreference = aiLength;
    window.aiActiveSkillId = skillIdForTask(aiTask);

    const taskSeg = seg([["continue", "续写"], ["expand", "扩写"], ["condense", "缩写"], ["polish", "改写"], ["analyze", "分析"]],
      () => aiTask, (v) => {
        aiTask = v;
        window.aiSkillBridge.syncWindow(v);
        if (workbenchChatInstance) workbenchChatInstance.setActiveTask(v);
      });
    taskBtns = taskSeg;

    const lenCustomInput = ui.el("input", {
      type: "number", min: "100", max: "20000", step: "100",
      class: "w-24 px-2 py-1 rounded-lg bg-surface-container text-on-surface font-label-sm text-label-sm outline-none focus:ring-1 focus:ring-primary",
      placeholder: "自定义字数",
      title: "自定义生成长度（100~20000 字），输入后自动生效",
    });
    const lenSeg = seg([["1000", "1000字"], ["2000", "2000字"], ["3000", "3000字"]],
      () => aiLength, (v) => {
        aiLength = v;
        window.aiLengthPreference = v;
        lenCustomInput.value = "";
        try { localStorage.setItem("moyu_ai_length", v); } catch (_) {}
      });
    lenBtns = lenSeg;
    lenCustomInput.addEventListener("input", () => {
      const n = parseInt(lenCustomInput.value, 10);
      if (Number.isFinite(n) && n > 0) {
        aiLength = String(n);
        window.aiLengthPreference = aiLength;
        try { localStorage.setItem("moyu_ai_length", aiLength); } catch (_) {}
        lenSeg.sync();
      }
    });
    if (!["1000", "2000", "3000"].includes(aiLength)) lenCustomInput.value = aiLength;

    const candSeg = seg([[1, "1"], [2, "2"], [3, "3"]],
      () => aiCandidates, (v) => { aiCandidates = v; });
    candBtns = candSeg;

    /* 长度/候选：单一实例，随聊天/经典模式在抽屉与经典面板之间搬移挂载（写作技能已迁移至任务标签旁菜单，按任务绑定） */
    const settingsBlock = ui.el("div", { class: "flex flex-col gap-2" },
      ui.el("div", { class: "flex items-center gap-space-sm" },
        ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant shrink-0" }, "长度"), lenSeg.wrap, lenCustomInput),
      ui.el("div", { class: "flex items-center gap-space-sm" },
        ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant shrink-0" }, "候选"), candSeg.wrap),
      ui.el("div", { class: "flex items-center justify-between" },
        ui.el("span", { class: "text-[11px] text-on-surface-variant" }, "技能在输入框上方任务标签右侧按任务选择"),
        ui.el("a", { class: "text-[11px] text-primary hover:underline cursor-pointer", href: "#/skills", onclick: (e) => { e.preventDefault(); location.hash = "#/skills"; } }, "管理技能 →")));
    const drawerContextBox = ui.el("div", { class: "flex flex-col gap-2" },
      ctxBox,
      relatedBox,
      ui.el("div", { class: "flex flex-wrap gap-1 pt-2 border-t border-border-feather/50" },
        ui.el("a", { class: "px-2 py-1 rounded-lg bg-surface-container-low hover:bg-surface-container text-on-surface-variant font-label-sm text-label-sm", href: `#/outline/${workId}`, onclick: (e) => { e.preventDefault(); location.hash = `#/outline/${workId}`; } }, "故事大纲"),
        ui.el("a", { class: "px-2 py-1 rounded-lg bg-surface-container-low hover:bg-surface-container text-on-surface-variant font-label-sm text-label-sm", href: `#/entities/${workId}`, onclick: (e) => { e.preventDefault(); location.hash = `#/entities/${workId}`; } }, "设定库"),
        ui.el("a", { class: "px-2 py-1 rounded-lg bg-surface-container-low hover:bg-surface-container text-on-surface-variant font-label-sm text-label-sm", href: `#/versions/${workId}`, onclick: (e) => { e.preventDefault(); location.hash = chapter ? `#/versions/${workId}?chapter=${chapter.id}` : `#/versions/${workId}`; } }, "版本快照"),
        ui.el("a", { class: "px-2 py-1 rounded-lg bg-surface-container-low hover:bg-surface-container text-on-surface-variant font-label-sm text-label-sm", href: "#/audit", onclick: (e) => { e.preventDefault(); location.hash = "#/audit"; } }, "一致性检查"))
    );

    if (window.WorkbenchChat) {
      workbenchChatInstance = window.WorkbenchChat.init({
        workId,
        getChapter: () => chapter,
        getSelection: () => ({ text: selText, range: selRange }),
        clearSelection: () => { selRange = null; selText = ""; hideSelToolbar(); },
        getContext: () => ctxItems.filter((i) => i.cb.checked).map((i) => i.getText()).filter(Boolean).join("\n\n----\n\n"),
        getContextCount: () => ctxItems.filter((i) => i.cb.checked).length,
        contextDrawerEl: drawerContextBox,
        onAdopt: async (msg, text) => {
          const res = await applyAdoptContent(text, msg ? msg.id : null);
          if (res && res.ok) {
            msg._oldContent = res.oldContent;
            return true;
          }
          return false;
        },
        onUndoAdopt: async (msg) => {
          await applyUndoAdopt(msg ? msg._oldContent : undefined, msg ? msg.id : null);
        },
        onRetry: (task) => {
          aiTask = task;
          if (window.aiSkillBridge) window.aiSkillBridge.syncWindow(task);
          syncTaskBtns();
          workbenchChatInstance.setActiveTask(task);
          workbenchChatInstance.sendQuickTask(task, selText);
        },
      });
    }

    const panelWrapper = ui.el("div", {
      class: "flex flex-col gap-space-sm h-full min-h-0",
    }, workbenchChatInstance ? workbenchChatInstance.el : null);
    return panelWrapper;
  }

  function syncTaskBtns() { taskBtns.sync && taskBtns.sync(); }
  function syncGenBtns() {
    genBtn.classList.toggle("hidden", generating);
    stopBtn.classList.toggle("hidden", !generating);
  }

  /* ---------- 实体上下文联动 ---------- */

  function formatEntityContext(e) {
    const meta = ENTITY_CATS[e.category] || ENTITY_CATS.custom;
    const lines = [`【${meta.label}设定 · ${e.name}】`];
    if (e.tags) lines.push(`标签：${e.tags}`);
    if (e.fields && typeof e.fields === "object") {
      const fl = [];
      for (const [k, v] of Object.entries(e.fields)) {
        if (v && typeof v === "string" && v.trim()) fl.push(`- ${k}：${v.trim()}`);
      }
      if (fl.length) lines.push("关键属性：\n" + fl.join("\n"));
    }
    if (e.content && e.content.trim()) lines.push(`设定描述：\n${e.content.trim()}`);
    return lines.join("\n");
  }

  function detectEntitiesInContent(text) {
    if (!text || !allEntities.length) return [];
    const found = [];
    for (const ent of allEntities) {
      if (!ent.name || ent.name.length < 2) continue;
      if (text.includes(ent.name)) { found.push(ent); continue; }
      if (ent.tags) {
        const tags = ent.tags.split(/[,，\s]+/).filter((t) => t.length >= 2);
        if (tags.some((t) => text.includes(t))) found.push(ent);
      }
    }
    return found;
  }

  function syncDetectedEntities() {
    if (!chapter) return;
    const text = editorText();
    const linkedIds = new Set(linkedEntities.map((e) => e.id));
    const oldIds = new Set(detectedEntities.map((e) => e.id));
    const newDetected = detectEntitiesInContent(text).filter((e) => !linkedIds.has(e.id));
    const newIds = new Set(newDetected.map((e) => e.id));
    if (newIds.size !== oldIds.size || [...newIds].some((id) => !oldIds.has(id))) {
      detectedEntities = newDetected;
      renderContext();
    }
  }

  async function loadPrevSummary() {
    prevChapterText = "";
    const flatIds = tree.flatMap((v) => v.chapters.map((c) => c.id));
    const idx = flatIds.indexOf(chapter.id);
    if (idx > 0) {
      try {
        const prev = await api.get(`/chapters/${flatIds[idx - 1]}`);
        prevChapterText = (prev.content || "").slice(-500);
      } catch (e) { /* 忽略 */ }
    }
  }

  function ctxRow(label, checked) {
    const cb = ui.el("input", { type: "checkbox", class: "accent-[#316bf3]" });
    cb.checked = checked;
    return {
      cb,
      row: ui.el("label", { class: "flex items-center gap-2 px-1 py-1 rounded-lg hover:bg-surface-container-low cursor-pointer" },
        cb, ui.el("span", { class: "font-body-sm text-body-sm text-on-surface-variant truncate" }, label)),
    };
  }

  async function renderContext() {
    ctxBox.innerHTML = "";
    ctxItems = [];

    /* ---- 基础上下文组 ---- */
    const baseGroup = ui.el("div", { class: "flex flex-col gap-0.5 pb-2 border-b border-border-feather" });

    const cur = ctxRow("当前章节（前 3000 字）", true);
    cur.getText = () => editorText().slice(0, 3000);
    ctxItems.push(cur);
    baseGroup.append(cur.row);

    if (prevChapterText) {
      const prev = ctxRow("前情摘要（上一章末 500 字）", true);
      prev.getText = () => prevChapterText;
      ctxItems.push(prev);
      baseGroup.append(prev.row);
    }

    const node = findCurrentOutlineNode();
    if (node && (node.title || node.synopsis)) {
      const preview = node.synopsis ? `（${node.synopsis.replace(/\s+/g, " ").slice(0, 20)}…）` : "";
      const outRow = ctxRow(`大纲 · ${node.title}${preview}`, true);
      outRow.getText = () => `【关联大纲 · ${node.title}】\n${node.synopsis || "（本节暂无细纲）"}`;
      ctxItems.push(outRow);
      baseGroup.append(outRow.row);

      // 三位一体深度联动：自动加载当前大纲节点关联的时间线事件与伏笔
      try {
        const plotData = await api.get(`/works/${workId}/outline/nodes/${node.id}/plot-items`);
        if (plotData) {
          if (Array.isArray(plotData.timeline_events) && plotData.timeline_events.length > 0) {
            plotData.timeline_events.forEach((ev) => {
              const tLabel = ev.time_label ? `[${ev.time_label}] ` : "";
              const evRow = ctxRow(`事件 · ${tLabel}${ev.event}`, true);
              evRow.getText = () => `【时间线事件】${tLabel}${ev.event}${ev.characters ? ` (涉及人物: ${ev.characters})` : ""}`;
              ctxItems.push(evRow);
              baseGroup.append(evRow.row);
            });
          }
          if (Array.isArray(plotData.foreshadows) && plotData.foreshadows.length > 0) {
            plotData.foreshadows.forEach((fs) => {
              const st = fs.status === "resolved" ? "已回收" : "埋设中";
              const fsRow = ctxRow(`伏笔 · 《${fs.title}》（${st}）`, true);
              fsRow.getText = () => `【关联伏笔】《${fs.title}》（${st}）${fs.content ? `：${fs.content}` : ""}`;
              ctxItems.push(fsRow);
              baseGroup.append(fsRow.row);
            });
          }
        }
      } catch (_) {}
    }
    ctxBox.append(baseGroup);

    /* ---- 设定库联动组 ---- */
    const entitySection = ui.el("div", { class: "flex flex-col gap-1.5 pt-1.5" });
    const countBadge = ui.el("span", {
      class: "text-[11px] px-1.5 rounded-full bg-surface-container text-on-surface-variant font-label-sm leading-[18px]",
    }, "0项");

    const detectBtn = ui.el("button", {
      class: "flex items-center gap-0.5 px-1.5 py-0.5 rounded-md hover:bg-surface-container text-secondary text-[12px] font-label-sm transition-colors",
      title: "扫描正文，智能识别提及的人物、地点与设定",
      onclick: () => runSmartDetect(),
    }, ui.icon("troubleshoot", "text-[14px]"), "识别");

    const addEntityBtn = ui.el("button", {
      class: "flex items-center gap-0.5 px-1.5 py-0.5 rounded-md bg-primary-container text-on-primary text-[12px] font-label-sm hover:opacity-90 transition-opacity",
      title: "从全书设定库挑选条目关联到本章",
      onclick: () => openEntityPickerDialog(),
    }, ui.icon("add", "text-[14px]"), "关联");

    const entityHeader = ui.el("div", { class: "flex items-center justify-between" },
      ui.el("div", { class: "flex items-center gap-1.5" },
        ui.icon("psychology", "text-[16px] text-primary"),
        ui.el("span", { class: "font-label-sm text-label-sm font-semibold text-primary" }, "设定库联动"),
        countBadge),
      ui.el("div", { class: "flex items-center gap-0.5" }, detectBtn, addEntityBtn));

    const entityListEl = ui.el("div", { class: "flex flex-col gap-0.5 max-h-[220px] overflow-y-auto" });
    entitySection.append(entityHeader, entityListEl);
    ctxBox.append(entitySection);

    await refreshEntityList(entityListEl, countBadge);
    renderRelated();
    if (workbenchChatInstance && workbenchChatInstance.updateContextCount) {
      workbenchChatInstance.updateContextCount();
    }
  }

  async function refreshEntityList(container, countBadge) {
    if (!container) return;
    container.innerHTML = "";
    if (!chapter) return;

    try { linkedEntities = await api.get(`/chapters/${chapter.id}/entities`); }
    catch (e) { linkedEntities = []; }

    const linkedIds = new Set(linkedEntities.map((e) => e.id));
    const text = editorText();
    detectedEntities = detectEntitiesInContent(text).filter((e) => !linkedIds.has(e.id));

    const allToShow = [
      ...linkedEntities.map((e) => ({ entity: e, isLinked: true })),
      ...detectedEntities.map((e) => ({ entity: e, isLinked: false })),
    ];

    function updateBadge() {
      const active = allToShow.filter((it) => it.ctxEntry && it.ctxEntry.cb.checked).length;
      if (countBadge) countBadge.textContent = `${active}/${allToShow.length}项`;
    }

    if (!allToShow.length) {
      container.append(ui.el("div", {
        class: "py-2 px-1 rounded-lg text-center text-on-surface-variant text-[12px] flex flex-col items-center gap-1",
      },
        ui.el("span", null, "暂无挂载设定"),
        ui.el("span", { class: "text-[11px] text-outline" }, "可点击「关联」或「识别」")));
      updateBadge();
      return;
    }

    for (const item of allToShow) {
      const ent = item.entity;
      const isLinked = item.isLinked;
      const meta = ENTITY_CATS[ent.category] || ENTITY_CATS.custom;

      const cb = ui.el("input", { type: "checkbox", class: "accent-[#316bf3] shrink-0" });
      cb.checked = !uncheckedEntityIds.has(ent.id);
      cb.addEventListener("change", () => {
        if (cb.checked) uncheckedEntityIds.delete(ent.id);
        else uncheckedEntityIds.add(ent.id);
        updateBadge();
      });

      const ctxEntry = { cb, getText: () => formatEntityContext(ent) };
      item.ctxEntry = ctxEntry;
      ctxItems.push(ctxEntry);

      const catIcon = ui.el("span", {
        class: `inline-flex items-center justify-center w-5 h-5 rounded text-[12px] shrink-0 ${meta.badge}`,
        title: meta.label,
      }, ui.icon(meta.icon, "text-[12px]"));

      const nameEl = ui.el("span", {
        class: "font-body-sm text-body-sm text-on-surface truncate flex-1 cursor-pointer hover:text-secondary",
        title: `${ent.name}${ent.tags ? ` · ${ent.tags}` : ""}\n点击查看设定详情`,
        onclick: (ev) => { ev.preventDefault(); openEntityPreviewDialog(ent); },
      }, ent.name);

      const statusTag = isLinked
        ? ui.el("span", { class: "text-[10px] px-1 rounded bg-surface-container text-on-surface-variant shrink-0" }, "已绑定")
        : ui.el("span", { class: "text-[10px] px-1 rounded bg-amber-50 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300 shrink-0" }, "正文提及");

      const actionBtn = isLinked
        ? ui.el("button", {
            class: "text-on-surface-variant hover:text-error p-0.5 rounded transition-colors shrink-0",
            title: "取消本章关联",
            onclick: async (ev) => {
              ev.preventDefault(); ev.stopPropagation();
              try {
                await api.del(`/chapters/${chapter.id}/entities/${ent.id}`);
                ui.toast(`已取消关联「${ent.name}」`, "ok");
                renderContext();
              } catch (err) { ui.toast("取消关联失败：" + err.message, "err"); }
            },
          }, ui.icon("close", "text-[14px]"))
        : ui.el("button", {
            class: "text-secondary hover:text-primary p-0.5 rounded transition-colors shrink-0",
            title: "固定关联到本章",
            onclick: async (ev) => {
              ev.preventDefault(); ev.stopPropagation();
              try {
                await api.post(`/chapters/${chapter.id}/entities`, { entity_id: ent.id });
                ui.toast(`已将「${ent.name}」固定关联至本章`, "ok");
                renderContext();
              } catch (err) { ui.toast("关联失败：" + err.message, "err"); }
            },
          }, ui.icon("bookmark_add", "text-[14px]"));

      const row = ui.el("div", {
        class: "flex items-center gap-1.5 px-1 py-0.5 rounded-lg hover:bg-surface-container-low transition-colors group",
      }, cb, catIcon, nameEl, statusTag, actionBtn);

      container.append(row);
    }
    updateBadge();
  }

  async function runSmartDetect() {
    if (!chapter) return;
    if (!allEntities.length) {
      try { allEntities = await api.get(`/works/${workId}/entities`); } catch (e) {}
    }
    const text = editorText();
    const all = detectEntitiesInContent(text);

    let unreg = [];
    try {
      const res = await api.post(`/works/${workId}/entities/detect-unregistered`, {
        content: text,
        chapter_id: chapter.id
      });
      if (res && res.unregistered) unreg = res.unregistered;
    } catch (e) {
      console.warn("探测未入库设定失败:", e);
    }

    if (unreg.length > 0) {
      openUnregisteredIntakeDialog(unreg);
    } else {
      if (!all.length) {
        ui.toast("正文中未提及已登记设定，亦未发现新设定候选", "info");
      } else {
        const linkedIds = new Set(linkedEntities.map((e) => e.id));
        const newOnes = all.filter((e) => !linkedIds.has(e.id));
        ui.toast(`智能识别完成：探测到 ${all.length} 个设定条目${newOnes.length ? `（${newOnes.length} 个未绑定）` : ""}`, "ok");
      }
    }
    await renderContext();
  }

  /* ---------- 未入库新设定确认弹窗 ---------- */
  function openUnregisteredIntakeDialog(unregList) {
    if (!chapter || !unregList || !unregList.length) return;
    const root = document.getElementById("modal-root");

    const itemsState = unregList.map((item) => ({
      name: item.name,
      category: item.category || "term",
      snippet: item.snippet || "",
      suggested_tags: item.suggested_tags || "",
      checked: true,
    }));

    const listBox = ui.el("div", { class: "flex flex-col gap-2 max-h-[50vh] overflow-y-auto pr-1" });

    function renderList() {
      listBox.innerHTML = "";
      itemsState.forEach((st) => {
        const cb = ui.el("input", { type: "checkbox", class: "accent-[#316bf3] shrink-0" });
        cb.checked = st.checked;
        cb.addEventListener("change", () => {
          st.checked = cb.checked;
          updateSubmitBtn();
        });

        const nameInput = ui.el("input", {
          class: "px-2 py-1 text-[13px] font-semibold text-primary bg-surface-container rounded-lg border border-border-feather focus:border-primary outline-none min-w-[100px] max-w-[140px]",
          value: st.name,
        });
        nameInput.addEventListener("input", () => {
          st.name = nameInput.value.trim();
          updateSubmitBtn();
        });

        const catSelect = ui.el("select", {
          class: "px-2 py-1 text-[12px] bg-surface-container rounded-lg border border-border-feather outline-none text-on-surface-variant font-label-sm shrink-0",
        },
          ui.el("option", { value: "character", selected: st.category === "character" }, "人物"),
          ui.el("option", { value: "item", selected: st.category === "item" }, "道具/法宝"),
          ui.el("option", { value: "place", selected: st.category === "place" }, "地点/场景"),
          ui.el("option", { value: "faction", selected: st.category === "faction" }, "势力/宗门"),
          ui.el("option", { value: "term", selected: st.category === "term" }, "法则/术语"),
          ui.el("option", { value: "custom", selected: st.category === "custom" }, "自定义")
        );
        catSelect.addEventListener("change", () => {
          st.category = catSelect.value;
        });

        const snippetEl = st.snippet ? ui.el("span", {
          class: "text-[11px] text-on-surface-variant line-clamp-1 italic bg-surface-container-low px-1.5 py-0.5 rounded truncate flex-1 min-w-0",
          title: st.snippet
        }, `“${st.snippet}”`) : null;

        const row = ui.el("div", {
          class: "flex items-center gap-2 p-2 rounded-xl border border-border-feather bg-surface-container-lowest hover:bg-surface-container-low/50 transition-colors",
        }, cb, nameInput, catSelect, snippetEl);

        listBox.append(row);
      });
    }

    const selectAllBtn = ui.el("button", {
      class: "text-[12px] text-primary hover:underline cursor-pointer",
      onclick: () => {
        const allChecked = itemsState.every((i) => i.checked);
        itemsState.forEach((i) => { i.checked = !allChecked; });
        renderList();
        updateSubmitBtn();
      }
    }, "全选 / 反选");

    const submitBtn = ui.el("button", {
      class: "px-4 py-1.5 rounded-lg bg-primary text-on-primary font-label-md text-label-md hover:bg-primary-container transition-colors disabled:opacity-40 disabled:cursor-not-allowed",
      onclick: async () => {
        const selected = itemsState.filter((i) => i.checked && i.name);
        if (!selected.length) return;
        submitBtn.disabled = true;
        submitBtn.textContent = "入库中...";
        try {
          const payload = {
            entities: selected.map((s) => ({
              name: s.name,
              category: s.category,
              content: s.snippet ? `【出处引文】\n${s.snippet}` : "",
              tags: s.suggested_tags
            })),
            chapter_id: chapter.id
          };
          const res = await api.post(`/works/${workId}/entities/batch-intake`, payload);
          ui.toast(`成功收录 ${res.added_count} 个新设定并关联至本章`, "ok");
          overlay.remove();
          if (window.store && window.store.events) {
            window.store.events.emit("entity:changed", { workId });
          }
          try { allEntities = await api.get(`/works/${workId}/entities`); } catch (_) {}
          await renderContext();
        } catch (e) {
          ui.toast("批量入库失败: " + e.message, "err");
          submitBtn.disabled = false;
          updateSubmitBtn();
        }
      }
    });

    function updateSubmitBtn() {
      const cnt = itemsState.filter((i) => i.checked && i.name).length;
      submitBtn.textContent = `确认收录入库 (${cnt})`;
      submitBtn.disabled = cnt === 0;
    }

    const overlay = ui.el("div", {
      class: "fixed inset-0 z-[90] bg-ink-black/40 backdrop-blur-sm flex items-center justify-center",
      onclick: (e) => { if (e.target === overlay) overlay.remove(); },
    },
      ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-lg w-[620px] max-w-[calc(100vw-1.5rem)] shadow-[0_12px_32px_rgba(27,42,56,0.16)] flex flex-col gap-space-md" },
        ui.el("div", { class: "flex items-center justify-between" },
          ui.el("div", { class: "flex items-center gap-2" },
            ui.icon("auto_awesome", "text-[22px] text-primary"),
            ui.el("div", { class: "flex flex-col" },
              ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, "发现正文未入库新设定"),
              ui.el("p", { class: "text-[12px] text-on-surface-variant" }, "以下条目疑似新设定，请核对分类并选择需要正式收录到万相谱的条目："))),
          ui.el("button", {
            class: "p-1 rounded-lg hover:bg-surface-container text-on-surface-variant cursor-pointer",
            onclick: () => overlay.remove(),
          }, ui.icon("close", "text-[20px]"))),
        ui.el("div", { class: "flex items-center justify-between px-1" },
          ui.el("span", { class: "text-[12px] text-on-surface-variant font-label-sm" }, `共探测到 ${itemsState.length} 个候选条目`),
          selectAllBtn),
        listBox,
        ui.el("div", { class: "flex items-center justify-end gap-2 pt-2 border-t border-border-feather" },
          ui.el("button", {
            class: "px-3 py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface-variant font-label-md text-label-md transition-colors cursor-pointer",
            onclick: () => overlay.remove()
          }, "取消"),
          submitBtn)));

    renderList();
    updateSubmitBtn();
    root.append(overlay);
  }

  /* ---------- 实体挑选弹窗 ---------- */

  function openEntityPickerDialog() {
    if (!chapter) return;
    const root = document.getElementById("modal-root");
    let filterCat = "all";
    let filterQ = "";

    const searchInput = ui.el("input", {
      class: "w-full bg-transparent outline-none font-body-sm text-body-sm",
      placeholder: "搜索设定名称、标签、内容…",
    });

    const tabsBox = ui.el("div", { class: "flex items-center gap-1 flex-wrap" });
    const listBox = ui.el("div", { class: "flex flex-col gap-2 max-h-[46vh] overflow-y-auto pr-1" });

    function renderPickerTabs() {
      tabsBox.innerHTML = "";
      const tabs = [{ key: "all", label: "全部" }, ...Object.values(ENTITY_CATS)];
      for (const t of tabs) {
        const key = t.key || "all";
        const count = key === "all"
          ? allEntities.length
          : allEntities.filter((e) => e.category === key).length;
        tabsBox.append(ui.el("button", {
          class: `px-2.5 py-1 rounded-full text-[12px] font-label-sm transition-all ${
            filterCat === key
              ? "bg-primary text-on-primary font-semibold"
              : "bg-surface-container-low text-on-surface-variant hover:bg-surface-container"
          }`,
          onclick: () => { filterCat = key; renderPickerTabs(); renderPickerList(); },
        }, `${t.label}${count ? ` (${count})` : ""}`));
      }
    }

    function renderPickerList() {
      listBox.innerHTML = "";
      const linkedIds = new Set(linkedEntities.map((e) => e.id));
      const q = filterQ.trim().toLowerCase();
      const filtered = allEntities.filter((e) => {
        if (filterCat !== "all" && e.category !== filterCat) return false;
        if (!q) return true;
        return (e.name && e.name.toLowerCase().includes(q)) ||
               (e.tags && e.tags.toLowerCase().includes(q)) ||
               (e.content && e.content.toLowerCase().includes(q));
      });

      if (!filtered.length) {
        listBox.append(ui.el("div", {
          class: "p-6 text-center text-on-surface-variant font-body-sm flex flex-col items-center gap-2",
        },
          ui.icon("manage_search", "text-[32px] text-outline"),
          ui.el("p", null, allEntities.length === 0
            ? "设定库暂无条目，可先前往万象谱创建"
            : "没有符合条件的设定条目"),
          allEntities.length === 0 ? ui.el("button", {
            class: "px-3 py-1 rounded-lg bg-primary text-on-primary font-label-md text-label-md",
            onclick: () => { overlay.remove(); location.hash = `#/entities/${workId}`; },
          }, "前往万象谱") : null));
        return;
      }

      for (const ent of filtered) {
        const isLinked = linkedIds.has(ent.id);
        const meta = ENTITY_CATS[ent.category] || ENTITY_CATS.custom;
        const brief = (ent.content || "").replace(/\s+/g, " ").slice(0, 50);

        const linkBtn = ui.el("button", {
          class: isLinked
            ? "px-2.5 py-1 rounded-md bg-surface-container text-on-surface-variant font-label-sm text-label-sm hover:bg-error-container hover:text-on-error-container transition-colors shrink-0"
            : "px-2.5 py-1 rounded-md bg-primary text-on-primary font-label-sm text-label-sm hover:bg-primary-container transition-colors shrink-0",
          onclick: async () => {
            try {
              if (isLinked) {
                await api.del(`/chapters/${chapter.id}/entities/${ent.id}`);
                linkedEntities = linkedEntities.filter((x) => x.id !== ent.id);
                ui.toast(`已取消关联「${ent.name}」`, "ok");
              } else {
                await api.post(`/chapters/${chapter.id}/entities`, { entity_id: ent.id });
                linkedEntities.push(ent);
                ui.toast(`已关联「${ent.name}」`, "ok");
              }
              renderPickerList();
              renderContext();
            } catch (err) { ui.toast("操作失败：" + err.message, "err"); }
          },
        }, isLinked ? "取消关联" : "+ 关联");

        const row = ui.el("div", {
          class: "flex items-start justify-between gap-3 p-2.5 rounded-xl border border-border-feather hover:border-primary/40 bg-surface-container-lowest transition-colors",
        },
          ui.el("div", { class: "flex items-start gap-2.5 min-w-0" },
            ui.el("div", { class: `w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${meta.badge}` },
              ui.icon(meta.icon, "text-[16px]")),
            ui.el("div", { class: "flex flex-col gap-0.5 min-w-0" },
              ui.el("div", { class: "flex items-center gap-1.5 flex-wrap" },
                ui.el("span", { class: "font-label-md text-label-md text-on-surface font-semibold truncate" }, ent.name),
                ui.el("span", { class: `text-[10px] px-1 rounded ${meta.badge}` }, meta.label),
                ent.tags ? ui.el("span", { class: "text-[11px] text-on-surface-variant" }, `· ${ent.tags}`) : null),
              brief ? ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant line-clamp-2" }, brief) : null)),
          linkBtn);
        listBox.append(row);
      }
    }

    let debounceSearch = null;
    searchInput.addEventListener("input", () => {
      clearTimeout(debounceSearch);
      debounceSearch = setTimeout(() => { filterQ = searchInput.value; renderPickerList(); }, 200);
    });

    const overlay = ui.el("div", {
      class: "fixed inset-0 z-[90] bg-ink-black/40 backdrop-blur-sm flex items-center justify-center",
      onclick: (e) => { if (e.target === overlay) overlay.remove(); },
    },
      ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-lg w-[560px] max-w-[calc(100vw-1.5rem)] shadow-[0_12px_32px_rgba(27,42,56,0.16)] flex flex-col gap-space-md" },
        ui.el("div", { class: "flex items-center justify-between" },
          ui.el("div", { class: "flex items-center gap-2" },
            ui.icon("psychology", "text-[22px] text-primary"),
            ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, "关联设定到当前章节")),
          ui.el("button", {
            class: "p-1 rounded-lg hover:bg-surface-container text-on-surface-variant",
            onclick: () => overlay.remove(),
          }, ui.icon("close", "text-[20px]"))),
        ui.el("div", { class: "flex items-center gap-2 bg-surface-container-low rounded-lg px-2.5 py-1" },
          ui.icon("search", "text-[18px] text-on-surface-variant"), searchInput),
        tabsBox,
        listBox,
        ui.el("div", { class: "flex items-center justify-between pt-1 border-t border-border-feather" },
          ui.el("a", {
            class: "flex items-center gap-1 font-label-sm text-label-sm text-secondary hover:underline",
            href: `#/entities/${workId}`,
            onclick: (e) => { e.preventDefault(); overlay.remove(); location.hash = `#/entities/${workId}`; },
          }, ui.icon("open_in_new", "text-[14px]"), "前往万象谱管理全部设定"),
          ui.el("button", {
            class: "px-4 py-1.5 rounded-lg bg-primary text-on-primary font-label-md text-label-md hover:bg-primary-container transition-colors",
            onclick: () => overlay.remove(),
          }, "完成"))));

    renderPickerTabs();
    renderPickerList();
    root.append(overlay);
    searchInput.focus();
  }

  /* ---------- 实体详情预览弹窗 ---------- */

  function openEntityPreviewDialog(ent) {
    const root = document.getElementById("modal-root");
    const meta = ENTITY_CATS[ent.category] || ENTITY_CATS.custom;

    const fieldsBox = ui.el("div", { class: "grid grid-cols-1 sm:grid-cols-2 gap-2" });
    if (ent.fields && typeof ent.fields === "object") {
      for (const [k, v] of Object.entries(ent.fields)) {
        if (v && typeof v === "string" && v.trim()) {
          fieldsBox.append(ui.el("div", { class: "flex flex-col p-2 rounded-lg bg-surface-container-low" },
            ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant font-medium" }, k),
            ui.el("span", { class: "font-body-sm text-body-sm text-on-surface" }, v.trim())));
        }
      }
    }
    const hasFields = fieldsBox.children.length > 0;

    const overlay = ui.el("div", {
      class: "fixed inset-0 z-[90] bg-ink-black/40 backdrop-blur-sm flex items-center justify-center",
      onclick: (e) => { if (e.target === overlay) overlay.remove(); },
    },
      ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-lg w-[520px] max-w-[calc(100vw-1.5rem)] shadow-[0_12px_32px_rgba(27,42,56,0.16)] flex flex-col gap-space-md max-h-[85vh] overflow-y-auto" },
        ui.el("div", { class: "flex items-start justify-between gap-2" },
          ui.el("div", { class: "flex items-center gap-2" },
            ui.el("div", { class: `w-9 h-9 rounded-lg flex items-center justify-center ${meta.badge}` },
              ui.icon(meta.icon, "text-[20px]")),
            ui.el("div", { class: "flex flex-col" },
              ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, ent.name),
              ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, `${meta.label}${ent.tags ? ` · ${ent.tags}` : ""}`))),
          ui.el("button", {
            class: "p-1 rounded-lg hover:bg-surface-container text-on-surface-variant",
            onclick: () => overlay.remove(),
          }, ui.icon("close", "text-[20px]"))),
        hasFields ? fieldsBox : null,
        ui.el("div", { class: "flex flex-col gap-1" },
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant font-medium" }, "详细设定"),
          ui.el("div", {
            class: "p-3 rounded-lg bg-surface-container-low font-body-sm text-body-sm text-on-surface whitespace-pre-wrap leading-relaxed max-h-[30vh] overflow-y-auto",
          }, ent.content || "（暂无详细说明）")),
        ui.el("div", { class: "flex items-center justify-between pt-2 border-t border-border-feather" },
          ui.el("a", {
            class: "flex items-center gap-1 font-label-sm text-label-sm text-secondary hover:underline",
            href: `#/entities/${workId}`,
            onclick: (e) => { e.preventDefault(); overlay.remove(); location.hash = `#/entities/${workId}`; },
          }, ui.icon("edit", "text-[14px]"), "在万象谱中编辑"),
          ui.el("button", {
            class: "px-4 py-1.5 rounded-lg bg-primary text-on-primary font-label-md text-label-md hover:bg-primary-container transition-colors",
            onclick: () => overlay.remove(),
          }, "关闭"))));
    root.append(overlay);
  }

  /* ---------- 关联信息栏 ---------- */

  function renderRelated() {
    relatedBox.innerHTML = "";
    if (!chapter) return;
    const node = findCurrentOutlineNode();
    if (node) {
      relatedBox.append(ui.el("div", { class: "flex items-start gap-2 px-2 py-1.5 rounded-lg bg-surface-container-low" },
        ui.icon("account_tree", "text-[16px] text-secondary mt-0.5"),
        ui.el("div", { class: "flex flex-col min-w-0" },
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "关联大纲节点"),
          ui.el("span", { class: "font-body-sm text-body-sm text-on-surface truncate" }, node.title))));
    }
    relatedBox.append(ui.el("div", { class: "flex items-start gap-2 px-2 py-1.5 rounded-lg bg-surface-container-low" },
      ui.icon("edit_note", "text-[16px] text-secondary mt-0.5"),
      ui.el("div", { class: "flex flex-col min-w-0" },
        ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "当前章节字数"),
        ui.el("span", { class: "font-body-sm text-body-sm text-on-surface" }, `${ui.fmtWords(chapter.word_count || 0)} 字`))));
  }

  /* ---------- 生成（SSE 流式） ---------- */

  async function runGenerate() {
    if (generating || !chapter) return;
    if (dirty) await saveContent();
    saveRecentInstruction(instrInput.value.trim());
    const context = ctxItems.filter((i) => i.cb.checked)
      .map((i) => i.getText()).filter(Boolean).join("\n\n----\n\n");
    const payload = {
      task: aiTask,
      instruction: instrInput.value.trim(),
      context,
      selection: selText,
      length: aiLength,
      candidates: aiCandidates,
      stream: true,
      skill_id: skillIdForTask(aiTask),
    };
    abortCtrl = new AbortController();
    let resp;
    try {
      resp = await fetch("/api/ai/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: abortCtrl.signal,
      });
    } catch (e) {
      if (e.name !== "AbortError") ui.toast("生成请求失败：" + e.message, "err");
      return;
    }
    if (!resp.ok) {
      let msg = resp.statusText;
      try { msg = (await resp.json()).detail || msg; } catch (e) {}
      if (resp.status === 400 && msg.includes("未配置")) {
        const go = await ui.confirm("未配置 AI 接口", msg + "。配置后即可使用续写、改写等能力。", "去设置");
        if (go) location.hash = "#/settings";
      } else {
        ui.toast(msg, "err");
      }
      return;
    }

    generating = true;
    syncGenBtns();
    let curCard = null, gotDone = false, sawDelta = false;
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf("\n\n")) >= 0) {
          const frame = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          if (!frame.startsWith("data:")) continue;
          let evt;
          try { evt = JSON.parse(frame.slice(5).trim()); } catch (e) { continue; }
          if (evt.task_id) {
            updateTaskStatus(evt.task_id, "当前生成任务运行中…");
          } else if (evt.error) {
            ui.toast(evt.error, "err");
            if (curCard) { finishCard(curCard, true); curCard = null; }
          } else if (evt.start) {
            if (curCard) finishCard(curCard);   // 上一候选结束
            curCard = addCandidateCard(evt.candidate);
          } else if (evt.delta !== undefined && curCard) {
            sawDelta = true;
            curCard._text += evt.delta;
            curCard._body.textContent = curCard._text;
            curCard.scrollIntoView({ block: "nearest" });
          } else if (evt.done) {
            gotDone = true;
            if (curCard) { finishCard(curCard); curCard = null; }
            updateTaskStatus(evt.task_id, "当前生成任务已完成");
          }
        }
      }
    } catch (e) {
      if (e.name !== "AbortError") ui.toast("生成中断：" + e.message, "err");
    }
    /* 停止 / 中断时已生成内容保留；完全没收到内容的空卡视为失败清理掉 */
    if (curCard) {
      if (!curCard._text && !gotDone) { curCard.remove(); if (!sawDelta) ui.toast("生成中断：未收到有效内容，请重试", "err"); }
      else finishCard(curCard);
    }
    generating = false;
    abortCtrl = null;
    syncGenBtns();
  }

  /* ---------- 候选卡 ---------- */

  function addCandidateCard(idx) {
    const body = ui.el("div", {
      class: "streaming-caret font-serif-content text-body-sm whitespace-pre-wrap leading-relaxed text-on-surface",
    });
    const actions = ui.el("div", { class: "hidden flex-wrap gap-1 pt-1" });
    const taskName = { continue: "续写", expand: "扩写", condense: "缩写", polish: "改写润色" }[aiTask] || aiTask;
    const card = ui.el("div", {
      class: "ai-glow bg-surface-container-lowest rounded-xl p-space-sm flex flex-col gap-1",
    },
      ui.el("div", { class: "flex items-center gap-2" },
        ui.el("span", { class: "px-1.5 py-0.5 rounded bg-secondary-container text-on-secondary-container font-label-sm text-label-sm" }, "AI 生成"),
        ui.el("span", { class: "flex-1 font-label-sm text-label-sm text-on-surface-variant" }, `候选 ${idx + 1} · ${taskName}`),
        /* 流式期间卡内也放停止按钮，避免面板滚动后够不到 */
        ui.el("button", {
          class: "card-stop flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-error-container text-on-error-container font-label-sm text-label-sm",
          onclick: () => abortCtrl && abortCtrl.abort(),
        }, ui.icon("stop", "text-[13px]"), "停止")),
      body, actions);
    card._body = body;
    card._actions = actions;
    card._text = "";
    candidatesBox.append(card);
    card.scrollIntoView({ block: "nearest", behavior: "smooth" });
    return card;
  }

  function finishCard(card, isError = false) {
    card._body.classList.remove("streaming-caret");
    const stop = card.querySelector(".card-stop");
    if (stop) stop.remove();
    if (isError && !card._text) { card.remove(); return; }
    const a = card._actions;
    a.classList.remove("hidden");
    a.classList.add("flex");
    a.innerHTML = "";
    const btn = (label, icon, onclick, primary = false) => ui.el("button", {
      class: `flex items-center gap-0.5 px-2 py-1 rounded-md font-label-sm text-label-sm transition-colors ${
        primary ? "bg-primary text-on-primary" : "bg-surface-container hover:bg-surface-container-high"}`,
      onclick,
    }, ui.icon(icon, "text-[14px]"), label);

    a.append(
      btn("预览差异", "compare", () => toggleDiff(card)),
      btn("采纳", "check", () => adopt(card), true),
      btn("复制", "content_copy", async () => {
        await navigator.clipboard.writeText(card._text);
        ui.toast("已复制", "ok");
      }),
      btn("重试", "refresh", () => runGenerate()),
      btn("放弃", "close", async () => {
        const ok = await ui.confirm("放弃候选", "该候选内容将被丢弃，确定继续？", "放弃", true);
        if (ok) card.remove();
      }));
  }

  /* 行级 diff（LCS），返回各行集合 */
  function lineDiff(a, b) {
    const A = a.split("\n"), B = b.split("\n");
    const m = A.length, n = B.length;
    const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
    for (let i = m - 1; i >= 0; i--)
      for (let j = n - 1; j >= 0; j--)
        dp[i][j] = A[i] === B[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    const del = new Set(), add = new Set();
    let i = 0, j = 0;
    while (i < m && j < n) {
      if (A[i] === B[j]) { i++; j++; }
      else if (dp[i + 1][j] >= dp[i][j + 1]) { del.add(i); i++; }
      else { add.add(j); j++; }
    }
    while (i < m) del.add(i++);
    while (j < n) add.add(j++);
    return { A, B, del, add };
  }

  function renderDiffLines(lines, marks, cls) {
    const box = ui.el("div", { class: "font-serif-content text-body-sm whitespace-pre-wrap leading-relaxed" });
    lines.forEach((ln, i) => {
      const d = ui.el("div", {}, ln || " ");
      if (marks.has(i)) d.className = cls + " px-1";
      box.append(d);
    });
    return box;
  }

  function toggleDiff(card) {
    if (card._diffBox) { card._diffBox.remove(); card._diffBox = null; return; }
    const original = selText || editorText().slice(-500);
    const { A, B, del, add } = lineDiff(original, card._text);
    card._diffBox = ui.el("div", { class: "grid grid-cols-1 sm:grid-cols-2 gap-2 p-2 rounded-lg bg-surface-container-low" },
      ui.el("div", { class: "flex flex-col gap-1 min-w-0" },
        ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, selText ? "原文（选区）" : "原文（正文末尾 500 字）"),
        renderDiffLines(A, del, "diff-del")),
      ui.el("div", { class: "flex flex-col gap-1 min-w-0" },
        ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "AI 文本"),
        renderDiffLines(B, add, "diff-add")));
    card.insertBefore(card._diffBox, card._actions);
  }

  /* 选区 Range 是否仍然有效且内容未变 */
  function rangeAlive() {
    try {
      return selRange && selRange.startContainer.isConnected
        && editor.contains(selRange.startContainer)
        && selRange.toString() === selText;
    } catch (e) { return false; }
  }

  async function adopt(card) {
    const text = card._text;
    const res = await applyAdoptContent(text, null);
    if (!res || !res.ok) return;
    const old = res.oldContent;

    /* 提供撤销采纳 */
    card._actions.innerHTML = "";
    card._actions.append(ui.el("button", {
      class: "flex items-center gap-0.5 px-2 py-1 rounded-md bg-error-container text-on-error-container font-label-sm text-label-sm",
      onclick: async () => {
        await applyUndoAdopt(old, null);
        card.remove();
      },
    }, ui.icon("undo", "text-[14px]"), "撤销采纳"));
  }

  /* ---------- 无作品参数时的作品选择 ---------- */

  async function renderWorkPicker(v) {
    ui.setCrumb("写作工作台");
    const grid = ui.el("div", { class: "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-space-md" });
    v.append(
      ui.el("div", { class: "flex flex-col gap-1 mb-space-lg" },
        ui.el("h1", { class: "font-headline-lg text-headline-lg text-primary font-semibold" }, "选择要写作的作品"),
        ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant" }, "从下面的作品进入写作工作台。")),
      grid);
    let works;
    try { works = await api.get("/works"); } catch (e) { ui.toast(e.message, "err"); return; }
    if (!works.length) {
      grid.append(ui.el("div", { class: "col-span-full flex flex-col items-center gap-space-md py-space-xl text-on-surface-variant" },
        ui.icon("auto_stories", "text-[48px] text-outline-variant"),
        ui.el("p", { class: "font-body-md text-body-md" }, "书架还是空的，请先到书架创建作品"),
        ui.el("button", {
          class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md",
          onclick: () => { location.hash = "#/bookshelf"; },
        }, "前往书架")));
      return;
    }
    for (const w of works) {
      grid.append(ui.el("div", {
        class: "bg-surface-container-lowest rounded-xl p-space-md shadow-[0_4px_20px_rgba(6,21,35,0.03)] flex flex-col gap-space-xs cursor-pointer hover:shadow-[0_8px_28px_rgba(6,21,35,0.08)] transition-shadow",
        onclick: async () => {
          if (w.last_chapter) { location.hash = `#/workbench/${w.id}?chapter=${w.last_chapter.id}`; return; }
          const t = await api.get(`/works/${w.id}/tree`);
          const c = t.flatMap((x) => x.chapters)[0];
          location.hash = c ? `#/workbench/${w.id}?chapter=${c.id}` : `#/workbench/${w.id}`;
        },
      },
        ui.el("div", { class: "flex items-center gap-2" },
          ui.el("span", { class: "px-2 py-0.5 rounded-full bg-primary-fixed text-on-primary-fixed font-label-sm text-label-sm" }, w.status || "连载中"),
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, ui.fmtWords(w.total_words) + " 字")),
        ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold truncate" }, w.title),
        w.last_chapter && ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "最近：" + w.last_chapter.title)));
    }
  }
});
