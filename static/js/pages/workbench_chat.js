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
      contextDrawerEl,
      classicSettingsEl,
      onAdopt,
      onUndoAdopt,
      onRetry,
      isClassicMode,
      toggleClassicMode,
    } = options;

    let currentSessionId = null;
    let messages = [];
    let isGenerating = false;
    let abortCtrl = null;
    let activeTask = "continue"; // continue | expand | condense | polish

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

    const settingsToggleBtn = ui.el("button", {
      class: "w-8 h-8 rounded-lg flex items-center justify-center hover:bg-surface-container text-on-surface-variant hover:text-on-surface transition-colors cursor-pointer",
      title: "展开精调设置与经典模式",
      onclick: () => toggleSettingsDrawer(),
    }, ui.icon("settings", "text-[18px]"));

    const newChatBtn = ui.el("button", {
      class: "flex items-center gap-1 px-2.5 py-1 rounded-lg bg-surface-container hover:bg-surface-container-high text-primary font-label-sm text-label-sm transition-colors cursor-pointer",
      title: "新建会话，重置上下文轮次",
      onclick: () => startNewSession(),
    }, ui.icon("add_comment", "text-[15px]"), "新对话");

    const header = ui.el("div", {
      class: "flex items-center justify-between gap-2 p-space-sm bg-surface-container-lowest rounded-xl border border-border-feather shadow-[0_2px_10px_rgba(6,21,35,0.02)] shrink-0",
    }, headerTitle, ui.el("div", { class: "flex items-center gap-1 shrink-0" }, settingsToggleBtn, newChatBtn));

    // 2. 设置展开抽屉 (默认折叠)
    const classicModeCb = ui.el("input", {
      type: "checkbox",
      class: "rounded text-primary focus:ring-0 cursor-pointer w-4 h-4",
    });
    classicModeCb.checked = isClassicMode ? isClassicMode() : false;
    classicModeCb.onchange = () => {
      if (toggleClassicMode) toggleClassicMode(classicModeCb.checked);
    };

    const classicModeRow = ui.el("label", {
      class: "flex items-center justify-between p-2 rounded-lg bg-surface-container-low hover:bg-surface-container cursor-pointer transition-colors",
    },
      ui.el("div", { class: "flex flex-col" },
        ui.el("span", { class: "font-label-sm text-label-sm font-medium text-on-surface" }, "经典多候选对比模式"),
        ui.el("span", { class: "text-[11px] text-on-surface-variant" }, "开启后显示并排候选卡片与行级 Diff 对比")),
      classicModeCb
    );

    const settingsDrawer = ui.el("div", {
      class: "hidden flex flex-col gap-2 p-3 bg-surface-container-lowest rounded-xl border border-border-feather shadow-sm text-body-sm transition-all",
    },
      ui.el("div", { class: "flex items-center justify-between text-on-surface-variant font-label-sm pb-1 border-b border-border-feather" },
        ui.el("span", { class: "font-semibold text-primary" }, "修撰使精调选项"),
        ui.el("button", { class: "hover:text-primary", onclick: () => toggleSettingsDrawer(false) }, ui.icon("close", "text-[16px]"))),
      classicModeRow,
      classicSettingsEl || ui.el("div")
    );

    function toggleSettingsDrawer(show) {
      const willShow = show !== undefined ? show : settingsDrawer.classList.contains("hidden");
      settingsDrawer.classList.toggle("hidden", !willShow);
      settingsToggleBtn.classList.toggle("bg-surface-container-high", willShow);
    }

    // 3. 上下文折叠栏 (显示“已挂载 N 项上下文”，点击可展开查看设定与细纲明细)
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
    const taskChips = [
      { id: "continue", label: "续写" },
      { id: "expand",   label: "扩写" },
      { id: "condense", label: "缩写" },
      { id: "polish",   label: "改写" },
    ];

    const taskChipEls = {};
    const taskChipsBar = ui.el("div", { class: "flex flex-wrap items-center gap-1.5 pb-1" });

    taskChips.forEach((tc) => {
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

    /* 当前任务的技能选择菜单（数据来自 workbench.js 的 aiSkillBridge，按任务绑定） */
    const skillMenuLabel = ui.el("span", { class: "max-w-[64px] truncate" }, "自动");
    const skillMenuBox = ui.el("div", {
      class: "hidden absolute right-0 bottom-full mb-1 w-52 max-h-60 overflow-y-auto rounded-xl bg-surface-container-lowest border border-border-feather shadow-[0_8px_28px_rgba(6,21,35,0.14)] p-1 z-30 flex-col gap-0.5",
    });
    const skillMenuBtn = ui.el("button", {
      class: "flex items-center gap-0.5 px-2 py-1 rounded-lg text-[12px] font-label-sm cursor-pointer transition-all border shrink-0 bg-surface-container hover:bg-surface-container-high text-on-surface-variant border-transparent",
      title: "为当前任务选择写作技能",
      onclick: (e) => { e.stopPropagation(); toggleSkillMenu(); },
    }, ui.icon("tune", "text-[14px] text-primary"), skillMenuLabel, ui.icon("keyboard_arrow_up", "text-[14px]"));
    const skillMenuWrap = ui.el("div", { class: "relative ml-auto shrink-0" }, skillMenuBtn, skillMenuBox);
    taskChipsBar.append(skillMenuWrap);

    function updateSkillMenuLabel() {
      const bridge = window.aiSkillBridge;
      if (!bridge) { skillMenuWrap.classList.add("hidden"); return; }
      skillMenuWrap.classList.remove("hidden");
      const id = bridge.get(activeTask);
      const s = id ? bridge.listForTask(activeTask).find((x) => x.id === id) : null;
      skillMenuLabel.textContent = s ? s.title : "自动";
      skillMenuBtn.title = s ? `当前任务技能：${s.title}` : "自动匹配内置技能（点击更换）";
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
        skillMenuBox.append(ui.el("div", { class: "px-2 py-1 text-[11px] text-on-surface-variant" }, "当前任务暂无其他可用技能"));
      }
      skillMenuBox.classList.remove("hidden");
      skillMenuBox.classList.add("flex");
    }
    document.addEventListener("click", closeSkillMenu);

    function setActiveTask(task) {
      activeTask = task;
      taskChips.forEach((tc) => {
        const el = taskChipEls[tc.id];
        if (tc.id === activeTask) {
          el.className = "px-2.5 py-1 rounded-lg text-[12px] font-label-sm cursor-pointer transition-all shrink-0 bg-primary text-on-primary border-primary font-semibold shadow-xs";
        } else {
          el.className = "px-2.5 py-1 rounded-lg text-[12px] font-label-sm cursor-pointer transition-all shrink-0 bg-surface-container hover:bg-surface-container-high text-on-surface-variant border-transparent";
        }
      });
      if (window.aiSkillBridge) window.aiSkillBridge.syncWindow(task);
      closeSkillMenu();
      updateSkillMenuLabel();
    }
    setActiveTask("continue");

    // 选区引用条
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
        selQuoteBox.querySelector(".sel-count").textContent = String(count);
        selQuoteBox.classList.remove("hidden");
        selQuoteBox.classList.add("flex");
      } else {
        selQuoteBox.classList.add("hidden");
        selQuoteBox.classList.remove("flex");
      }
    }

    // 输入框与发送按钮
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

    // 输入区容器
    const inputBar = ui.el("div", {
      class: "flex flex-col gap-1.5 p-2.5 bg-surface-container-lowest rounded-xl border border-border-feather shadow-[0_2px_12px_rgba(6,21,35,0.04)] shrink-0",
    },
      taskChipsBar,
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
      settingsDrawer,
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
        // 用户消息气泡：右对齐，使用朱砂强调暖色调
        return ui.el("div", { class: "flex flex-col items-end gap-1 pl-6" },
          ui.el("div", {
            class: "px-3.5 py-2 rounded-2xl rounded-tr-xs bg-[#D9483B] text-white font-body-sm text-body-sm shadow-xs whitespace-pre-wrap leading-relaxed select-text",
          }, msg.content),
          msg.created_at && ui.el("span", { class: "text-[10px] text-on-surface-variant pr-1" }, msg.created_at.slice(11, 16))
        );
      }

      // AI 回复气泡：左对齐，文人书斋墨色边框卡片
      const taskLabel = TASK_LABELS[msg.task_type] || "修撰";
      const taskBadge = ui.el("span", {
        class: "text-[11px] px-1.5 py-0.5 rounded bg-primary/10 text-primary font-medium shrink-0",
      }, taskLabel);

      const aiHeader = ui.el("div", { class: "flex items-center justify-between gap-1 pb-1 mb-1 border-b border-border-feather/60" },
        ui.el("div", { class: "flex items-center gap-1.5" },
          ui.icon("auto_awesome", "text-[14px] text-primary"),
          ui.el("span", { class: "font-label-sm text-[12px] font-semibold text-primary" }, "修撰使"),
          taskBadge),
        msg.created_at && ui.el("span", { class: "text-[10px] text-on-surface-variant" }, msg.created_at.slice(11, 16))
      );

      const contentBox = ui.el("div", {
        class: "font-serif-content text-body-sm whitespace-pre-wrap leading-relaxed text-on-surface select-text",
      }, msg.content || "");

      const actionsBox = ui.el("div", {
        class: "flex flex-wrap items-center gap-1 pt-2 mt-1 border-t border-border-feather/40",
      });

      const card = ui.el("div", {
        class: "flex flex-col p-3 rounded-2xl rounded-tl-xs bg-surface-container-lowest border border-border-feather shadow-xs mr-4 transition-shadow",
      }, aiHeader, contentBox, actionsBox);

      // 历史消息回放思考过程（折叠态）
      let historySteps = null;
      try { historySteps = JSON.parse(msg.meta_json || "{}").steps || null; } catch (_) { /* 旧消息无 meta */ }
      if (Array.isArray(historySteps) && historySteps.length) {
        const stepsBox = buildStepsBox(false);
        historySteps.forEach((st) => stepsBox._upsertStep(st));
        stepsBox._finalize(historySteps.some((s) => s.status === "error") ? "error" : "done");
        card.insertBefore(stepsBox, contentBox);
      }

      card._msg = msg;
      card._contentBox = contentBox;
      card._actionsBox = actionsBox;

      updateBubbleActions(card);
      return card;
    }

    function updateBubbleActions(card) {
      const msg = card._msg;
      const actions = card._actionsBox;
      actions.innerHTML = "";
      if (!msg.content) return;

      const isAdopted = Number(msg.adopted) === 1;

      // 采纳 / 已采纳按钮
      if (isAdopted) {
        const undoBtn = ui.el("button", {
          class: "flex items-center gap-1 px-2.5 py-1 rounded-lg bg-surface-container hover:bg-error-container text-on-surface hover:text-on-error-container font-label-sm text-[12px] transition-colors cursor-pointer",
          title: "正文已恢复或点击撤销",
          onclick: async () => {
            if (onUndoAdopt) await onUndoAdopt(msg);
            msg.adopted = 0;
            updateBubbleActions(card);
          },
        }, ui.icon("undo", "text-[14px]"), "撤销采纳");

        const statusTag = ui.el("span", {
          class: "flex items-center gap-0.5 px-2 py-0.5 rounded-md bg-primary-container text-on-primary font-label-sm text-[11px]",
        }, ui.icon("check", "text-[13px]"), "已采纳");

        actions.append(statusTag, undoBtn);
      } else {
        const adoptBtn = ui.el("button", {
          class: "flex items-center gap-1 px-3 py-1 rounded-lg bg-primary hover:bg-primary/90 text-on-primary font-label-sm text-[12px] font-medium shadow-xs transition-colors cursor-pointer",
          title: "确认后将内容写入正文（写入前自动留存版本快照）",
          onclick: async () => {
            if (onAdopt) {
              const ok = await onAdopt(msg, msg.content);
              if (ok) {
                msg.adopted = 1;
                updateBubbleActions(card);
              }
            }
          },
        }, ui.icon("check", "text-[14px]"), "采纳");

        actions.append(adoptBtn);
      }

      // 复制按钮
      actions.append(ui.el("button", {
        class: "flex items-center gap-1 px-2 py-1 rounded-lg hover:bg-surface-container text-on-surface-variant font-label-sm text-[12px] transition-colors cursor-pointer",
        onclick: async () => {
          await navigator.clipboard.writeText(msg.content);
          ui.toast("已复制到剪贴板", "ok");
        },
      }, ui.icon("content_copy", "text-[14px]"), "复制"));

      // 重试按钮
      actions.append(ui.el("button", {
        class: "flex items-center gap-1 px-2 py-1 rounded-lg hover:bg-surface-container text-on-surface-variant font-label-sm text-[12px] transition-colors cursor-pointer",
        onclick: () => {
          if (onRetry) onRetry(msg.task_type || activeTask, "", "");
          else sendTask(msg.task_type || activeTask, "");
        },
      }, ui.icon("refresh", "text-[14px]"), "重试"));

      // 放弃按钮
      actions.append(ui.el("button", {
        class: "flex items-center gap-1 px-2 py-1 rounded-lg hover:bg-surface-container text-on-surface-variant font-label-sm text-[12px] transition-colors cursor-pointer",
        onclick: async () => {
          const ok = await ui.confirm("放弃此条", "该条建议将被移除，确定放弃？", "放弃", true);
          if (ok) {
            card.remove();
            messages = messages.filter((m) => m.id !== msg.id);
            if (!messages.length) msgListEl.append(emptyPlaceholder);
          }
        },
      }, ui.icon("close", "text-[14px]"), "放弃"));
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
      const contextText = getContext ? getContext() : "";

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
      const tempAiMsg = {
        id: "temp_" + Date.now(),
        role: "ai",
        content: "",
        task_type: taskType,
        adopted: 0,
        created_at: new Date().toISOString(),
      };
      const aiCard = createMessageBubble(tempAiMsg);
      aiCard._contentBox.classList.add("streaming-caret");
      const stepsBox = buildStepsBox(true);
      aiCard.insertBefore(stepsBox, aiCard._contentBox);
      msgListEl.append(aiCard);
      scrollToBottom();

      setGeneratingState(true);
      abortCtrl = new AbortController();

      const payload = {
        chapter_id: chapter.id,
        message: instructionText,
        task: taskType,
        selection: selText,
        context: contextText,
        length: window.aiLengthPreference || "medium",
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
        let fullContent = "";

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

            if (evt.delta !== undefined) {
              fullContent += evt.delta;
              tempAiMsg.content = fullContent;
              aiCard._contentBox.textContent = fullContent;
              scrollToBottom();
            }

            if (evt.done) {
              if (evt.message_id) tempAiMsg.id = evt.message_id;
              aiCard._contentBox.classList.remove("streaming-caret");
              stepsBox._finalize("done");
              updateBubbleActions(aiCard);
            }

            if (evt.error) {
              ui.toast(evt.error, "err");
              aiCard._contentBox.classList.remove("streaming-caret");
              stepsBox._finalize("error");
            }
          }
        }

        // 流式正常结束
        aiCard._contentBox.classList.remove("streaming-caret");
        stepsBox._finalize("done");
        tempAiMsg.content = fullContent;
        messages.push(tempAiMsg);
        updateBubbleActions(aiCard);
      } catch (e) {
        if (e.name !== "AbortError") {
          ui.toast("生成中断: " + e.message, "err");
        }
        aiCard._contentBox.classList.remove("streaming-caret");
        stepsBox._finalize("error");
        if (!tempAiMsg.content) {
          aiCard.remove();
        } else {
          messages.push(tempAiMsg);
          updateBubbleActions(aiCard);
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
