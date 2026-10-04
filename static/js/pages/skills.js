/* Skill 市场（Agent Skills 规范管理、资源挂载与导入导出） */
registerPage("skills", async (view) => {
  ui.setCrumb("Skill 市场");

  const fileInput = ui.el("input", {
    type: "file",
    accept: ".skill,.zip",
    class: "hidden",
    onchange: async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const fd = new FormData();
      fd.append("file", file);
      try {
        ui.toast("正在导入技能包...", "info");
        const res = await api.upload("/skills/import", fd);
        ui.toast(`成功导入技能：${res.title}`, "ok");
        await loadSkills();
      } catch (err) {
        ui.toast(`导入失败：${err.message}`, "err");
      } finally {
        fileInput.value = "";
      }
    },
  });
  document.body.append(fileInput);

  ui.setActions(
    ui.el("div", { class: "flex items-center gap-2" },
      ui.el("button", {
        class: "flex items-center gap-1 px-3 py-1.5 rounded-full border border-outline-variant text-on-surface hover:bg-surface-container-high transition-all text-xs font-medium",
        onclick: () => fileInput.click(),
      }, ui.icon("upload_file", "text-[16px]"), ui.el("span", {}, "导入 .skill")),
      ui.el("button", {
        class: "flex items-center gap-1 px-space-sm py-1.5 rounded-full bg-primary text-on-primary shadow-[0_2px_12px_rgba(6,21,35,0.2)] hover:bg-primary-container transition-all",
        onclick: () => openSkillModal(null),
      }, ui.icon("add", "text-[18px]"), ui.el("span", { class: "font-label-md text-label-md" }, "新建技能")),
    )
  );

  const TASKS = [
    ["all", "全部"],
    ["general", "通用"],
    ["continue", "续写"],
    ["expand", "扩写"],
    ["shorten", "缩写"],
    ["rewrite", "改写润色"],
    ["outline", "大纲生成"],
    ["audit", "设定检查"],
    ["analysis", "分析"],
  ];
  const TASK_LABEL = {
    "": "通用",
    general: "通用",
    continue: "续写",
    expand: "扩写",
    shorten: "缩写",
    rewrite: "改写润色",
    outline: "大纲生成",
    audit: "设定检查",
    analysis: "分析",
  };

  const SOURCE_BADGES = {
    builtin: { label: "系统内置", bg: "bg-surface-container-high text-on-surface-variant" },
    custom: { label: "自定义", bg: "bg-primary-container text-on-primary-container" },
    migrated: { label: "旧版迁移", bg: "bg-tertiary-fixed text-on-tertiary-fixed" },
    imported: { label: "外部导入", bg: "bg-secondary-container text-on-secondary-container" },
  };

  let skills = [];
  let activeTab = "all";
  let activeSource = "all";
  let searchQuery = "";

  const container = ui.el("div", { class: "max-w-6xl mx-auto px-4 py-6 space-y-6" });
  view.append(container);

  // 顶部过滤与搜索栏
  const toolbar = ui.el("div", { class: "flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-outline-variant" });
  const tabBar = ui.el("div", { class: "flex flex-wrap gap-1.5" });
  
  const searchInput = ui.el("input", {
    type: "text",
    placeholder: "搜索技能名称、标题或触发依据...",
    class: "w-full md:w-64 px-3 py-1.5 text-xs rounded-lg border border-outline-variant bg-surface text-on-surface focus:outline-none focus:border-primary",
    oninput: (e) => {
      searchQuery = e.target.value.trim().toLowerCase();
      renderGrid();
    }
  });

  toolbar.append(tabBar, searchInput);
  container.append(toolbar);

  const grid = ui.el("div", { class: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" });
  container.append(grid);

  function renderTabs() {
    tabBar.innerHTML = "";
    TASKS.forEach(([key, label]) => {
      const active = activeTab === key;
      const btn = ui.el("button", {
        class: `px-3 py-1 text-xs rounded-full transition-all ${
          active ? "bg-primary text-on-primary font-medium" : "bg-surface-container-low text-on-surface-variant hover:bg-surface-container"
        }`,
        onclick: () => {
          activeTab = key;
          renderTabs();
          renderGrid();
        },
      }, label);
      tabBar.append(btn);
    });
  }

  function renderGrid() {
    grid.innerHTML = "";
    const filtered = skills.filter((s) => {
      if (activeTab === "general") {
        if (s.applies_to && s.applies_to !== "general") return false;
      } else if (activeTab !== "all") {
        if (s.applies_to !== activeTab) return false;
      }
      if (searchQuery) {
        const text = `${s.name} ${s.title} ${s.description}`.toLowerCase();
        if (!text.includes(searchQuery)) return false;
      }
      return true;
    });

    if (filtered.length === 0) {
      grid.append(
        ui.el("div", { class: "col-span-full py-16 text-center text-on-surface-variant text-sm" },
          ui.icon("filter_list_off", "text-4xl mb-2 opacity-50 block mx-auto"),
          "暂无符合条件的 Skill"
        )
      );
      return;
    }

    filtered.forEach((skill) => {
      const isBuiltin = skill.source === "builtin";
      const srcMeta = SOURCE_BADGES[skill.source] || SOURCE_BADGES.custom;

      const card = ui.el("div", {
        class: "flex flex-col justify-between p-4 rounded-xl border border-outline-variant bg-surface hover:shadow-md transition-all relative overflow-hidden group",
      });

      // 顶部
      const top = ui.el("div", { class: "space-y-2.5" });
      const headerRow = ui.el("div", { class: "flex items-start justify-between gap-2" });
      const titleWrap = ui.el("div", { class: "flex items-center gap-2" });
      const icon = ui.icon(skill.icon || "auto_awesome", "text-[20px] text-primary");
      const title = ui.el("h3", { class: "font-serif text-base font-semibold text-on-surface" }, skill.title);
      titleWrap.append(icon, title);

      const badges = ui.el("div", { class: "flex items-center gap-1.5 flex-wrap justify-end" });
      const taskTag = ui.el("span", { class: "px-2 py-0.5 text-[10px] rounded bg-surface-container text-on-surface-variant" },
        TASK_LABEL[skill.applies_to] || "通用"
      );
      const srcBadge = ui.el("span", { class: `px-2 py-0.5 text-[10px] rounded ${srcMeta.bg}` }, srcMeta.label);
      badges.append(taskTag, srcBadge);
      headerRow.append(titleWrap, badges);

      const subRow = ui.el("div", { class: "text-[11px] font-mono text-outline" }, `${skill.name}@${skill.version || "1.0.0"}`);

      const desc = ui.el("p", {
        class: "text-xs text-on-surface-variant line-clamp-3 leading-relaxed",
        title: skill.description || "暂无触发描述",
      }, skill.description || "暂无触发描述");

      // 资源统计信息
      const filesInfo = ui.el("div", { class: "flex items-center gap-2 text-[11px] text-on-surface-variant pt-1" },
        ui.icon("folder", "text-[14px] opacity-70"),
        ui.el("span", {}, `${skill.files_count || 0} 个挂载文件`),
        ui.el("span", { class: "text-outline" }, `·`),
        ui.el("span", {}, `${((skill.total_files_size || 0) / 1024).toFixed(1)} KB`),
        skill.enabled === 1 
          ? ui.el("span", { class: "ml-auto text-[10px] text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded" }, "已启用")
          : ui.el("span", { class: "ml-auto text-[10px] text-rose-600 bg-rose-50 px-1.5 py-0.5 rounded" }, "已停用")
      );

      top.append(headerRow, subRow, desc, filesInfo);

      // 底部操作区
      const bottom = ui.el("div", { class: "flex items-center justify-between pt-3 mt-3 border-t border-outline-variant/60 text-xs" });

      const leftActions = ui.el("div", { class: "flex items-center gap-2" });
      // 启停切换按钮
      const toggleBtn = ui.el("button", {
        class: `px-2 py-1 rounded text-xs transition-all ${
          skill.enabled === 1 ? "text-emerald-700 hover:bg-emerald-50" : "text-on-surface-variant hover:bg-surface-container"
        }`,
        title: skill.enabled === 1 ? "点击停用" : "点击启用",
        onclick: async () => {
          try {
            await api.patch(`/skills/${skill.id}`, { enabled: skill.enabled === 1 ? 0 : 1 });
            ui.toast(skill.enabled === 1 ? "已停用技能" : "已启用技能", "ok");
            await loadSkills();
          } catch (err) {
            ui.toast(`状态更新失败：${err.message}`, "err");
          }
        },
      }, ui.icon(skill.enabled === 1 ? "toggle_on" : "toggle_off", "text-[18px] align-middle"));

      // 校验按钮
      const valBtn = ui.el("button", {
        class: "p-1 rounded text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-all",
        title: "规范校验",
        onclick: () => openValidateModal(skill.id),
      }, ui.icon("verified", "text-[16px]"));

      // 导出按钮
      const exportBtn = ui.el("button", {
        class: "p-1 rounded text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-all",
        title: "导出为 .skill 包",
        onclick: () => {
          window.open(`/api/skills/${skill.id}/export`, "_blank");
        },
      }, ui.icon("download", "text-[16px]"));

      leftActions.append(toggleBtn, valBtn, exportBtn);

      const rightActions = ui.el("div", { class: "flex items-center gap-1.5" });
      // 副本按钮
      const dupBtn = ui.el("button", {
        class: "px-2 py-1 rounded text-on-surface-variant hover:bg-surface-container-high transition-all",
        title: "复制副本",
        onclick: async () => {
          try {
            ui.toast("正在创建副本...", "info");
            const res = await api.post(`/skills/${skill.id}/duplicate`);
            ui.toast(`已创建副本：${res.title}`, "ok");
            await loadSkills();
          } catch (err) {
            ui.toast(`复制失败：${err.message}`, "err");
          }
        },
      }, "副本");

      // 编辑按钮
      const editBtn = ui.el("button", {
        class: "px-2.5 py-1 rounded bg-primary-container text-on-primary-container font-medium hover:brightness-95 transition-all",
        onclick: () => openSkillModal(skill.id),
      }, "编辑");

      rightActions.append(dupBtn, editBtn);

      if (!isBuiltin) {
        const delBtn = ui.el("button", {
          class: "p-1 rounded text-error hover:bg-error-container transition-all ml-1",
          title: "删除技能",
          onclick: async () => {
            if (!confirm(`确定要彻底删除技能「${skill.title}」吗？`)) return;
            try {
              await api.delete(`/skills/${skill.id}`);
              ui.toast("已删除技能", "ok");
              await loadSkills();
            } catch (err) {
              ui.toast(`删除失败：${err.message}`, "err");
            }
          },
        }, ui.icon("delete", "text-[16px]"));
        rightActions.append(delBtn);
      }

      bottom.append(leftActions, rightActions);
      card.append(top, bottom);
      grid.append(card);
    });
  }

  async function loadSkills() {
    try {
      skills = await api.get("/skills");
      renderGrid();
    } catch (e) {
      ui.toast("加载技能列表失败: " + e.message, "err");
    }
  }

  // --- 规范校验弹窗 ---
  async function openValidateModal(skillId) {
    ui.toast("正在进行规范校验...", "info");
    let result = null;
    try {
      result = await api.post(`/skills/${skillId}/validate`);
    } catch (e) {
      ui.toast("校验失败: " + e.message, "err");
      return;
    }

    const { valid, issues, skill_name } = result;
    const body = ui.el("div", { class: "space-y-4 text-xs" });

    const statusBanner = ui.el("div", {
      class: `p-3 rounded-lg flex items-center gap-2 ${
        valid ? "bg-emerald-50 text-emerald-800 border border-emerald-200" : "bg-rose-50 text-rose-800 border border-rose-200"
      }`
    },
      ui.icon(valid ? "check_circle" : "error", "text-lg"),
      ui.el("span", { class: "font-medium" }, valid ? "符合 Agent Skill 架构规范要求" : "未完全满足 Agent Skill 规范，需按提示修正")
    );
    body.append(statusBanner);

    const list = ui.el("div", { class: "space-y-2" });
    if (issues.length === 0) {
      list.append(ui.el("div", { class: "text-on-surface-variant p-2" }, "零警告、零异常，规范完整度 100%。"));
    } else {
      issues.forEach((item) => {
        const isErr = item.level === "error";
        const row = ui.el("div", {
          class: `p-2.5 rounded-lg border flex items-start gap-2 ${
            isErr ? "bg-rose-50/50 border-rose-200 text-rose-900" : "bg-amber-50/50 border-amber-200 text-amber-900"
          }`
        },
          ui.icon(isErr ? "cancel" : "warning", "text-sm mt-0.5"),
          ui.el("span", { class: "flex-1 leading-normal" }, item.message)
        );
        list.append(row);
      });
    }
    body.append(list);

    ui.modal(`规范契约校验 · ${skill_name}`, body, [
      ui.el("button", {
        class: "px-4 py-1.5 rounded-full bg-surface-container text-on-surface hover:bg-surface-container-high text-xs",
        onclick: () => document.getElementById("modal-root").innerHTML = "",
      }, "关闭")
    ]);
  }

  // --- 双栏编辑与资源管理弹窗 ---
  async function openSkillModal(skillId) {
    let skill = null;
    if (skillId) {
      try {
        skill = await api.get(`/skills/${skillId}`);
      } catch (e) {
        ui.toast("获取技能详情失败: " + e.message, "err");
        return;
      }
    } else {
      skill = {
        name: "",
        title: "",
        description: "",
        applies_to: "",
        version: "1.0.0",
        enabled: 1,
        icon: "auto_awesome",
        body_md: "---\nname: my-new-skill\ndescription: 详细说明技能的核心作用与适用写作场景\n---\n\n你是一位专业的长篇小说助手。\n\n【上下文】\n{{context}}\n\n【选区】\n{{selection}}\n\n【要求】\n{{instruction}}\n\n请直接输出正文，不要输出解释。",
        files: []
      };
    }

    const modalBody = ui.el("div", { class: "flex flex-col lg:flex-row gap-4 h-[75vh] max-h-[750px] overflow-hidden text-xs" });

    // 左栏：元数据与资源文件管理
    const leftCol = ui.el("div", { class: "w-full lg:w-5/12 flex flex-col gap-3 pr-2 overflow-y-auto" });

    // 字段组件
    function field(label, inputEl, tip = "") {
      const wrap = ui.el("div", { class: "space-y-1" });
      const lbl = ui.el("label", { class: "font-medium text-on-surface block" }, label);
      wrap.append(lbl, inputEl);
      if (tip) wrap.append(ui.el("p", { class: "text-[10px] text-outline" }, tip));
      return wrap;
    }

    const nameInput = ui.el("input", {
      type: "text",
      value: skill.name || "",
      placeholder: "如: chapter-polish",
      class: "w-full px-3 py-1.5 rounded-lg border border-outline-variant bg-surface text-on-surface focus:outline-none focus:border-primary font-mono",
    });

    const titleInput = ui.el("input", {
      type: "text",
      value: skill.title || "",
      placeholder: "如: 章节精修打磨",
      class: "w-full px-3 py-1.5 rounded-lg border border-outline-variant bg-surface text-on-surface focus:outline-none focus:border-primary",
    });

    const descInput = ui.el("textarea", {
      rows: 3,
      value: skill.description || "",
      placeholder: "说明技能是什么、何时使用（建议 ≥20 字）...",
      class: "w-full px-3 py-1.5 rounded-lg border border-outline-variant bg-surface text-on-surface focus:outline-none focus:border-primary leading-relaxed",
    });

    const appliesSelect = ui.el("select", {
      class: "w-full px-3 py-1.5 rounded-lg border border-outline-variant bg-surface text-on-surface focus:outline-none focus:border-primary",
    });
    TASKS.forEach(([k, l]) => {
      appliesSelect.append(ui.el("option", { value: k === "all" ? "" : k, selected: skill.applies_to === k }, l));
    });

    const verInput = ui.el("input", {
      type: "text",
      value: skill.version || "1.0.0",
      class: "w-full px-3 py-1.5 rounded-lg border border-outline-variant bg-surface text-on-surface focus:outline-none focus:border-primary font-mono",
    });

    leftCol.append(
      field("规范名称 (name)", nameInput, "仅支持小写字母、数字与连字符 -（例：chapter-polish，禁止下划线），≤64 字符"),
      field("展示标题 (title)", titleInput),
      field("触发依据与描述 (description)", descInput, "用于模型选择依据与功能自述"),
      field("适用任务类型 (applies_to)", appliesSelect),
      field("版本号 (version)", verInput),
    );

    // 资源文件管理分区
    const filesSection = ui.el("div", { class: "mt-3 pt-3 border-t border-outline-variant space-y-2" });
    const filesHeader = ui.el("div", { class: "flex items-center justify-between" });
    filesHeader.append(
      ui.el("span", { class: "font-semibold text-on-surface" }, "挂载资源文件 (scripts/references/assets)"),
      ui.el("button", {
        class: "text-[11px] text-primary hover:underline flex items-center gap-0.5",
        onclick: () => promptNewFile(skill.id),
      }, ui.icon("add", "text-sm"), "新建文件")
    );
    filesSection.append(filesHeader);

    const filesList = ui.el("div", { class: "space-y-1.5 max-h-40 overflow-y-auto" });
    function renderFileList(fileArr) {
      filesList.innerHTML = "";
      if (!fileArr || fileArr.length === 0) {
        filesList.append(ui.el("div", { class: "text-[11px] text-outline py-2 italic text-center" }, "暂无挂载文件"));
        return;
      }
      fileArr.forEach((f) => {
        const row = ui.el("div", { class: "flex items-center justify-between p-2 rounded bg-surface-container-low border border-outline-variant/50" });
        const left = ui.el("div", { class: "flex items-center gap-1.5 overflow-hidden" });
        const iconName = f.path.startsWith("references/") ? "article" : f.path.startsWith("scripts/") ? "code" : "image";
        left.append(
          ui.icon(iconName, "text-xs text-outline"),
          ui.el("span", { class: "font-mono text-[11px] truncate max-w-[140px]", title: f.path }, f.path),
          ui.el("span", { class: "text-[10px] text-outline" }, `(${((f.size || 0)/1024).toFixed(1)}k)`)
        );
        const acts = ui.el("div", { class: "flex items-center gap-1" });
        if (f.path.startsWith("references/")) {
          const editF = ui.el("button", {
            class: "p-1 rounded text-primary hover:bg-surface-container",
            title: "编辑参考文档内容",
            onclick: () => openFileEditor(skill.id, f.path),
          }, ui.icon("edit_note", "text-xs"));
          acts.append(editF);
        }
        const delF = ui.el("button", {
          class: "p-1 rounded text-error hover:bg-error-container",
          title: "删除文件",
          onclick: async () => {
            if (!confirm(`确认删除文件 ${f.path} 吗？`)) return;
            try {
              await api.delete(`/skills/${skill.id}/files/${encodeURIComponent(f.path)}`);
              ui.toast("文件已删除", "ok");
              const updated = await api.get(`/skills/${skill.id}`);
              skill.files = updated.files;
              renderFileList(skill.files);
            } catch (err) {
              ui.toast("删除失败: " + err.message, "err");
            }
          }
        }, ui.icon("close", "text-xs"));
        acts.append(delF);
        row.append(left, acts);
        filesList.append(row);
      });
    }
    renderFileList(skill.files);
    filesSection.append(filesList);
    leftCol.append(filesSection);

    // 右栏：SKILL.md 正文编辑器
    const rightCol = ui.el("div", { class: "w-full lg:w-7/12 flex flex-col gap-2 pl-2 border-t lg:border-t-0 lg:border-l border-outline-variant" });
    const rightHeader = ui.el("div", { class: "flex items-center justify-between" });
    rightHeader.append(
      ui.el("span", { class: "font-semibold text-on-surface" }, "SKILL.md 核心指令与模板"),
      ui.el("div", { class: "flex items-center gap-1" },
        ui.el("button", {
          class: "px-2 py-0.5 rounded bg-surface-container hover:bg-surface-container-high text-[10px] text-on-surface",
          onclick: () => insertPlaceholder("{{context}}"),
        }, "+ 上下文"),
        ui.el("button", {
          class: "px-2 py-0.5 rounded bg-surface-container hover:bg-surface-container-high text-[10px] text-on-surface",
          onclick: () => insertPlaceholder("{{selection}}"),
        }, "+ 选区"),
        ui.el("button", {
          class: "px-2 py-0.5 rounded bg-surface-container hover:bg-surface-container-high text-[10px] text-on-surface",
          onclick: () => insertPlaceholder("{{instruction}}"),
        }, "+ 写作要求"),
      )
    );

    const bodyEditor = ui.el("textarea", {
      class: "w-full flex-1 p-3 rounded-lg border border-outline-variant bg-surface text-on-surface font-mono text-xs leading-relaxed focus:outline-none focus:border-primary resize-none",
      value: skill.body_md || "",
      placeholder: "输入 SKILL.md Markdown 指令...",
    });

    function insertPlaceholder(ph) {
      const start = bodyEditor.selectionStart;
      const end = bodyEditor.selectionEnd;
      const val = bodyEditor.value;
      bodyEditor.value = val.substring(0, start) + ph + val.substring(end);
      bodyEditor.selectionStart = bodyEditor.selectionEnd = start + ph.length;
      bodyEditor.focus();
    }

    rightCol.append(rightHeader, bodyEditor);
    modalBody.append(leftCol, rightCol);

    // 保存主技能
    async function doSave() {
      const payload = {
        name: nameInput.value.trim(),
        title: titleInput.value.trim(),
        description: descInput.value.trim(),
        applies_to: appliesSelect.value,
        version: verInput.value.trim() || "1.0.0",
        body_md: bodyEditor.value,
      };

      if (!payload.name) {
        ui.toast("请填写规范名称", "err");
        nameInput.focus();
        return;
      }
      const nameRegex = /^[a-z0-9][a-z0-9-]{0,63}$/;
      if (!nameRegex.test(payload.name)) {
        ui.toast("规范名称格式不正确：仅支持小写字母、数字及连字符 -（不可使用下划线或大写）", "err");
        nameInput.focus();
        return;
      }
      if (!payload.description) {
        ui.toast("请填写触发描述", "err");
        descInput.focus();
        return;
      }

      try {
        if (skillId) {
          await api.patch(`/skills/${skillId}`, payload);
          ui.toast("Skill 保存成功", "ok");
        } else {
          await api.post("/skills", payload);
          ui.toast("Skill 新建成功", "ok");
        }
        document.getElementById("modal-root").innerHTML = "";
        await loadSkills();
      } catch (err) {
        ui.toast(`保存失败：${err.message}`, "err");
      }
    }

    // 挂载文件新建提示
    async function promptNewFile(sId) {
      if (!sId) {
        ui.toast("请先保存该 Skill 基础信息后再挂载资源文件", "info");
        return;
      }
      const p = prompt("请输入文件相对路径（必须以 scripts/、references/ 或 assets/ 开头）：", "references/lore-guide.txt");
      if (!p) return;
      try {
        await api.put(`/skills/${sId}/files/${encodeURIComponent(p)}`, { content: "# 示例资源内容\n" });
        ui.toast("资源文件已创建", "ok");
        const updated = await api.get(`/skills/${sId}`);
        skill.files = updated.files;
        renderFileList(skill.files);
      } catch (err) {
        ui.toast("创建失败: " + err.message, "err");
      }
    }

    // 文件内容编辑弹窗
    async function openFileEditor(sId, filePath) {
      try {
        const fileObj = await api.get(`/skills/${sId}/files/${encodeURIComponent(filePath)}`);
        const fArea = ui.el("textarea", {
          class: "w-full h-72 p-3 font-mono text-xs rounded border border-outline-variant bg-surface text-on-surface focus:outline-none focus:border-primary resize-none",
          value: fileObj.content || "",
        });
        ui.modal(`编辑参考文档 · ${filePath}`, fArea, [
          ui.el("button", {
            class: "px-3 py-1.5 rounded bg-surface-container text-on-surface text-xs",
            onclick: () => document.getElementById("modal-root").innerHTML = "",
          }, "取消"),
          ui.el("button", {
            class: "px-4 py-1.5 rounded bg-primary text-on-primary text-xs font-medium",
            onclick: async () => {
              try {
                await api.put(`/skills/${sId}/files/${encodeURIComponent(filePath)}`, { content: fArea.value });
                ui.toast("文件已保存", "ok");
                document.getElementById("modal-root").innerHTML = "";
                const updated = await api.get(`/skills/${sId}`);
                skill.files = updated.files;
                renderFileList(skill.files);
              } catch (e) {
                ui.toast("保存失败: " + e.message, "err");
              }
            }
          }, "保存文件")
        ]);
      } catch (e) {
        ui.toast("读取文件失败: " + e.message, "err");
      }
    }

    ui.modal(skillId ? `编辑 Skill · ${skill.title}` : "新建 Agent Skill", modalBody, [
      ui.el("button", {
        class: "px-4 py-1.5 rounded-full bg-surface-container text-on-surface hover:bg-surface-container-high text-xs",
        onclick: () => document.getElementById("modal-root").innerHTML = "",
      }, "取消"),
      ui.el("button", {
        class: "px-5 py-1.5 rounded-full bg-primary text-on-primary font-medium hover:bg-primary-container text-xs shadow-sm",
        onclick: doSave,
      }, "保存技能"),
    ]);
  }

  renderTabs();
  await loadSkills();
});