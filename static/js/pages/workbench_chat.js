/* 墨语 MoYu · AI 修撰使 多轮对话聊天窗口 (v1.3.0) */

window.WorkbenchChat = (() => {
  /**
   * 初始化修撰使聊天面板
   * @param {Object} options
   * @param {number} options.workId
   * @param {Function} options.getChapter - 获取当前章节记录 () => chapter
   * @param {Function} options.getSelection - 获取选区对象 () => ({ text, range })
   * @param {Function} options.clearSelection - 清除选区 () => void
   * @param {Function} options.getContext - 获取挂载的上下文文本 () => string
   * @param {Function} options.getContextCount - 获取挂载上下文项数 () => number
   * @param {HTMLElement} options.contextDrawerEl - 上下文抽屉元素 (展开时展示)
   * @param {HTMLElement} options.classicSettingsEl - 经典任务设置元素 (设置抽屉内展示)
   * @param {Function} options.onAdopt - 采纳回调 async (msg, text) => Promise<boolean>
   * @param {Function} options.onUndoAdopt - 撤销采纳回调 async (msg) => Promise<void>
   * @param {Function} options.onRetry - 重试生成回调 (task, selection, instruction) => void
   * @param {Function} options.isClassicMode - 是否经典候选模式 () => boolean
   * @param {Function} options.toggleClassicMode - 切换经典候选模式 (val) => void
   */
  function init(options) {
    const {
      workId,
      getChapter,
      getSelection,
      clearSelection,
      getContext,
      getContextCount,
      getContextOptions,
      contextDrawerEl,
      onAdopt,
      onUndoAdopt,
      onRetry,
    } = options;

    let currentSessionId = null;
    let messages = [];
    let isGenerating = false;
    let abortCtrl = null;
    let activeTask = "continue"; // continue | expand | condense | polish | analyze

    let aiLength = "2000";
    try {
      const savedLen = localStorage.getItem("moyu_ai_length");
      if (savedLen && ["500", "1000", "2000", "3000", "unlimited"].includes(savedLen)) aiLength = savedLen;
    } catch (_) {}

    let aiCandidates = 1;
    try {
      const savedCands = localStorage.getItem("moyu_ai_candidates");
      if (savedCands && ["1", "2", "3"].includes(savedCands)) aiCandidates = parseInt(savedCands, 10);
    } catch (_) {}

    /* ---------- DOM 结构搭建 ---------- */

    // 1. 顶部栏 (Avatar + 标题 + 经典模式/设置切换 + 新对话)
    const headerTitle = ui.el("div", { class: "flex items-center gap-2 min-w-0" },
      ui.el("div", {
        class: "w-8 h-8 rounded-full bg-primary text-on-primary flex items-center justify-center shrink-0 shadow-sm",
      }, ui.icon("auto_awesome", "text-[16px]")),
      ui.el("div", { class: "flex flex-col min-w-0" },
        ui.el("span", { class: "font-headline-sm text-label-md font-semibold text-primary truncate" }, "墨语 · 修撰使"),
        ui.el("span", { class: "font-label-sm text-[11px] text-on-surface-variant truncate" }, "多轮会话 · 伴写推演"))
    );

    const newChatBtn = ui.el("button", {
      class: "flex items-center gap-1 px-2.5 py-1 rounded-lg bg-surface-container hover:bg-surface-container-high text-primary font-label-sm text-label-sm transition-colors cursor-pointer",
      title: "新建对话，清空当前对话窗",
      onclick: () => startNewSession(),
    }, ui.icon("add_comment", "text-[15px]"), "新对话");

    const header = ui.el("div", {
      class: "flex items-center justify-between gap-2 p-space-sm bg-surface-container-lowest rounded-xl border border-border-feather shadow-[0_2px_10px_rgba(6,21,35,0.02)] shrink-0",
    }, headerTitle, newChatBtn);

    const ctxSummaryCount = ui.el("span", { class: "text-primary font-semibold" }, "0");
    const ctxArrowIcon = ui.icon("keyboard_arrow_down", "text-[18px] transition-transform");

    const contextSummaryBar = ui.el("div", {
      class: "flex items-center justify-between px-3 py-1.5 bg-surface-container-lowest rounded-xl border border-border-feather shadow-[0_1px_4px_rgba(6,21,35,0.02)] cursor-pointer hover:bg-surface-container-low transition-colors shrink-0",
      onclick: () => toggleContextDrawer(),
    },
      ui.el("div", { class: "flex items-center gap-1.5 text-on-surface-variant font-label-sm text-label-sm" },
        ui.icon("linked_services", "text-[16px] text-primary"),
        ui.el("span", {}, "已挂载 "),
        ctxSummaryCount,
        ui.el("span", {}, " 项上下文")),
      ctxArrowIcon
    );

    const contextDrawerBox = ui.el("div", {
      class: "hidden flex flex-col gap-2 p-2 bg-surface-container-lowest rounded-xl border border-border-feather shadow-sm shrink-0 max-h-64 overflow-y-auto",
    }, contextDrawerEl || ui.el("div"));

    function toggleContextDrawer(show) {
      const willShow = show !== undefined ? show : contextDrawerBox.classList.contains("hidden");
      contextDrawerBox.classList.toggle("hidden", !willShow);
      ctxArrowIcon.style.transform = willShow ? "rotate(180deg)" : "rotate(0deg)";
    }

    function updateContextCount() {
      const count = getContextCount ? getContextCount() : 0;
      ctxSummaryCount.textContent = String(count);
    }

    // 4. 消息滚动区
    const msgListEl = ui.el("div", {
      class: "flex-1 min-h-[180px] overflow-y-auto flex flex-col gap-3 py-2 pr-1 select-text scroll-smooth",
    });

    const emptyPlaceholder = ui.el("div", {
      class: "flex-1 flex flex-col items-center justify-center p-6 text-center text-on-surface-variant gap-2 opacity-80",
    },
      ui.icon("chat_bubble_outline", "text-[36px] text-outline-variant"),
      ui.el("span", { class: "font-label-md text-label-md font-medium text-on-surface" }, "长篇创作伙伴就绪"),
      ui.el("p", { class: "text-body-sm text-[12px] max-w-xs leading-relaxed" },
        "在正文选中文字或在下方选择任务标签，可直接顺延文势续写、扩写细节或打磨辞藻。")
    );

    // 5. 底部固定输入区
    // 快捷任务标签
    // 任务药丸 (Action Pills) 与联动提示
    const TASK_PILLS = [
      { id: "continue", label: "续写", placeholder: "输入续写要求或补充指引（可选），Enter 发送，Shift+Enter 换行" },
      { id: "expand",   label: "扩写", placeholder: "输入扩写指引，重点丰富细节、描写或动作心理..." },
      { id: "condense", label: "缩写", placeholder: "输入精炼指引，保留核心冲突与情节骨架..." },
      { id: "polish",   label: "润色", placeholder: "输入润色风格要求（如强化白描、文笔典雅等）..." },
      { id: "analyze",  label: "推演", placeholder: "输入推演方向，分析当前情节走向与戏剧冲突..." },
    ];

    const taskChipEls = {};
    const taskChipsBar = ui.el("div", { class: "flex items-center gap-1 overflow-x-auto no-scrollbar py-0.5" });

    TASK_PILLS.forEach((tc) => {
      const chip = ui.el("button", {
        class: "px-2.5 py-1 rounded-lg text-[12px] font-label-sm cursor-pointer transition-all border shrink-0",
        onclick: () => {
          setActiveTask(tc.id);
          inputArea.focus();
        },
      }, tc.label);
      taskChipEls[tc.id] = chip;
      taskChipsBar.append(chip);
    });

    const lenSelect = ui.el("select", {
      class: "text-[11px] py-1 px-1.5 rounded-lg bg-surface-container border-0 text-on-surface-variant font-label-sm cursor-pointer outline-none hover:bg-surface-container-high transition-colors shrink-0",
      title: "目标输出字数偏好",
      onchange: (e) => {
        aiLength = e.target.value;
        try { localStorage.setItem("moyu_ai_length", aiLength); } catch (_) {}
      },
    },
      ui.el("option", { value: "500", selected: aiLength === "500" }, "500字"),
      ui.el("option", { value: "1000", selected: aiLength === "1000" }, "1000字"),
      ui.el("option", { value: "2000", selected: aiLength === "2000" }, "2000字"),
      ui.el("option", { value: "3000", selected: aiLength === "3000" }, "3000字"),
      ui.el("option", { value: "unlimited", selected: aiLength === "unlimited" }, "不上限")
    );

    const candSelect = ui.el("select", {
      class: "text-[11px] py-1 px-1.5 rounded-lg bg-surface-container border-0 text-on-surface-variant font-label-sm cursor-pointer outline-none hover:bg-surface-container-high transition-colors shrink-0",
      title: "候选生成数量（1~3候选对比）",
      onchange: (e) => {
        aiCandidates = parseInt(e.target.value, 10);
        try { localStorage.setItem("moyu_ai_candidates", String(aiCandidates)); } catch (_) {}
      },
    },
      ui.el("option", { value: "1", selected: aiCandidates === 1 }, "1候选"),
      ui.el("option", { value: "2", selected: aiCandidates === 2 }, "2候选"),
      ui.el("option", { value: "3", selected: aiCandidates === 3 }, "3候选")
    );

    const skillMenuLabel = ui.el("span", { class: "max-w-[56px] truncate" }, "自动");
    const skillMenuBox = ui.el("div", {
      class: "hidden absolute right-0 bottom-full mb-1 w-52 max-h-60 overflow-y-auto rounded-xl bg-surface-container-lowest border border-border-feather shadow-[0_8px_28px_rgba(6,21,35,0.14)] p-1 z-30 flex-col gap-0.5",
    });
    const skillMenuBtn = ui.el("button", {
      class: "flex items-center gap-0.5 px-1.5 py-1 rounded-lg text-[11px] font-label-sm cursor-pointer transition-all border shrink-0 bg-surface-container hover:bg-surface-container-high text-on-surface-variant border-transparent",
      title: "为当前任务选择写作技能",
      onclick: (e) => { e.stopPropagation(); toggleSkillMenu(); },
    }, ui.icon("tune", "text-[13px] text-primary"), skillMenuLabel, ui.icon("keyboard_arrow_up", "text-[13px]"));
    const skillMenuWrap = ui.el("div", { class: "relative shrink-0" }, skillMenuBtn, skillMenuBox);

    function updateSkillMenuLabel() {
      const bridge = window.aiSkillBridge;
      if (!bridge) { skillMenuWrap.classList.add("hidden"); return; }
      skillMenuWrap.classList.remove("hidden");
      const id = bridge.get(activeTask);
      const s = id ? bridge.listForTask(activeTask).find((x) => x.id === id) : null;
      skillMenuLabel.textContent = s ? s.title : "自动";
      skillMenuBtn.title = s ? `当前技能：${s.title}` : "自动匹配内置技能（点击更换）";
    }

    function closeSkillMenu() {
      if (!skillMenuBox.isConnected) {
        document.removeEventListener("click", closeSkillMenu);
        return;
      }
      skillMenuBox.classList.add("hidden");
      skillMenuBox.classList.remove("flex");
    }

    function toggleSkillMenu() {
      if (!skillMenuBox.classList.contains("hidden")) { closeSkillMenu(); return; }
      const bridge = window.aiSkillBridge;
      if (!bridge) return;
      skillMenuBox.innerHTML = "";
      const current = bridge.get(activeTask);
      const mkItem = (id, label, hint) => ui.el("button", {
        class: "flex items-center gap-1.5 w-full text-left px-2 py-1.5 rounded-lg hover:bg-surface-container text-[12px] text-on-surface cursor-pointer",
        onclick: (e) => {
          e.stopPropagation();
          bridge.set(activeTask, id);
          updateSkillMenuLabel();
          closeSkillMenu();
        },
      },
        ui.icon(id === current ? "check_circle" : "radio_button_unchecked", `text-[14px] shrink-0 ${id === current ? "text-primary" : "text-outline-variant"}`),
        ui.el("span", { class: "truncate" }, label),
        hint && ui.el("span", { class: "ml-auto text-[10px] text-on-surface-variant shrink-0" }, hint));
      skillMenuBox.append(mkItem(null, "自动匹配内置技能", "推荐"));
      const list = bridge.listForTask(activeTask);
      list.forEach((s) => skillMenuBox.append(mkItem(s.id, s.title, s.source === "builtin" ? "内置" : "自定义")));
      if (!list.length) {
        skillMenuBox.append(ui.el("div", { class: "px-2 py-1 text-[11px] text-on-surface-variant" }, "当前类型暂无可用技能"));
      }
      skillMenuBox.classList.remove("hidden");
      skillMenuBox.classList.add("flex");
    }
    document.addEventListener("click", closeSkillMenu);

    function setActiveTask(task) {
      activeTask = task;
      TASK_PILLS.forEach((tc) => {
        const el = taskChipEls[tc.id];
        if (tc.id === activeTask) {
          el.className = "px-2.5 py-1 rounded-lg text-[12px] font-label-sm cursor-pointer transition-all shrink-0 bg-primary text-on-primary border-primary font-semibold shadow-xs";
          if (typeof inputArea !== "undefined") inputArea.placeholder = tc.placeholder;
        } else {
          el.className = "px-2.5 py-1 rounded-lg text-[12px] font-label-sm cursor-pointer transition-all shrink-0 bg-surface-container hover:bg-surface-container-high text-on-surface-variant border-transparent";
        }
      });
      if (window.aiSkillBridge) window.aiSkillBridge.syncWindow(task);
      closeSkillMenu();
      updateSkillMenuLabel();
    }

    const controlsWrap = ui.el("div", { class: "flex items-center gap-1 ml-auto shrink-0" }, lenSelect, candSelect, skillMenuWrap);
    const topControlRow = ui.el("div", { class: "flex items-center justify-between gap-1.5 pb-1 flex-wrap" }, taskChipsBar, controlsWrap);

    // 选区引用提示条
    const selQuoteBox = ui.el("div", {
      class: "hidden items-center justify-between gap-1 px-2.5 py-1 mb-1 rounded-lg bg-surface-container text-on-surface-variant font-label-sm text-[12px] border border-border-feather",
    },
      ui.el("div", { class: "flex items-center gap-1 min-w-0" },
        ui.icon("format_quote", "text-[15px] text-primary shrink-0"),
        ui.el("span", { class: "truncate" }, "已引用选区 "),
        ui.el("span", { class: "font-semibold text-primary sel-count" }, "0"),
        ui.el("span", {}, " 字")),
      ui.el("button", {
        class: "w-5 h-5 flex items-center justify-center rounded hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface cursor-pointer shrink-0",
        title: "取消引用该选区",
        onclick: () => {
          if (clearSelection) clearSelection();
          updateSelectionQuote();
        },
      }, ui.icon("close", "text-[14px]"))
    );

    function updateSelectionQuote() {
      const sel = getSelection ? getSelection() : null;
      if (sel && sel.text && sel.text.trim()) {
        const count = sel.text.trim().length;
        const countEl = selQuoteBox.querySelector(".sel-count");
        if (countEl) countEl.textContent = String(count);
        selQuoteBox.classList.remove("hidden");
        selQuoteBox.classList.add("flex");
      } else {
        selQuoteBox.classList.add("hidden");
        selQuoteBox.classList.remove("flex");
      }
    }

    const inputArea = ui.el("textarea", {
      class: "w-full max-h-32 min-h-[44px] py-2 px-3 rounded-xl bg-surface-container-low border border-border-feather focus:border-primary focus:bg-surface-container-lowest outline-none font-body-sm text-body-sm resize-none leading-relaxed transition-all placeholder:text-outline-variant",
      rows: "2",
      placeholder: "输入创作要求（如：补充暴风雨的环境描写），Enter 发送，Shift+Enter 换行",
    });

    const sendBtn = ui.el("button", {
      class: "w-9 h-9 min-h-[36px] rounded-xl flex items-center justify-center bg-primary text-on-primary hover:opacity-90 active:scale-95 transition-all cursor-pointer shrink-0 shadow-sm disabled:opacity-40 disabled:cursor-not-allowed",
      title: "发送 (Enter)",
      onclick: () => handleSend(),
    }, ui.icon("send", "text-[18px]"));

    const stopBtn = ui.el("button", {
      class: "hidden w-9 h-9 min-h-[36px] rounded-xl flex items-center justify-center bg-error-container text-on-error-container hover:opacity-90 active:scale-95 transition-all cursor-pointer shrink-0 shadow-sm",
      title: "中断生成",
      onclick: () => handleStop(),
    }, ui.icon("stop", "text-[18px]"));

    inputArea.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    });

    setActiveTask("continue");

    // 输入区容器
    const inputBar = ui.el("div", {
      class: "flex flex-col gap-1.5 p-2.5 bg-surface-container-lowest rounded-xl border border-border-feather shadow-[0_2px_12px_rgba(6,21,35,0.04)] shrink-0",
    },
      topControlRow,
      selQuoteBox,
      ui.el("div", { class: "flex items-end gap-2" },
        ui.el("div", { class: "flex-1 min-w-0" }, inputArea),
        sendBtn,
        stopBtn
      )
    );

    // 整个面板容器
    const rootEl = ui.el("div", {
      class: "h-full flex flex-col gap-2 min-h-0",
    },
      header,
      contextSummaryBar,
      contextDrawerBox,
      msgListEl,
      inputBar
    );

    /* ---------- 消息渲染机制 ---------- */

    function scrollToBottom() {
      msgListEl.scrollTop = msgListEl.scrollHeight;
    }

    function renderMessages() {
      msgListEl.innerHTML = "";
      if (!messages.length) {
        msgListEl.append(emptyPlaceholder);
        return;
      }
      messages.forEach((m) => {
        const bubble = createMessageBubble(m);
        msgListEl.append(bubble);
      });
      scrollToBottom();
    }

    const TASK_LABELS = {
      continue: "续写",
      expand: "扩写",
      condense: "缩写",
      polish: "改写",
      outline: "大纲",
      check: "检查",
      analyze: "分析",
    };

    /* ---------- 修撰使思考过程（Agent 风格步骤追踪） ---------- */

    const STEP_STATUS_STYLE = {
      doing: { icon: "progress_activity", cls: "text-primary animate-spin" },
      done:  { icon: "check_circle",      cls: "text-primary" },
      error: { icon: "error",             cls: "text-error" },
    };

    function buildStepsBox(autoExpanded) {
      const listEl = ui.el("div", { class: "flex flex-col gap-1 pt-1.5 mt-1 border-t border-border-feather/50" });
      const summaryText = ui.el("span", { class: "font-label-sm text-[12px] text-on-surface-variant whitespace-nowrap overflow-hidden text-ellipsis" }, "思考过程");
      const arrow = ui.icon("keyboard_arrow_down", "text-[16px] text-on-surface-variant transition-transform shrink-0");
      const summaryRow = ui.el("div", {
        class: "flex items-center gap-1.5 cursor-pointer select-none",
        onclick: () => {
          const willShow = listEl.classList.contains("hidden");
          listEl.classList.toggle("hidden", !willShow);
          arrow.style.transform = willShow ? "rotate(180deg)" : "rotate(0deg)";
        },
      }, ui.icon("psychology", "text-[14px] text-primary"), summaryText, arrow);
      const box = ui.el("div", {
        class: "mb-2 px-2.5 py-1.5 rounded-lg bg-surface-container-low/70 border border-border-feather/60",
      }, summaryRow, listEl);

      const stepEls = {};
      let stepCount = 0;

      if (!autoExpanded) {
        listEl.classList.add("hidden");
      } else {
        arrow.style.transform = "rotate(180deg)";
      }

      box._upsertStep = (st) => {
        if (!st || !st.id) return;
        let row = stepEls[st.id];
        if (!row) {
          const iconEl = ui.icon("progress_activity", "text-[14px] mt-px shrink-0 text-primary animate-spin");
          const titleEl = ui.el("span", { class: "font-medium text-on-surface" }, st.title || st.id);
          const detailEl = ui.el("span", { class: "text-on-surface-variant break-words" }, st.detail || "");
          row = {
            iconEl, detailEl,
            el: ui.el("div", { class: "flex items-start gap-1.5 text-[12px] leading-relaxed" },
              iconEl,
              ui.el("div", { class: "flex flex-col min-w-0" }, titleEl, detailEl)),
          };
          stepEls[st.id] = row;
          listEl.append(row.el);
          stepCount += 1;
        }
        const style = STEP_STATUS_STYLE[st.status] || STEP_STATUS_STYLE.done;
        row.iconEl.textContent = style.icon;
        row.iconEl.className = `material-symbols-outlined text-[14px] mt-px shrink-0 ${style.cls}`;
        row.detailEl.textContent = st.detail || "";
        if (st.status === "doing") {
          summaryText.textContent = `思考过程 · ${st.title || ""}…`;
        }
      };

      box._finalize = (result) => {
        if (stepCount === 0) {
          box.classList.add("hidden");
          return;
        }
        listEl.classList.add("hidden");
        arrow.style.transform = "rotate(0deg)";
        if (result === "error") {
          summaryText.textContent = `思考过程 · 生成中断（${stepCount} 步）`;
        } else {
          summaryText.textContent = `已完成思考 · ${stepCount} 步`;
        }
      };

      return box;
    }

    function createMessageBubble(msg) {
      const isUser = msg.role === "user";

      if (isUser) {
        return ui.el("div", { class: "flex flex-col items-end gap-1 pl-6" },
          ui.el("div", {
            class: "px-3.5 py-2 rounded-2xl rounded-tr-xs bg-[#D9483B] text-white font-body-sm text-body-sm shadow-xs whitespace-pre-wrap leading-relaxed select-text",
          }, msg.content),
          msg.created_at && ui.el("span", { class: "text-[10px] text-on-surface-variant pr-1" }, msg.created_at.slice(11, 16))
        );
      }

      // AI 回复内容
      const taskLabel = TASK_LABELS[msg.task_type] || "伴写";
      const taskBadge = ui.el("span", {
        class: "text-[11px] px-1.5 py-0.5 rounded bg-primary/10 text-primary font-medium shrink-0",
      }, taskLabel);

      let candidates = [];
      if (Array.isArray(msg.candidates) && msg.candidates.length) {
        candidates = [...msg.candidates];
      } else {
        try {
          const meta = typeof msg.meta_json === "string" ? JSON.parse(msg.meta_json) : (msg.meta_json || {});
          if (Array.isArray(meta.candidates) && meta.candidates.length) {
            candidates = [...meta.candidates];
          }
        } catch (_) {}
      }
      if (!candidates.length && msg.content) {
        candidates = [msg.content];
      }

      let activeIndex = 0;
      let isCompare = false;
      let adoptedIdx = Number(msg.adopted) === 1 ? (msg._adoptedIndex !== undefined ? msg._adoptedIndex : 0) : -1;

      const tabsBar = ui.el("div", { class: "flex items-center gap-1 overflow-x-auto no-scrollbar pb-1 mb-1 border-b border-border-feather/40" });
      const compareToggleBtn = ui.el("button", {
        class: "flex items-center gap-0.5 px-2 py-0.5 rounded text-[11px] font-label-sm text-primary hover:bg-primary/10 cursor-pointer transition-colors shrink-0 ml-auto",
        title: "切换并排对比/单栏视图",
        onclick: () => {
          isCompare = !isCompare;
          renderBubbleBody();
        },
      }, ui.icon("view_column", "text-[14px]"), "并排对比");

      const headerRight = ui.el("div", { class: "flex items-center gap-1.5 shrink-0" });
      if (msg.created_at) {
        headerRight.append(ui.el("span", { class: "text-[10px] text-on-surface-variant" }, msg.created_at.slice(11, 16)));
      }

      const aiHeader = ui.el("div", { class: "flex items-center justify-between gap-1 pb-1 mb-1 border-b border-border-feather/60" },
        ui.el("div", { class: "flex items-center gap-1.5" },
          ui.icon("auto_awesome", "text-[14px] text-primary"),
          ui.el("span", { class: "font-label-sm text-[12px] font-semibold text-primary" }, "侍撰使"),
          taskBadge),
        headerRight
      );

      const contentSlot = ui.el("div", { class: "flex flex-col gap-2 min-h-0" });
      const actionsBox = ui.el("div", { class: "flex flex-wrap items-center gap-1 pt-2 mt-1 border-t border-border-feather/40" });

      const card = ui.el("div", {
        class: "flex flex-col p-3 rounded-2xl rounded-tl-xs bg-surface-container-lowest border border-border-feather shadow-xs mr-4 transition-shadow",
      }, aiHeader);

      let historySteps = null;
      try { historySteps = JSON.parse(msg.meta_json || "{}").steps || null; } catch (_) {}
      if (Array.isArray(historySteps) && historySteps.length) {
        const stepsBox = buildStepsBox(false);
        historySteps.forEach((st) => stepsBox._upsertStep(st));
        stepsBox._finalize(historySteps.some((s) => s.status === "error") ? "error" : "done");
        card.append(stepsBox);
      }

      card.append(tabsBar, contentSlot, actionsBox);

      function renderBubbleBody() {
        const cCount = candidates.length;
        if (cCount <= 1) {
          tabsBar.classList.add("hidden");
        } else {
          tabsBar.classList.remove("hidden");
          compareToggleBtn.innerHTML = "";
          compareToggleBtn.append(
            ui.icon(isCompare ? "tab" : "view_column", "text-[14px]"),
            isCompare ? "单栏视图" : "并排对比"
          );
        }

        tabsBar.innerHTML = "";
        if (cCount > 1 && !isCompare) {
          candidates.forEach((candText, idx) => {
            const isTabActive = idx === activeIndex;
            const isTabAdopted = idx === adoptedIdx;
            const tabBtn = ui.el("button", {
              class: `flex items-center gap-1 px-2.5 py-0.5 rounded-lg text-[11px] font-label-sm cursor-pointer transition-all ${
                isTabActive
                  ? "bg-primary text-on-primary font-semibold shadow-xs"
                  : "bg-surface-container hover:bg-surface-container-high text-on-surface-variant"
              }`,
              onclick: () => {
                activeIndex = idx;
                renderBubbleBody();
              },
            },
              ui.el("span", {}, `候选 ${idx + 1}`),
              isTabAdopted ? ui.icon("check", "text-[12px] text-green-500 font-bold") : null
            );
            tabsBar.append(tabBtn);
          });
          tabsBar.append(compareToggleBtn);
        } else if (cCount > 1 && isCompare) {
          tabsBar.append(ui.el("span", { class: "font-label-sm text-[11px] text-on-surface-variant" }, `并排对比（共 ${cCount} 个候选）`), compareToggleBtn);
        }

        contentSlot.innerHTML = "";
        actionsBox.innerHTML = "";

        if (cCount > 1 && isCompare) {
          const gridCls = cCount === 3 ? "grid grid-cols-1 md:grid-cols-3 gap-2" : "grid grid-cols-1 md:grid-cols-2 gap-2";
          const grid = ui.el("div", { class: gridCls });

          candidates.forEach((candText, idx) => {
            const isAdopted = idx === adoptedIdx;
            const colHeader = ui.el("div", { class: "flex items-center justify-between pb-1 border-b border-border-feather/50" },
              ui.el("span", { class: "font-label-sm text-[12px] font-semibold text-primary" }, `候选 ${idx + 1}`),
              isAdopted ? ui.el("span", { class: "text-[10px] px-1.5 py-0.2 rounded bg-primary/10 text-primary font-medium" }, "已采纳") : null
            );

            const colBody = ui.el("div", {
              class: "font-serif-content text-body-sm whitespace-pre-wrap leading-relaxed text-on-surface select-text p-2 rounded-lg bg-surface-container-lowest max-h-72 overflow-y-auto",
            }, candText || "（候选生成中…）");

            const colActions = ui.el("div", { class: "flex items-center gap-1 pt-1" });
            if (isAdopted) {
              colActions.append(
                ui.el("button", {
                  class: "px-2 py-0.5 rounded bg-surface-container hover:bg-error-container text-on-surface hover:text-on-error-container font-label-sm text-[11px] cursor-pointer",
                  onclick: async () => {
                    if (onUndoAdopt) await onUndoAdopt(msg);
                    adoptedIdx = -1;
                    msg.adopted = 0;
                    renderBubbleBody();
                  },
                }, ui.icon("undo", "text-[12px]"), "撤销")
              );
            } else {
              colActions.append(
                ui.el("button", {
                  class: "px-2.5 py-0.5 rounded bg-primary hover:bg-primary/90 text-on-primary font-label-sm text-[11px] font-medium shadow-xs cursor-pointer",
                  onclick: async () => {
                    if (onAdopt) {
                      const ok = await onAdopt(msg, candText);
                      if (ok) {
                        adoptedIdx = idx;
                        msg.adopted = 1;
                        msg._adoptedIndex = idx;
                        renderBubbleBody();
                      }
                    }
                  },
                }, ui.icon("check", "text-[12px]"), "采纳")
              );
            }

            colActions.append(
              ui.el("button", {
                class: "px-1.5 py-0.5 rounded hover:bg-surface-container text-on-surface-variant font-label-sm text-[11px] cursor-pointer",
                title: "复制此候选",
                onclick: async () => {
                  await navigator.clipboard.writeText(candText);
                  ui.toast("已复制到剪贴板", "ok");
                },
              }, ui.icon("content_copy", "text-[12px]"))
            );

            const colCard = ui.el("div", { class: "flex flex-col gap-1 p-2 rounded-xl bg-surface-container-low/60 border border-border-feather" },
              colHeader, colBody, colActions
            );
            grid.append(colCard);
          });

          contentSlot.append(grid);

          actionsBox.append(
            ui.el("button", {
              class: "flex items-center gap-1 px-2 py-1 rounded-lg hover:bg-surface-container text-on-surface-variant font-label-sm text-[12px] cursor-pointer",
              onclick: () => {
                if (onRetry) onRetry(msg.task_type || activeTask, "", "");
                else sendTask(msg.task_type || activeTask, "");
              },
            }, ui.icon("refresh", "text-[14px]"), "重试"),
            ui.el("button", {
              class: "flex items-center gap-1 px-2 py-1 rounded-lg hover:bg-surface-container text-on-surface-variant font-label-sm text-[12px] cursor-pointer",
              onclick: async () => {
                const ok = await ui.confirm("删除消息", "该生成结果将被移除，确定删除？", "删除", true);
                if (ok) {
                  card.remove();
                  messages = messages.filter((m) => m.id !== msg.id);
                  if (!messages.length) msgListEl.append(emptyPlaceholder);
                }
              },
            }, ui.icon("close", "text-[14px]"), "删除")
          );

        } else {
          // 单栏展示
          const currentText = candidates[activeIndex] || msg.content || "";
          const contentBox = ui.el("div", {
            class: "font-serif-content text-body-sm whitespace-pre-wrap leading-relaxed text-on-surface select-text",
          }, currentText);
          contentSlot.append(contentBox);

          const isAdopted = activeIndex === adoptedIdx;
          if (isAdopted) {
            actionsBox.append(
              ui.el("span", {
                class: "flex items-center gap-0.5 px-2 py-0.5 rounded-md bg-primary-container text-on-primary font-label-sm text-[11px]",
              }, ui.icon("check", "text-[13px]"), "已采纳"),
              ui.el("button", {
                class: "flex items-center gap-1 px-2.5 py-1 rounded-lg bg-surface-container hover:bg-error-container text-on-surface hover:text-on-error-container font-label-sm text-[12px] cursor-pointer",
                onclick: async () => {
                  if (onUndoAdopt) await onUndoAdopt(msg);
                  adoptedIdx = -1;
                  msg.adopted = 0;
                  renderBubbleBody();
                },
              }, ui.icon("undo", "text-[14px]"), "撤销采纳")
            );
          } else {
            actionsBox.append(
              ui.el("button", {
                class: "flex items-center gap-1 px-3 py-1 rounded-lg bg-primary hover:bg-primary/90 text-on-primary font-label-sm text-[12px] font-medium shadow-xs cursor-pointer",
                onclick: async () => {
                  if (onAdopt) {
                    const ok = await onAdopt(msg, currentText);
                    if (ok) {
                      adoptedIdx = activeIndex;
                      msg.adopted = 1;
                      msg._adoptedIndex = activeIndex;
                      renderBubbleBody();
                    }
                  }
                },
              }, ui.icon("check", "text-[14px]"), "采纳为正文")
            );
          }

          actionsBox.append(
            ui.el("button", {
              class: "flex items-center gap-1 px-2 py-1 rounded-lg hover:bg-surface-container text-on-surface-variant font-label-sm text-[12px] cursor-pointer",
              onclick: async () => {
                await navigator.clipboard.writeText(currentText);
                ui.toast("已复制到剪贴板", "ok");
              },
            }, ui.icon("content_copy", "text-[14px]"), "复制"),
            ui.el("button", {
              class: "flex items-center gap-1 px-2 py-1 rounded-lg hover:bg-surface-container text-on-surface-variant font-label-sm text-[12px] cursor-pointer",
              onclick: () => {
                if (onRetry) onRetry(msg.task_type || activeTask, "", "");
                else sendTask(msg.task_type || activeTask, "");
              },
            }, ui.icon("refresh", "text-[14px]"), "重试"),
            ui.el("button", {
              class: "flex items-center gap-1 px-2 py-1 rounded-lg hover:bg-surface-container text-on-surface-variant font-label-sm text-[12px] cursor-pointer",
              onclick: async () => {
                const ok = await ui.confirm("删除消息", "该生成结果将被移除，确定删除？", "删除", true);
                if (ok) {
                  card.remove();
                  messages = messages.filter((m) => m.id !== msg.id);
                  if (!messages.length) msgListEl.append(emptyPlaceholder);
                }
              },
            }, ui.icon("close", "text-[14px]"), "删除")
          );
        }
      }

      card._msg = msg;
      card._renderBubbleBody = renderBubbleBody;
      card._setCandidates = (cList) => {
        candidates = [...cList];
        card.classList.remove("streaming-caret");
        renderBubbleBody();
      };
      card._updateStreaming = (idx, text) => {
        while (candidates.length <= idx) candidates.push("");
        candidates[idx] = text;
        card.classList.add("streaming-caret");
        renderBubbleBody();
      };

      renderBubbleBody();
      return card;
    }

    /* ---------- API 交互与流式生成 ---------- */

    async function loadChapterHistory(chapterId) {
      if (!chapterId) {
        messages = [];
        renderMessages();
        return;
      }
      try {
        const res = await api.get(`/chat?chapter_id=${chapterId}`);
        currentSessionId = res.session ? res.session.id : null;
        messages = res.messages || [];
      } catch (e) {
        console.warn("加载聊天历史异常:", e);
        messages = [];
      }
      renderMessages();
      updateContextCount();
      updateSelectionQuote();
    }

    async function startNewSession() {
      const chapter = getChapter ? getChapter() : null;
      if (!chapter) {
        ui.toast("请先选择章节", "info");
        return;
      }
      try {
        const res = await api.post("/chat/session/new", { chapter_id: chapter.id });
        currentSessionId = res.session.id;
        messages = [];
        renderMessages();
        ui.toast("已开启新会话", "ok");
      } catch (e) {
        ui.toast("创建会话失败: " + e.message, "err");
      }
    }

    function setGeneratingState(generating) {
      isGenerating = generating;
      sendBtn.classList.toggle("hidden", generating);
      stopBtn.classList.toggle("hidden", !generating);
      inputArea.disabled = generating;
    }

    function handleStop() {
      if (abortCtrl) {
        abortCtrl.abort();
        abortCtrl = null;
      }
      setGeneratingState(false);
    }

    async function handleSend() {
      const text = inputArea.value.trim();
      if (isGenerating) return;
      await sendTask(activeTask, text);
    }

    async function sendTask(taskType, instructionText = "", customSelection = null) {
      const chapter = getChapter ? getChapter() : null;
      if (!chapter) {
        ui.toast("请先选择章节再进行创作", "err");
        return;
      }

      const selObj = customSelection !== null ? { text: customSelection } : (getSelection ? getSelection() : null);
      const selText = selObj && selObj.text ? selObj.text.trim() : "";
      const ctxOpts = getContextOptions ? getContextOptions() : {};

      const userDisplay = instructionText || (selText ? `针对选区（${selText.length}字）执行${TASK_LABELS[taskType] || taskType}` : `执行${TASK_LABELS[taskType] || taskType}`);

      // 立即在前端追加用户气泡
      const tempUserMsg = {
        role: "user",
        content: userDisplay,
        created_at: new Date().toISOString(),
      };
      if (!messages.length) msgListEl.innerHTML = "";
      messages.push(tempUserMsg);
      msgListEl.append(createMessageBubble(tempUserMsg));
      scrollToBottom();

      // 清空输入框与选区引用
      inputArea.value = "";
      if (clearSelection) clearSelection();
      updateSelectionQuote();

      // 创建并追加空的 AI 临时卡片（带流式光标）
      const numCands = aiCandidates || 1;
      let candTexts = new Array(numCands).fill("");
      const tempAiMsg = {
        id: "temp_" + Date.now(),
        role: "ai",
        content: "",
        candidates: candTexts,
        task_type: taskType,
        adopted: 0,
        created_at: new Date().toISOString(),
      };
      const aiCard = createMessageBubble(tempAiMsg);
      const stepsBox = buildStepsBox(true);
      aiCard.insertBefore(stepsBox, aiCard.children[1]); // 插入在 aiHeader 之后
      msgListEl.append(aiCard);
      scrollToBottom();

      setGeneratingState(true);
      abortCtrl = new AbortController();

      const payload = {
        chapter_id: chapter.id,
        message: instructionText,
        task: taskType,
        selection: selText,
        entity_ids: ctxOpts.entity_ids || [],
        include_current_chapter: ctxOpts.include_current_chapter !== false,
        include_prev_chapter: ctxOpts.include_prev_chapter !== false,
        include_outline: ctxOpts.include_outline !== false,
        include_style: ctxOpts.include_style !== false,
        length: aiLength || "2000",
        candidates: aiCandidates || 1,
        skill_id: window.aiActiveSkillId || null,
        stream: true,
      };

      try {
        const resp = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
          signal: abortCtrl.signal,
        });

        if (!resp.ok) {
          let errDetail = resp.statusText;
          try { errDetail = (await resp.json()).detail || errDetail; } catch (e) {}
          if (resp.status === 400 && errDetail.includes("未配置")) {
            const go = await ui.confirm("未配置 AI 接口", errDetail + "。是否前往设置？", "去设置");
            if (go) location.hash = "#/settings";
          } else {
            ui.toast(errDetail, "err");
          }
          aiCard.remove();
          setGeneratingState(false);
          return;
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";

        while (true) {
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

            if (evt.session_id) currentSessionId = evt.session_id;

            if (evt.step) {
              stepsBox._upsertStep(evt.step);
              scrollToBottom();
            }

            if (evt.candidate !== undefined) {
              const cIdx = evt.candidate;
              if (evt.delta !== undefined) {
                while (candTexts.length <= cIdx) candTexts.push("");
                candTexts[cIdx] += evt.delta;
                tempAiMsg.content = candTexts[0] || "";
                tempAiMsg.candidates = candTexts;
                aiCard._updateStreaming(cIdx, candTexts[cIdx]);
                scrollToBottom();
              }
            } else if (evt.delta !== undefined) {
              candTexts[0] += evt.delta;
              tempAiMsg.content = candTexts[0];
              tempAiMsg.candidates = candTexts;
              aiCard._updateStreaming(0, candTexts[0]);
              scrollToBottom();
            }

            if (evt.done) {
              if (evt.message_id) tempAiMsg.id = evt.message_id;
              if (Array.isArray(evt.candidates)) {
                candTexts = [...evt.candidates];
                tempAiMsg.candidates = candTexts;
                tempAiMsg.content = candTexts[0] || "";
              }
              stepsBox._finalize("done");
              aiCard._setCandidates(candTexts);
            }

            if (evt.error) {
              ui.toast(evt.error, "err");
              stepsBox._finalize("error");
            }
          }
        }

        // 流式正常结束
        stepsBox._finalize("done");
        tempAiMsg.content = candTexts[0] || "";
        tempAiMsg.candidates = candTexts;
        messages.push(tempAiMsg);
        aiCard._setCandidates(candTexts);
      } catch (e) {
        if (e.name !== "AbortError") {
          ui.toast("生成中断: " + e.message, "err");
        }
        stepsBox._finalize("error");
        if (!tempAiMsg.content) {
          aiCard.remove();
        } else {
          messages.push(tempAiMsg);
          aiCard._setCandidates(candTexts);
        }
      } finally {
        setGeneratingState(false);
        abortCtrl = null;
      }
    }

    return {
      el: rootEl,
      loadChapter: loadChapterHistory,
      startNewSession,
      sendQuickTask: (task, sel) => sendTask(task, "", sel),
      updateContextCount,
      updateSelectionQuote,
      getActiveTask: () => activeTask,
      setActiveTask,
    };
  }

  return { init };
})();
