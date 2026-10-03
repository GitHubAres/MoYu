/* 系统设置页（对应设计稿 _10，本地版裁剪：去掉云端同步/隐私项，加 AI 配置与备份） */
registerPage("settings", async (view) => {
  ui.setCrumb("系统设置");

  let settings = {};
  try { settings = await api.get("/settings"); } catch (e) { ui.toast(e.message, "err"); }

  async function save(values, msg = "已保存") {
    try {
      settings = await api.patch("/settings", { values });
      ui.toast(msg, "ok");
      ui.refreshStats();
    } catch (e) { ui.toast(e.message, "err"); }
  }

  function section(icon, title, desc, ...children) {
    return ui.el("section", { class: "p-space-xl rounded-xl bg-surface-container-lowest shadow-sm flex flex-col gap-space-lg" },
      ui.el("div", { class: "flex flex-col gap-1" },
        ui.el("div", { class: "flex items-center gap-space-sm" },
          ui.el("span", { class: "w-2.5 h-2.5 rounded-full bg-secondary" }),
          ui.el("h2", { class: "font-headline-md text-headline-md text-primary font-semibold" }, title),
          icon && ui.icon(icon, "text-[20px] text-on-surface-variant")),
        desc && ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant" }, desc)),
      ...children);
  }

  /* ---------- 1. 主题配色 ---------- */
  const THEMES = [
    { key: "light", name: "素纸晨光", tag: "默认浅色", desc: "清朗平实，字字如印古宣", bg: "#F6F8FA", dot: "#1B2A38", bar: "#e4e2e3", lines: "rgba(68,71,76,0.2)", chip: "素墨", chipCls: "bg-secondary-container text-on-secondary-container" },
    { key: "dark", name: "黛蓝夜读", tag: "深色沉浸", desc: "幽玄静谧，深夜灵思泉涌", bg: "#061523", dot: "#b4c5ff", bar: "#1b2a38", lines: "rgba(234,231,233,0.3)", chip: "星野", chipCls: "bg-secondary text-on-secondary" },
    { key: "paper", name: "古籍羊皮纸", tag: "温润暖黄", desc: "柔和护眼，如翻黄卷残篇", bg: "#FAF4EB", dot: "#211002", bar: "#ffdcc0", lines: "rgba(90,66,45,0.2)", chip: "沉香", chipCls: "bg-tertiary-container text-on-tertiary-container" },
  ];
  const themeCards = {};
  function renderThemes() {
    for (const t of THEMES) {
      const on = (settings.theme || "light") === t.key;
      themeCards[t.key].className = `cursor-pointer relative flex flex-col p-space-md rounded-xl transition-all duration-200 ${
        on ? "bg-surface-container-lowest shadow-md ring-2 ring-secondary" : "bg-surface-container-low hover:bg-surface-container"}`;
      themeCards[t.key].querySelector(".theme-check").className =
        `theme-check absolute top-3 right-3 w-5 h-5 rounded-full flex items-center justify-center shadow-sm ${
          on ? "bg-secondary text-on-secondary" : "hidden"}`;
    }
  }
  for (const t of THEMES) {
    themeCards[t.key] = ui.el("div", {
      class: "",
      onclick: () => { ui.applyTheme(t.key); settings.theme = t.key; renderThemes(); save({ theme: t.key }, "主题已切换"); },
    },
      ui.el("div", { class: "theme-check hidden" }, ui.icon("check", "text-[14px]")),
      ui.el("div", { class: "w-full h-24 rounded-lg p-space-sm flex flex-col justify-between overflow-hidden shadow-inner", style: `background:${t.bg}` },
        ui.el("div", { class: "flex items-center gap-1.5" },
          ui.el("span", { class: "w-2 h-2 rounded-full", style: `background:${t.dot}` }),
          ui.el("span", { class: "w-10 h-2 rounded", style: `background:${t.bar}` })),
        ui.el("div", { class: "flex flex-col gap-1" },
          ui.el("div", { class: "w-3/4 h-2 rounded", style: `background:${t.lines}` }),
          ui.el("div", { class: "w-1/2 h-2 rounded", style: `background:${t.lines}` })),
        ui.el("span", { class: `self-end px-2 py-0.5 rounded text-[9px] font-medium ${t.chipCls}` }, t.chip)),
      ui.el("div", { class: "mt-space-sm flex flex-col" },
        ui.el("div", { class: "flex items-center justify-between" },
          ui.el("span", { class: "font-headline-sm text-headline-sm text-primary font-medium" }, t.name),
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, t.tag)),
        ui.el("span", { class: "font-body-sm text-body-sm text-on-surface-variant mt-0.5" }, t.desc)));
  }

  /* ---------- 2. 字体与版面 ---------- */
  const previewText = ui.el("p", {
    class: "font-display text-primary pt-space-xs transition-all duration-150",
    style: `font-size:${settings.editor_font_size || 18}px; line-height:${settings.editor_line_height || 1.9}`,
  }, "林夜站在星陨阁的残檐之下，冰棱正在以不可思议的速率凝结。他抬起右手，袖口隐现的那枚骨瓷戒指忽明忽暗。风穿过回廊时发出近似笙簧的低鸣，他明白，今夜在天权星坠落之前，必须在残卷上烙下最后一笔回溯符印。");

  function sliderCard(label, key, min, max, step, unit, onInput) {
    const val = ui.el("span", { class: "font-headline-sm text-headline-sm text-secondary font-semibold" });
    const input = ui.el("input", {
      type: "range", min, max, step,
      class: "w-full h-1.5 bg-surface-container-highest rounded-lg appearance-none cursor-pointer accent-secondary",
    });
    input.value = settings[key];
    const show = () => { val.textContent = `${input.value} ${unit}`; };
    input.addEventListener("input", () => { show(); onInput && onInput(input.value); });
    input.addEventListener("change", () => save({ [key]: String(input.value) }));
    show();
    return ui.el("div", { class: "flex flex-col gap-space-sm p-space-md rounded-xl bg-surface-container-low" },
      ui.el("div", { class: "flex items-center justify-between" },
        ui.el("span", { class: "font-label-md text-label-md text-primary font-medium" }, label), val),
      input,
      ui.el("div", { class: "flex justify-between font-label-sm text-label-sm text-outline" },
        ui.el("span", {}, `${min}${unit}`), ui.el("span", {}, `${max}${unit}`)));
  }

  const goalInput = ui.el("input", {
    type: "number", min: "100", step: "100",
    class: "w-32 px-3 py-1.5 rounded-lg bg-surface-container-lowest border border-border-feather focus:border-primary outline-none font-body-sm text-body-sm text-right",
    value: settings.daily_word_goal || "5000",
  });
  goalInput.addEventListener("change", () => save({ daily_word_goal: String(Math.max(0, Number(goalInput.value) || 0)) }));

  /* ---------- 3. AI 模型配置 ---------- */
  const inputCls = "w-full px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-sm text-body-sm";

  /* 主流厂商预设：选中后联动填充 Base URL 与推荐模型名，字段仍可手动修改 */
  const AI_PROVIDERS = [
    { key: "deepseek", name: "DeepSeek（深度求索）", base_url: "https://api.deepseek.com/v1", model: "deepseek-chat", models: "deepseek-chat / deepseek-reasoner", site: "platform.deepseek.com" },
    { key: "kimi", name: "Kimi（月之暗面）", base_url: "https://api.moonshot.cn/v1", model: "kimi-k2.6", models: "kimi-k2.6 / kimi-k2-0905-preview / moonshot-v1-8k", site: "platform.moonshot.cn" },
    { key: "zhipu", name: "智谱 GLM", base_url: "https://open.bigmodel.cn/api/paas/v4", model: "glm-4-flash", models: "glm-4-flash / glm-4-plus", site: "open.bigmodel.cn" },
    { key: "qwen", name: "通义千问（阿里云）", base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1", model: "qwen-plus", models: "qwen-plus / qwen-max", site: "bailian.console.aliyun.com" },
    { key: "openai", name: "OpenAI", base_url: "https://api.openai.com/v1", model: "gpt-4o-mini", models: "gpt-4o-mini / gpt-4o", site: "platform.openai.com" },
    { key: "custom", name: "自定义", base_url: "", model: "", models: "", site: "" },
  ];

  const aiUrl = ui.el("input", { class: inputCls, placeholder: "https://api.openai.com/v1", value: settings.ai_base_url || "" });
  const aiKey = ui.el("input", { class: inputCls, type: "password", placeholder: "sk-…", value: settings.ai_api_key || "" });
  const aiModel = ui.el("input", { class: inputCls, placeholder: "如 gpt-4o-mini / deepseek-chat", value: settings.ai_model || "" });
  aiUrl.addEventListener("change", () => save({ ai_base_url: aiUrl.value.trim() }));
  aiKey.addEventListener("change", () => save({ ai_api_key: aiKey.value.trim() }));
  aiModel.addEventListener("change", () => save({ ai_model: aiModel.value.trim() }));

  /* ---------- 3.1 AI ?????? (ModelPicker) ---------- */
  function createModelPicker(inputEl, urlEl, keyEl, providerSel, onSelect) {
    const wrap = ui.el("div", { class: "relative w-full" });
    
    // ?????????????????
    const inputGroup = ui.el("div", { class: "relative flex items-center w-full" });
    inputEl.className = inputCls + " pr-20";
    
    const browseBtn = ui.el("button", {
      type: "button",
      class: "absolute right-1 top-1/2 -translate-y-1/2 flex items-center gap-1 px-2.5 py-1 rounded-md bg-surface-container hover:bg-surface-container-high text-on-surface font-label-sm text-xs transition-colors cursor-pointer",
      onclick: (e) => {
        e.stopPropagation();
        toggleDropdown();
      }
    }, ui.icon("travel_explore", "text-[16px]"), "??");

    inputGroup.append(inputEl, browseBtn);
    wrap.append(inputGroup);

    // ??????
    const dropdown = ui.el("div", {
      class: "absolute left-0 top-full mt-1.5 w-full z-50 rounded-xl bg-surface-container-lowest border border-outline-variant/60 shadow-[0_8px_24px_rgba(27,42,56,0.15)] flex flex-col overflow-hidden max-h-80 text-xs animate-in fade-in zoom-in-95 duration-100",
      style: "display: none;"
    });
    wrap.append(dropdown);

    let isOpen = false;
    let loading = false;
    let modelsList = [];
    let activeIndex = -1;
    let currentSource = "remote";
    let statusMessage = "";

    function close() {
      if (!isOpen) return;
      isOpen = false;
      dropdown.style.display = "none";
      document.removeEventListener("click", onDocClick);
      document.removeEventListener("keydown", onKeyDown);
    }

    function onDocClick(e) {
      if (!wrap.contains(e.target)) close();
    }

    function onKeyDown(e) {
      if (!isOpen) return;
      if (e.key === "Escape") {
        e.preventDefault();
        close();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        if (modelsList.length > 0) {
          activeIndex = (activeIndex + 1) % modelsList.length;
          renderItems();
        }
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (modelsList.length > 0) {
          activeIndex = (activeIndex - 1 + modelsList.length) % modelsList.length;
          renderItems();
        }
      } else if (e.key === "Enter") {
        if (activeIndex >= 0 && activeIndex < modelsList.length) {
          e.preventDefault();
          selectModel(modelsList[activeIndex].id);
        }
      }
    }

    async function toggleDropdown() {
      if (isOpen) {
        close();
        return;
      }
      isOpen = true;
      dropdown.style.display = "flex";
      document.addEventListener("click", onDocClick);
      document.addEventListener("keydown", onKeyDown);

      // ????????? URL ? Key
      await save({
        ai_base_url: urlEl.value.trim(),
        ai_api_key: keyEl.value.trim(),
        ai_model: inputEl.value.trim()
      });

      await fetchModels(false);
    }

    async function fetchModels(forceRefresh = false) {
      loading = true;
      renderLoading();
      try {
        const res = await api.get(`/ai/models?refresh=${forceRefresh ? 1 : 0}`);
        loading = false;
        if (res.ok && res.models && res.models.length > 0) {
          modelsList = res.models;
          currentSource = res.source || "remote";
          statusMessage = res.message || "";
          // ???????????????????
          const curVal = inputEl.value.trim();
          const foundIdx = modelsList.findIndex(m => m.id === curVal);
          if (foundIdx > 0) {
            const item = modelsList.splice(foundIdx, 1)[0];
            modelsList.unshift(item);
          }
          activeIndex = modelsList.findIndex(m => m.id === curVal);
          if (activeIndex < 0) activeIndex = 0;
          renderList();
        } else {
          // ?? L2?????
          fallbackToPresets(res.message || "???????????");
        }
      } catch (err) {
        loading = false;
        fallbackToPresets(err.message || "????????");
      }
    }

    function fallbackToPresets(errMsg) {
      const p = AI_PROVIDERS.find(x => x.key === providerSel.value);
      if (p && p.key !== "custom" && p.models) {
        const rawPresets = p.models.split("/").map(s => s.trim()).filter(Boolean);
        modelsList = rawPresets.map(id => ({ id, owned_by: p.name }));
        currentSource = "preset";
        statusMessage = "????????????????";
        const curVal = inputEl.value.trim();
        activeIndex = modelsList.findIndex(m => m.id === curVal);
        renderList();
      } else {
        renderError(errMsg);
      }
    }

    function renderLoading() {
      dropdown.innerHTML = "";
      dropdown.append(ui.el("div", { class: "p-4 flex items-center justify-center gap-2 text-on-surface-variant font-label-sm" },
        ui.icon("progress_activity", "text-[18px] animate-spin text-primary"),
        ui.el("span", {}, "????????????")
      ));
    }

    function renderError(msg) {
      dropdown.innerHTML = "";
      const box = ui.el("div", { class: "p-3 space-y-2 text-center" });
      box.append(
        ui.el("div", { class: "text-error font-label-sm flex items-center justify-center gap-1" },
          ui.icon("error_outline", "text-[16px]"),
          ui.el("span", {}, msg)
        ),
        ui.el("div", { class: "flex items-center justify-center gap-2 pt-1" },
          ui.el("button", {
            type: "button",
            class: "px-3 py-1 rounded bg-surface-container hover:bg-surface-container-high text-xs text-on-surface cursor-pointer",
            onclick: () => fetchModels(true)
          }, "????"),
          ui.el("button", {
            type: "button",
            class: "px-3 py-1 rounded bg-primary text-on-primary text-xs cursor-pointer",
            onclick: close
          }, "????")
        )
      );
      dropdown.append(box);
    }

    function selectModel(mId) {
      inputEl.value = mId;
      if (onSelect) onSelect(mId);
      close();
    }

    function renderList() {
      dropdown.innerHTML = "";

      // ???????????
      const header = ui.el("div", { class: "flex items-center justify-between px-3 py-1.5 bg-surface-container-low border-b border-outline-variant/40 shrink-0" });
      const tipText = currentSource === "preset"
        ? (statusMessage || "?????????")
        : (currentSource === "cache" ? "??????24h???" : "????????");
      header.append(
        ui.el("span", { class: "text-[11px] text-outline truncate", title: tipText }, tipText),
        ui.el("button", {
          type: "button",
          class: "p-1 rounded text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors cursor-pointer",
          title: "????",
          onclick: (e) => {
            e.stopPropagation();
            fetchModels(true);
          }
        }, ui.icon("refresh", "text-[14px]"))
      );
      dropdown.append(header);

      const listBox = ui.el("div", { class: "flex-1 overflow-y-auto divide-y divide-outline-variant/30 py-1" });
      dropdown.append(listBox);
      renderItemsInto(listBox);
    }

    function renderItems() {
      const listBox = dropdown.querySelector(".overflow-y-auto");
      if (listBox) renderItemsInto(listBox);
    }

    function renderItemsInto(listBox) {
      listBox.innerHTML = "";
      const curVal = inputEl.value.trim();
      modelsList.forEach((m, idx) => {
        const isSelected = m.id === curVal;
        const isActive = idx === activeIndex;
        const itemRow = ui.el("div", {
          class: `px-3 py-2 flex items-center justify-between cursor-pointer transition-colors ${
            isActive ? "bg-surface-container-high" : (isSelected ? "bg-surface-container-low" : "hover:bg-surface-container")
          }`,
          onclick: (e) => {
            e.stopPropagation();
            selectModel(m.id);
          },
          onmouseenter: () => {
            activeIndex = idx;
            renderItems();
          }
        },
          ui.el("div", { class: "flex items-center gap-2 overflow-hidden" },
            isSelected ? ui.icon("check", "text-[16px] text-primary shrink-0") : ui.el("span", { class: "w-4 shrink-0" }),
            ui.el("div", { class: "flex flex-col overflow-hidden" },
              ui.el("span", { class: "font-mono font-medium text-on-surface truncate" }, m.id),
              m.owned_by ? ui.el("span", { class: "text-[10px] text-outline truncate" }, m.owned_by) : null
            )
          )
        );
        if (isActive) {
          setTimeout(() => itemRow.scrollIntoView({ block: "nearest" }), 0);
        }
        listBox.append(itemRow);
      });
    }

    return wrap;
  }



  const providerHint = ui.el("div", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "");
  const providerSelect = ui.el("select", { class: inputCls + " cursor-pointer" },
    AI_PROVIDERS.map((p) => ui.el("option", { value: p.key }, p.name)));

  function renderProviderHint() {
    const p = AI_PROVIDERS.find((x) => x.key === providerSelect.value);
    if (p && p.key !== "custom") {
      providerHint.textContent = `常用模型：${p.models} · 申请 API Key：${p.site}（字段均为预填，可继续修改）`;
    } else {
      providerHint.textContent = "自定义接口需兼容 OpenAI Chat Completions 协议（/v1/chat/completions）。";
    }
  }

  providerSelect.addEventListener("change", () => {
    const p = AI_PROVIDERS.find((x) => x.key === providerSelect.value);
    if (p && p.key !== "custom") {
      aiUrl.value = p.base_url;
      aiModel.value = p.model;
      save({ ai_base_url: p.base_url, ai_model: p.model }, `已切换为 ${p.name}，请填写 API Key 后测试连接`);
    }
    renderProviderHint();
  });

  /* 加载时按已保存的 Base URL 回显服务商，未命中则为自定义 */
  const matched = AI_PROVIDERS.find((p) => p.key !== "custom" && p.base_url === (settings.ai_base_url || "").trim());
  providerSelect.value = matched ? matched.key : "custom";
  renderProviderHint();

  const modelPickerWrap = createModelPicker(aiModel, aiUrl, aiKey, providerSelect, (mId) => {
    save({ ai_model: mId }, `??????${mId}`);
  });


  const testResult = ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "尚未测试");
  const testBtn = ui.el("button", {
    class: "flex items-center gap-1.5 px-space-md py-2 rounded-lg bg-primary text-on-primary hover:bg-primary-container transition-all font-label-md text-label-md disabled:opacity-50",
    onclick: async () => {
      testBtn.disabled = true;
      testResult.textContent = "正在测试连接…";
      testResult.className = "font-label-sm text-label-sm text-on-surface-variant";
      try {
        await save({ ai_base_url: aiUrl.value.trim(), ai_api_key: aiKey.value.trim(), ai_model: aiModel.value.trim() }, "配置已保存");
        const r = await api.post("/ai/test");
        testResult.textContent = r.message || (r.ok ? "连接成功" : "连接失败");
        testResult.className = `font-label-sm text-label-sm ${r.ok ? "text-emerald-700" : "text-error"}`;
      } catch (e) {
        testResult.textContent = e.message;
        testResult.className = "font-label-sm text-label-sm text-error";
      }
      testBtn.disabled = false;
    },
  }, ui.icon("cable", "text-[18px]"), "测试连接");

  const tokenBox = ui.el("span", { class: "font-display text-primary text-[28px] font-semibold" },
    Number(settings.token_used || 0).toLocaleString());

  /* 任务级模型覆盖：各写作任务可单独指定 Base URL 与模型名，留空跟随上方主配置 */
  const AI_TASKS = [
    ["continue", "续写"], ["expand", "扩写"], ["condense", "缩写"],
    ["polish", "润色"], ["outline", "大纲"], ["check", "设定核查"],
  ];
  const routeBody = ui.el("div", { class: "flex flex-col gap-space-md px-space-md pb-space-md", style: "display:none" },
    AI_TASKS.map(([task, label]) => {
      const modelIn = ui.el("input", {
        class: inputCls, placeholder: "模型名（留空跟随主配置）",
        value: settings[`route_${task}_model`] || "",
      });
      const urlIn = ui.el("input", {
        class: inputCls, placeholder: "Base URL（留空跟随主配置）",
        value: settings[`route_${task}_base_url`] || "",
      });
      modelIn.addEventListener("change", () => save({ [`route_${task}_model`]: modelIn.value.trim() }, "任务模型已保存"));
      urlIn.addEventListener("change", () => save({ [`route_${task}_base_url`]: urlIn.value.trim() }, "任务接口已保存"));
      return ui.el("div", { class: "flex flex-col sm:grid sm:grid-cols-[80px_1fr_1fr] items-start sm:items-center gap-1.5 sm:gap-space-md py-1" },
        ui.el("span", { class: "font-label-md text-label-md text-primary font-medium" }, label),
        modelIn, urlIn);
    }),
    ui.el("p", { class: "font-label-sm text-label-sm text-outline" },
      "API Key 始终跟随上方主配置；Base URL 与模型名留空即跟随主配置。失焦自动保存。"));
  const routeToggleIcon = ui.icon("expand_more", "text-[20px] text-on-surface-variant transition-transform");
  const routeCard = ui.el("div", { class: "rounded-xl bg-surface-container-low flex flex-col" },
    ui.el("button", {
      class: "flex items-center justify-between p-space-md text-left",
      onclick: () => {
        const open = routeBody.style.display === "none";
        routeBody.style.display = open ? "flex" : "none";
        routeToggleIcon.style.transform = open ? "rotate(180deg)" : "";
      },
    },
      ui.el("div", { class: "flex items-center gap-space-sm" },
        ui.icon("alt_route", "text-[20px] text-primary"),
        ui.el("div", { class: "flex flex-col" },
          ui.el("span", { class: "font-body-sm text-body-sm text-primary font-medium" }, "任务级模型覆盖"),
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "为不同写作任务指定不同的模型 / 接口"))),
      routeToggleIcon),
    routeBody);

  /* ---------- 4. 文风档案 ---------- */
  let styleWorks = [];
  try { styleWorks = await api.get("/works"); } catch (e) { /* 忽略作品加载失败 */ }
  let styleProfile = "";
  const styleView = ui.el("div", {});
  const styleWorkSel = ui.el("select", { class: inputCls + " max-w-xs cursor-pointer" },
    styleWorks.map((w) => ui.el("option", { value: String(w.id) }, w.title)));
  const genLabel = ui.el("span", {}, "生成文风档案");
  const genStyleBtn = ui.el("button", {
    class: "flex items-center gap-1.5 px-space-md py-2 rounded-lg bg-primary text-on-primary hover:bg-primary-container transition-all font-label-md text-label-md disabled:opacity-50",
    onclick: () => styleGenDialog(),
  }, ui.icon("auto_awesome", "text-[18px]"), genLabel);
  const editStyleBtn = ui.el("button", {
    class: "flex items-center gap-1.5 px-space-md py-2 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md disabled:opacity-50",
    onclick: () => styleEditDialog(),
  }, ui.icon("edit", "text-[18px]"), ui.el("span", {}, "编辑"));
  const clearStyleBtn = ui.el("button", {
    class: "flex items-center gap-1.5 px-space-md py-2 rounded-lg bg-surface-container hover:bg-error-container hover:text-on-error-container font-label-md text-label-md disabled:opacity-50",
    onclick: async () => {
      const wid = Number(styleWorkSel.value);
      if (!wid) return;
      const ok = await ui.confirm("清除文风档案", "将清空当前作品的文风档案，且不可恢复。确定继续？", "清除", true);
      if (!ok) return;
      try {
        await api.del(`/works/${wid}/style`);
        styleProfile = "";
        renderStyle();
        ui.toast("文风档案已清除", "ok");
      } catch (e) { ui.toast(e.message, "err"); }
    },
  }, ui.icon("delete", "text-[18px]"), ui.el("span", {}, "清除"));

  function renderStyle() {
    const has = !!styleProfile;
    styleView.textContent = has ? styleProfile
      : "尚未生成文风档案。选择 1~3 章正文，让 AI 提炼叙事视角、句式偏好、用词特征与对话风格，后续生成时将自动贴合。";
    styleView.className = `p-space-md rounded-xl bg-surface-container-low min-h-[72px] font-body-sm text-body-sm whitespace-pre-wrap ${has ? "text-on-surface" : "text-on-surface-variant"}`;
    genLabel.textContent = has ? "重新生成" : "生成文风档案";
    editStyleBtn.disabled = !has;
    clearStyleBtn.disabled = !has;
  }

  async function loadStyle() {
    const wid = Number(styleWorkSel.value);
    if (!wid) return;
    try {
      const r = await api.get(`/works/${wid}/style`);
      styleProfile = r.style_profile || "";
    } catch (e) { ui.toast(e.message, "err"); styleProfile = ""; }
    renderStyle();
  }
  styleWorkSel.addEventListener("change", loadStyle);

  function styleGenDialog() {
    const wid = Number(styleWorkSel.value);
    if (!wid) { ui.toast("请先选择作品", "err"); return; }
    if (!((settings.ai_base_url || "").trim() && (settings.ai_api_key || "").trim() && (settings.ai_model || "").trim())) {
      ui.toast("请先在上方「AI 模型配置」填写 Base URL、API Key 与模型名", "err");
      return;
    }
    (async () => {
      let tree;
      try { tree = await api.get(`/works/${wid}/tree`); } catch (e) { ui.toast(e.message, "err"); return; }
      const chapters = [];
      for (const v of tree) for (const c of (v.chapters || [])) chapters.push({ id: c.id, title: `${v.title} · ${c.title}` });
      if (!chapters.length) { ui.toast("该作品还没有章节，无法生成文风档案", "err"); return; }
      const boxes = chapters.map((c) => {
        const cb = ui.el("input", { type: "checkbox", class: "accent-secondary w-4 h-4", value: String(c.id) });
        cb.addEventListener("change", () => {
          if (cb.checked && boxes.filter((x) => x.checked).length > 3) {
            cb.checked = false;
            ui.toast("最多选择 3 章", "err");
          }
        });
        return cb;
      });
      const close = () => overlay.remove();
      const startBtn = ui.el("button", {
        class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md disabled:opacity-50",
        onclick: async () => {
          const ids = boxes.filter((x) => x.checked).map((x) => Number(x.value));
          if (!ids.length) { ui.toast("请至少勾选 1 章", "err"); return; }
          startBtn.disabled = true;
          startBtn.textContent = "正在分析…";
          try {
            const r = await api.post(`/works/${wid}/style/generate`, { chapter_ids: ids });
            styleProfile = r.style_profile || "";
            renderStyle();
            ui.toast("文风档案已生成", "ok");
            ui.refreshStats();
            close();
          } catch (e) {
            ui.toast(e.message, "err");
            startBtn.disabled = false;
            startBtn.textContent = "开始生成";
          }
        },
      }, "开始生成");
      const overlay = ui.el("div", {
        class: "fixed inset-0 z-[90] bg-ink-black/40 backdrop-blur-sm flex items-center justify-center",
        onclick: (e) => { if (e.target === overlay) close(); },
      },
        ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-lg w-[480px] max-w-[calc(100vw-2rem)] mx-2 sm:mx-0 shadow-[0_12px_32px_rgba(27,42,56,0.12)] flex flex-col gap-space-md" },
          ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, "生成文风档案"),
          ui.el("p", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "勾选 1~3 章作为分析样本，每章截取前 2500 字交由 AI 提炼文风。"),
          ui.el("div", { class: "flex flex-col gap-2 max-h-[320px] overflow-y-auto" },
            chapters.map((c, i) => ui.el("label", { class: "flex items-center gap-2 p-2 rounded-lg bg-surface-container-low cursor-pointer" },
              boxes[i], ui.el("span", { class: "font-body-sm text-body-sm text-on-surface" }, c.title)))),
          ui.el("div", { class: "flex justify-end gap-2" },
            ui.el("button", { class: "px-4 py-2 rounded-lg bg-surface-container font-label-md text-label-md", onclick: close }, "取消"),
            startBtn)));
      document.getElementById("modal-root").append(overlay);
    })();
  }

  function styleEditDialog() {
    const wid = Number(styleWorkSel.value);
    if (!wid) return;
    const ta = ui.el("textarea", { class: inputCls + " min-h-[240px] resize-y" }, styleProfile);
    const close = (ok) => {
      overlay.remove();
      if (!ok) return;
      (async () => {
        try {
          const r = await api.req("PUT", `/works/${wid}/style`, { style_profile: ta.value });
          styleProfile = r.style_profile || "";
          renderStyle();
          ui.toast("文风档案已保存", "ok");
        } catch (e) { ui.toast(e.message, "err"); }
      })();
    };
    const overlay = ui.el("div", {
      class: "fixed inset-0 z-[90] bg-ink-black/40 backdrop-blur-sm flex items-center justify-center",
      onclick: (e) => { if (e.target === overlay) close(false); },
    },
      ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-lg w-[560px] max-w-[calc(100vw-2rem)] mx-2 sm:mx-0 shadow-[0_12px_32px_rgba(27,42,56,0.12)] flex flex-col gap-space-md" },
        ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, "编辑文风档案"),
        ui.el("p", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "AI 生成时将把以下内容作为文风约束注入提示词。"),
        ta,
        ui.el("div", { class: "flex justify-end gap-2" },
          ui.el("button", { class: "px-4 py-2 rounded-lg bg-surface-container font-label-md text-label-md", onclick: () => close(false) }, "取消"),
          ui.el("button", { class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md", onclick: () => close(true) }, "保存"))));
    document.getElementById("modal-root").append(overlay);
    ta.focus();
  }

  renderStyle();

  /* ---------- 4.5 生图接口（丹青阁） ---------- */
  const imgUrl = ui.el("input", { class: inputCls, placeholder: "https://api.siliconflow.cn/v1", value: settings.img_base_url || "" });
  const imgKey = ui.el("input", { class: inputCls, type: "password", placeholder: "sk-…", value: settings.img_api_key || "" });
  const imgModel = ui.el("input", { class: inputCls, placeholder: "如 Kwai-Kolors/Kolors", value: settings.img_model || "" });
  const IMG_SIZES = ["1024x1024", "960x1280", "1280x720", "720x1280", "1440x720"];
  const imgSize = ui.el("select", { class: inputCls + " cursor-pointer" },
    IMG_SIZES.map((s) => ui.el("option", { value: s }, s)));
  if (settings.img_size && !IMG_SIZES.includes(settings.img_size))
    imgSize.append(ui.el("option", { value: settings.img_size }, settings.img_size));
  imgSize.value = settings.img_size || "1024x1024";
  imgUrl.addEventListener("change", () => save({ img_base_url: imgUrl.value.trim() }));
  imgKey.addEventListener("change", () => save({ img_api_key: imgKey.value.trim() }));
  imgModel.addEventListener("change", () => save({ img_model: imgModel.value.trim() }));
  imgSize.addEventListener("change", () => save({ img_size: imgSize.value }));

  const imgTestResult = ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "尚未测试");
  const imgTestBtn = ui.el("button", {
    class: "flex items-center gap-1.5 px-space-md py-2 rounded-lg bg-primary text-on-primary hover:bg-primary-container transition-all font-label-md text-label-md disabled:opacity-50",
    onclick: async () => {
      imgTestBtn.disabled = true;
      imgTestResult.textContent = "正在测试连接…";
      imgTestResult.className = "font-label-sm text-label-sm text-on-surface-variant";
      try {
        await save({
          img_base_url: imgUrl.value.trim(), img_api_key: imgKey.value.trim(),
          img_model: imgModel.value.trim(), img_size: imgSize.value,
        }, "配置已保存");
        const r = await api.post("/gallery/test");
        imgTestResult.textContent = r.message || (r.ok ? "连接成功" : "连接失败");
        imgTestResult.className = `font-label-sm text-label-sm ${r.ok ? "text-emerald-700" : "text-error"}`;
      } catch (e) {
        imgTestResult.textContent = e.message;
        imgTestResult.className = "font-label-sm text-label-sm text-error";
      }
      imgTestBtn.disabled = false;
    },
  }, ui.icon("cable", "text-[18px]"), "测试连接");

  /* ---------- 5. 数据与备份 ---------- */
  const backupBtn = ui.el("a", {
    class: "flex items-center gap-1.5 px-space-md py-2 rounded-lg bg-primary text-on-primary hover:bg-primary-container transition-all font-label-md text-label-md shadow-sm",
    href: "/api/settings/backup",
  }, ui.icon("database", "text-[18px]"), "导出整库备份 (moyu.db)");


  /* ---------- 6. 软件自动更新（v1.4.0） ---------- */
  let currentHealth = { version: "1.4.0" };
  try { currentHealth = await api.get("/health"); } catch (_) {}

  const updateChannelSel = ui.el("select", {
    class: "px-space-md py-2 rounded-lg bg-surface-container-low text-primary font-body-sm text-body-sm focus:outline-none focus:ring-1 focus:ring-secondary",
    onchange: () => save({ update_channel: updateChannelSel.value }),
  },
    ui.el("option", { value: "stable" }, "稳定版 (stable · 推荐)"),
    ui.el("option", { value: "beta" }, "尝鲜测试版 (beta)"));
  updateChannelSel.value = settings.update_channel || "stable";

  const updateAutoCheckSel = ui.el("select", {
    class: "px-space-md py-2 rounded-lg bg-surface-container-low text-primary font-body-sm text-body-sm focus:outline-none focus:ring-1 focus:ring-secondary",
    onchange: () => save({ update_auto_check: updateAutoCheckSel.value }),
  },
    ui.el("option", { value: "1" }, "自动检查 (进入设置时检查)"),
    ui.el("option", { value: "0" }, "手动检查 (关闭自动请求)"));
  updateAutoCheckSel.value = settings.update_auto_check !== undefined ? String(settings.update_auto_check) : "1";

  const updateMirrorInput = ui.el("input", {
    type: "text",
    placeholder: "如 https://ghproxy.net/（可选，加速国内访问）",
    value: settings.update_mirror || "",
    class: "w-full px-space-md py-2 rounded-lg bg-surface-container-low text-primary font-body-sm text-body-sm placeholder:text-outline focus:outline-none focus:ring-1 focus:ring-secondary",
  });
  updateMirrorInput.addEventListener("change", () => save({ update_mirror: updateMirrorInput.value.trim() }));

  const updateResultBox = ui.el("div", { class: "flex flex-col gap-space-md" });
  const checkStatusLabel = ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" },
    settings.update_last_check ? `上次检查：${settings.update_last_check}` : "尚未进行更新检查");

  const checkBtn = ui.el("button", {
    class: "flex items-center gap-1.5 px-space-md py-2 rounded-lg bg-secondary text-on-secondary hover:opacity-90 transition-all font-label-md text-label-md shadow-sm disabled:opacity-50 min-h-[44px]",
  }, ui.icon("refresh", "text-[18px]"), "检查新版本");

  async function pollVpsUpdateProgress(statusBox) {
    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      if (attempts > 60) {
        clearInterval(interval);
        return;
      }
      try {
        const s = await api.get("/update/status");
        if (s.status === "running") {
          statusBox.innerHTML = "";
          statusBox.append(
            ui.el("div", { class: "flex items-center gap-2 text-secondary font-label-md" },
              ui.icon("refresh", "animate-spin text-[16px]"),
              ui.el("span", {}, s.message || "正在更新中...")),
            ui.el("div", { class: "w-full h-2 rounded-full bg-surface-container-highest overflow-hidden mt-1" },
              ui.el("div", { class: "h-full bg-secondary transition-all duration-300", style: `width:${s.progress || 30}%` }))
          );
        } else if (s.status === "success") {
          clearInterval(interval);
          statusBox.innerHTML = "";
          statusBox.append(
            ui.el("div", { class: "p-space-md rounded-lg bg-emerald-50 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200 font-label-md flex items-center gap-2" },
              ui.icon("check_circle", "text-[18px]"),
              ui.el("span", {}, s.message || "更新成功！"))
          );
          ui.toast("更新成功！", "ok");
        } else if (s.status === "failed") {
          clearInterval(interval);
          statusBox.innerHTML = "";
          statusBox.append(
            ui.el("div", { class: "p-space-md rounded-lg bg-rose-50 text-rose-800 dark:bg-rose-950 dark:text-rose-200 font-body-sm flex flex-col gap-1" },
              ui.el("div", { class: "flex items-center gap-2 font-medium" },
                ui.icon("error", "text-[18px]"),
                ui.el("span", {}, "更新失败")),
              ui.el("span", { class: "text-xs font-mono" }, s.message || "未知错误"))
          );
        }
      } catch (_) {}
    }, 2000);
  }

  function renderUpdateResult(res) {
    updateResultBox.innerHTML = "";
    if (res.checked_at) {
      checkStatusLabel.textContent = `上次检查：${res.checked_at}`;
    }

    if (!res.has_update) {
      // 状态一：已是最新版本
      updateResultBox.append(
        ui.el("div", { class: "p-space-lg rounded-xl bg-surface-container-low border border-outline-variant/30 flex items-center gap-space-md" },
          ui.icon("check_circle", "text-[28px] text-emerald-600 dark:text-emerald-400 shrink-0"),
          ui.el("div", { class: "flex flex-col" },
            ui.el("span", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, "当前已是最新版本"),
            ui.el("span", { class: "font-body-sm text-body-sm text-on-surface-variant" },
              `墨语 MoYu v${res.current_version} · ${res.channel === "beta" ? "尝鲜测试通道" : "正式稳定通道"} · 本地环境运行良好。`)))
      );
      return;
    }

    // 状态二：发现新版本
    const isSkipped = res.is_skipped;
    const notesBox = ui.el("div", { class: "flex flex-col gap-1.5" },
      ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant font-medium" }, "新版特性与更新日志："),
      ui.el("pre", {
        class: "font-body-sm text-body-sm whitespace-pre-wrap font-sans max-h-60 overflow-y-auto p-space-md rounded-lg bg-surface-container-lowest border border-outline-variant/20 text-primary leading-relaxed select-text"
      }, res.release_notes || "（发布者未附带详细更新日志）"));

    const actionRow = ui.el("div", { class: "flex flex-wrap items-center gap-space-md mt-space-sm" });

    // 1. 前往 GitHub 发布页
    if (res.html_url) {
      actionRow.append(
        ui.el("a", {
          href: res.html_url,
          target: "_blank",
          rel: "noreferrer",
          class: "flex items-center gap-1 px-space-md py-2 rounded-lg bg-surface-container text-primary hover:bg-surface-container-high transition-all font-label-md text-label-md min-h-[44px]",
        }, ui.icon("open_in_new", "text-[16px]"), "查看 GitHub 发布详情")
      );
    }

    // 2. 桌面端 / 源码环境：提供 exe 直链下载
    if (res.exe_url) {
      actionRow.append(
        ui.el("a", {
          href: res.exe_url,
          target: "_blank",
          rel: "noreferrer",
          class: "flex items-center gap-1 px-space-md py-2 rounded-lg bg-secondary text-on-secondary hover:opacity-90 transition-all font-label-md text-label-md min-h-[44px] shadow-sm",
        }, ui.icon("download", "text-[18px]"), `下载 Windows 安装包 (${res.exe_name || "exe"})`)
      );
    }

    // 3. VPS 裸机 / systemd 环境：一键应用更新
    if (res.env === "systemd" || res.env === "source") {
      const vpsStatusBox = ui.el("div", { class: "w-full flex flex-col gap-2 mt-2" });
      const applyBtn = ui.el("button", {
        class: "flex items-center gap-1.5 px-space-md py-2 rounded-lg bg-primary text-on-primary hover:bg-primary-container transition-all font-label-md text-label-md min-h-[44px] disabled:opacity-50",
        onclick: async () => {
          if (!confirm("即将执行自动备份并更新代码至最新版本，是否继续？")) return;
          applyBtn.disabled = true;
          try {
            const applyRes = await api.post("/update/apply");
            ui.toast(applyRes.message || "更新任务已启动", "ok");
            pollVpsUpdateProgress(vpsStatusBox);
          } catch (err) {
            ui.toast(err.message, "err");
            applyBtn.disabled = false;
          }
        },
      }, ui.icon("refresh", "text-[18px]"), "立即在 VPS 执行一键更新");
      actionRow.append(applyBtn);
      actionRow.append(vpsStatusBox);
    }

    // 4. Docker 模式提示
    if (res.env === "docker") {
      actionRow.append(
        ui.el("div", { class: "w-full p-space-sm rounded-lg bg-surface-container-high/60 text-on-surface-variant font-body-sm text-body-sm flex items-center gap-2" },
          ui.icon("info", "text-[18px] text-secondary"),
          ui.el("span", {}, "Docker 容器已受安全隔离。推荐在宿主机执行 `docker compose pull && docker compose up -d` 或配置 Watchtower 镜像全自动拉取更新。"))
      );
    }

    // 5. 跳过此版本按钮
    const skipBtn = ui.el("button", {
      class: "text-on-surface-variant hover:text-primary transition-colors font-label-sm text-label-sm px-2 py-1 min-h-[44px]",
      onclick: async () => {
        try {
          await api.post("/update/skip", { version: res.latest_version });
          ui.toast(`已跳过 v${res.latest_version} 版本的弹窗提醒`, "ok");
          skipBtn.textContent = "已跳过该版本";
          skipBtn.disabled = true;
        } catch (e) {
          ui.toast(e.message, "err");
        }
      }
    }, isSkipped ? "已跳过此版本提醒" : "跳过此版本");
    if (isSkipped) skipBtn.disabled = true;
    actionRow.append(skipBtn);

    updateResultBox.append(
      ui.el("div", { class: "p-space-lg rounded-xl bg-surface-container-low border border-secondary/30 flex flex-col gap-space-md" },
        ui.el("div", { class: "flex items-start justify-between" },
          ui.el("div", { class: "flex flex-col" },
            ui.el("div", { class: "flex items-center gap-2" },
              ui.icon("auto_awesome", "text-[22px] text-secondary"),
              ui.el("span", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, `发现新版本：墨语 MoYu v${res.latest_version}`),
              ui.el("span", { class: "px-2 py-0.5 rounded text-[11px] font-medium bg-secondary-container text-on-secondary-container" }, res.raw_tag || `v${res.latest_version}`)),
            ui.el("span", { class: "font-body-sm text-body-sm text-on-surface-variant mt-0.5" },
              `当前安装版本：v${res.current_version} · 发布日期：${(res.published_at || "").slice(0, 10) || "近期"}`)),
          isSkipped && ui.el("span", { class: "font-label-sm text-label-sm text-outline px-2 py-0.5 rounded bg-surface-container" }, "已设置跳过")),
        notesBox,
        actionRow)
    );
  }

  function renderUpdateError(err) {
    updateResultBox.innerHTML = "";
    updateResultBox.append(
      ui.el("div", { class: "p-space-lg rounded-xl bg-surface-container-low border border-error/30 flex flex-col gap-space-sm" },
        ui.el("div", { class: "flex items-center gap-2 text-error" },
          ui.icon("error", "text-[22px]"),
          ui.el("span", { class: "font-headline-sm text-headline-sm font-semibold" }, "检查更新失败")),
        ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant" },
          err.message || "无法连接到 GitHub 版本检查服务，请确认网络畅通。"),
        ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant" },
          "💡 提示：若在国内网络下访问 GitHub 较慢或超时，可在上方配置「镜像加速代理」（例如填入 https://ghproxy.net/）后再次检查。"),
        ui.el("div", { class: "mt-space-xs" },
          ui.el("button", {
            class: "px-space-md py-1.5 rounded-lg bg-surface-container text-primary hover:bg-surface-container-high font-label-md text-label-md min-h-[44px]",
            onclick: () => doCheckUpdate(true),
          }, "重试检查")))
    );
  }

  async function doCheckUpdate(force = false) {
    checkBtn.disabled = true;
    checkBtn.textContent = "正在检查…";
    updateResultBox.innerHTML = "";
    updateResultBox.append(
      ui.el("div", { class: "flex items-center gap-2 p-space-md text-on-surface-variant font-body-sm text-body-sm" },
        ui.icon("refresh", "animate-spin text-[18px] text-secondary"),
        ui.el("span", {}, "正在连接版本服务检查新版本与发布日志..."))
    );
    try {
      await save({
        update_channel: updateChannelSel.value,
        update_auto_check: updateAutoCheckSel.value,
        update_mirror: updateMirrorInput.value.trim(),
      }, "更新设置已保存");
      const url = force ? "/update/check?force=true" : "/update/check";
      const res = await api.get(url);
      renderUpdateResult(res);
    } catch (e) {
      renderUpdateError(e);
    } finally {
      checkBtn.disabled = false;
      checkBtn.innerHTML = "";
      checkBtn.append(ui.icon("refresh", "text-[18px]"), "检查新版本");
    }
  }

  checkBtn.addEventListener("click", () => doCheckUpdate(true));

  // 页面加载时的自动检查（若开启且非禁用）
  if (settings.update_auto_check !== "0") {
    setTimeout(async () => {
      try {
        const res = await api.get("/update/check");
        if (res.has_update && !res.is_skipped) {
          renderUpdateResult(res);
        } else if (res.checked_at) {
          checkStatusLabel.textContent = `上次检查：${res.checked_at}`;
        }
      } catch (_) {}
    }, 600);
  }

  /* ---------- 6. 快捷键 ---------- */
  const SHORTCUTS = [
    ["save", "写作台手动保存当前章节", "Ctrl", "S"],
    ["search", "查找（浏览器页内查找）", "Ctrl", "F"],
    ["history", "版本快照：版本页「存快照」按钮", null, null],
    ["auto_awesome", "AI 续写/润色：工作台 AI 侧栏按钮", null, null],
  ];

  /* ---------- 组装 ---------- */
  view.append(
    ui.el("div", { class: "flex flex-col gap-1 pb-space-lg" },
      ui.el("span", { class: "font-label-sm text-label-sm uppercase tracking-widest text-secondary font-semibold" }, "Preferences · 本地单机"),
      ui.el("h1", { class: "font-display text-display text-primary tracking-tight" }, "系统偏好与创作者设置"),
      ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" },
        "所有设置保存在本地 data/moyu.db，改动即时生效、即时保存。")),

    section("palette", "书房主题配色", "点击配色卡立即切换并保存，无需重启。",
      ui.el("div", { class: "grid grid-cols-1 md:grid-cols-3 gap-space-md" },
        THEMES.map((t) => themeCards[t.key]))),

    section("format_shapes", "字体与版面呼吸率", "作用于写作工作台编辑区，滑块松手即保存。",
      ui.el("div", { class: "grid grid-cols-1 md:grid-cols-3 gap-space-lg" },
        sliderCard("正文字号", "editor_font_size", 14, 24, 1, "px", (v) => { previewText.style.fontSize = v + "px"; }),
        sliderCard("行高倍率", "editor_line_height", 1.5, 2.4, 0.1, "倍", (v) => { previewText.style.lineHeight = v; }),
        sliderCard("自动保存间隔", "autosave_interval", 1, 10, 1, "秒")),
      ui.el("div", { class: "flex items-center justify-between p-space-md rounded-xl bg-surface-container-low" },
        ui.el("div", { class: "flex items-center gap-space-sm" },
          ui.icon("target", "text-[20px] text-primary"),
          ui.el("div", { class: "flex flex-col" },
            ui.el("span", { class: "font-body-sm text-body-sm text-primary font-medium" }, "每日字数目标"),
            ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "顶栏「今日字数」进度按此目标计算"))),
        ui.el("div", { class: "flex items-center gap-2" }, goalInput,
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "字"))),
      ui.el("div", { class: "p-space-lg rounded-xl bg-surface-container-high/50 flex flex-col gap-space-xs" },
        ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider" }, "排版效果沙盒试读"),
        previewText)),

    section("neurology", "AI 模型配置", "选择服务商自动填充接口配置；AI 生成内容始终先预览、不静默写入正文。",
      ui.el("div", { class: "flex flex-col gap-1.5 max-w-sm" },
        ui.el("label", { class: "font-label-md text-label-md text-on-surface-variant font-medium" }, "服务商"),
        providerSelect,
        providerHint),
      ui.el("div", { class: "grid grid-cols-1 md:grid-cols-3 gap-space-md" },
        ui.el("div", { class: "flex flex-col gap-1.5" },
          ui.el("label", { class: "font-label-md text-label-md text-on-surface-variant font-medium" }, "Base URL"), aiUrl),
        ui.el("div", { class: "flex flex-col gap-1.5" },
          ui.el("label", { class: "font-label-md text-label-md text-on-surface-variant font-medium" }, "API Key"), aiKey),
        ui.el("div", { class: "flex flex-col gap-1.5" },
          ui.el("label", { class: "font-label-md text-label-md text-on-surface-variant font-medium" }, "模型名"), modelPickerWrap)),
      ui.el("div", { class: "flex items-center gap-space-md" }, testBtn, testResult),
      routeCard,
      ui.el("div", { class: "p-space-lg rounded-xl bg-gradient-to-r from-surface-container-low to-surface-container-high/40 flex flex-col gap-1" },
        ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "累计 Token 用量估算"),
        tokenBox,
        ui.el("span", { class: "font-label-sm text-label-sm text-outline" },
          "估算口径：优先取 API 返回的 usage，缺失时按字符数 ÷ 2 估算，仅供参考。"))),

    section("ink_pen", "文风档案", "让 AI 学习某部作品的文风档案，后续 AI 生成（续写 / 润色等）将自动贴合该档案。",
      styleWorks.length
        ? ui.el("div", { class: "flex flex-wrap items-center gap-space-md" },
            ui.el("label", { class: "font-label-md text-label-md text-on-surface-variant font-medium" }, "选择作品"),
            styleWorkSel,
            ui.el("div", { class: "flex items-center gap-2" }, genStyleBtn, editStyleBtn, clearStyleBtn))
        : ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant" }, "书架还没有作品，请先在书架创建作品。"),
      styleWorks.length && styleView),

    section("palette", "生图接口（丹青阁）", "为「炼丹炉 · 丹青阁」提供封面与插图生成能力。接口需兼容 OpenAI Images 协议（POST {Base URL}/images/generations），推荐 SiliconFlow，可到 platform.siliconflow.cn 申请 Key。失焦自动保存。",
      ui.el("div", { class: "grid grid-cols-1 md:grid-cols-2 gap-space-md" },
        ui.el("div", { class: "flex flex-col gap-1.5" },
          ui.el("label", { class: "font-label-md text-label-md text-on-surface-variant font-medium" }, "Base URL"), imgUrl),
        ui.el("div", { class: "flex flex-col gap-1.5" },
          ui.el("label", { class: "font-label-md text-label-md text-on-surface-variant font-medium" }, "API Key"), imgKey),
        ui.el("div", { class: "flex flex-col gap-1.5" },
          ui.el("label", { class: "font-label-md text-label-md text-on-surface-variant font-medium" }, "模型名"), imgModel),
        ui.el("div", { class: "flex flex-col gap-1.5" },
          ui.el("label", { class: "font-label-md text-label-md text-on-surface-variant font-medium" }, "默认尺寸"), imgSize)),
      ui.el("div", { class: "flex items-center gap-space-md" }, imgTestBtn, imgTestResult)),


    section("refresh", "软件更新", "检查墨语 MoYu 最新版本，查看新特性发布日志，支持 Windows 桌面端引导下载与 Linux/VPS 一键更新。",
      ui.el("div", { class: "grid grid-cols-1 md:grid-cols-3 gap-space-md" },
        ui.el("div", { class: "flex flex-col gap-1.5" },
          ui.el("label", { class: "font-label-md text-label-md text-on-surface-variant font-medium" }, "更新通道"),
          updateChannelSel),
        ui.el("div", { class: "flex flex-col gap-1.5" },
          ui.el("label", { class: "font-label-md text-label-md text-on-surface-variant font-medium" }, "自动检查策略"),
          updateAutoCheckSel),
        ui.el("div", { class: "flex flex-col gap-1.5" },
          ui.el("label", { class: "font-label-md text-label-md text-on-surface-variant font-medium" }, "GitHub 镜像代理 (可选)"),
          updateMirrorInput)),
      ui.el("div", { class: "flex flex-wrap items-center gap-space-md" },
        checkBtn,
        checkStatusLabel),
      updateResultBox),

    section("database", "数据与备份", null,
      ui.el("div", { class: "flex flex-col gap-2 p-space-md rounded-xl bg-surface-container-low font-body-sm text-body-sm text-on-surface-variant" },
        ui.el("span", {}, "全部数据（作品、章节、设定、导出记录）保存在应用目录下的 data/ 文件夹："),
        ui.el("span", { class: "font-mono text-[12px] text-primary" }, "data/moyu.db（整库）· data/exports/（导出文件）· data/imports/（导入暂存）"),
        ui.el("span", {}, "备份即复制 data/ 文件夹，或点击下方按钮直接下载数据库文件。")),
      ui.el("div", {}, backupBtn)),

    section("keyboard", "快捷键速查", "以各页面按钮与提示为准，以下为当前版本已实现的快捷操作。",
      ui.el("div", { class: "grid grid-cols-1 md:grid-cols-2 gap-space-md" },
        SHORTCUTS.map(([icon, label, k1, k2]) =>
          ui.el("div", { class: "flex items-center justify-between p-space-sm rounded-lg bg-surface-container-low" },
            ui.el("div", { class: "flex items-center gap-space-sm" },
              ui.icon(icon, "text-[18px] text-on-surface-variant"),
              ui.el("span", { class: "font-body-sm text-body-sm text-primary font-medium" }, label)),
            k1 && ui.el("div", { class: "flex items-center gap-1 font-label-sm text-label-sm" },
              ui.el("kbd", { class: "px-2 py-1 rounded bg-surface-container-lowest text-on-surface shadow-sm font-semibold" }, k1),
              k2 && ui.el("span", { class: "text-outline" }, "+"),
              k2 && ui.el("kbd", { class: "px-2 py-1 rounded bg-surface-container-lowest text-on-surface shadow-sm font-semibold" }, k2)))))),
  );

  renderThemes();
  if (styleWorks.length) loadStyle();
});
