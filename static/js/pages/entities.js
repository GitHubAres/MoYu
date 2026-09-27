/* 万象谱页（对应设计稿 _4）：分类 Tab + 条目列表 + 角色详情卡 */
const _ent = { selected: {} };

registerPage("entities", async (view, { segs }) => {
  const workId = Number(segs[0]) || null;
  if (!workId) return entitiesPickWork(view);

  const CATS = [
    { key: "character", label: "角色", icon: "person" },
    { key: "place", label: "地点", icon: "location_on" },
    { key: "faction", label: "势力", icon: "temple_buddhist" },
    { key: "item", label: "物品", icon: "colorize" },
    { key: "term", label: "术语", icon: "menu_book" },
    { key: "custom", label: "自定义", icon: "bookmark" },
  ];
  const CHAR_FIELDS = [
    { key: "identity", label: "身份" },
    { key: "personality", label: "性格" },
    { key: "background", label: "背景" },
    { key: "goal", label: "目标与变化" },
  ];

  let work, volumes;
  try {
    [work, volumes] = await Promise.all([
      api.get(`/works/${workId}`),
      api.get(`/works/${workId}/tree`),
    ]);
  } catch (e) { ui.toast(e.message, "err"); return; }

  let activeCat = "all";      // all | character... | archived
  let q = "";
  let items = [];

  ui.setCrumb("万象谱", work.title);
  ui.setActions(
    ui.el("button", {
      class: "flex items-center gap-1 px-space-sm py-1.5 rounded-full bg-primary text-on-primary shadow-[0_2px_12px_rgba(6,21,35,0.2)] hover:bg-primary-container transition-all",
      onclick: () => createEntity(),
    }, ui.icon("add", "text-[18px]"), ui.el("span", { class: "font-label-md text-label-md" }, "新建设定条目")),
  );

  const searchInput = ui.el("input", {
    class: "w-full bg-transparent outline-none font-body-sm text-body-sm",
    placeholder: "搜索人物、功法、秘境或法宝…",
  });
  searchInput.addEventListener("input", debounce(() => { q = searchInput.value.trim(); load(); }, 300));

  const tabsBox = ui.el("div", { class: "flex items-center gap-1 flex-wrap" });
  const listBox = ui.el("div", { class: "flex flex-col gap-space-sm max-h-[68vh] overflow-y-auto pr-1" });
  const detailBox = ui.el("div", { class: "flex flex-col gap-space-md" });

  view.append(
    ui.el("div", { class: "flex flex-col gap-space-lg" },
      ui.el("div", { class: "flex flex-col gap-1" },
        ui.el("span", { class: "font-label-sm text-label-sm text-secondary tracking-widest uppercase" }, "LORE ARCHIVE · 万象谱"),
        ui.el("h1", { class: "font-display text-display text-primary tracking-tight" }, "万象谱 · 世界观设定卷宗"),
        ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" },
          "贯通全书架构与人物血肉：角色 / 地点 / 势力 / 物品 / 术语分类管理，可关联章节。")),
      ui.el("div", { class: "flex items-center gap-2 bg-surface-container-lowest rounded-xl px-space-md py-space-sm shadow-[0_4px_20px_rgba(6,21,35,0.03)]" },
        ui.icon("search", "text-[20px] text-on-surface-variant"), searchInput),
      tabsBox,
      ui.el("div", { class: "grid grid-cols-12 gap-space-lg items-start" },
        ui.el("aside", { class: "col-span-12 lg:col-span-4 flex flex-col gap-space-sm" }, listBox),
        ui.el("main", { class: "col-span-12 lg:col-span-8" }, detailBox))));

  /* ---------- 数据加载 ---------- */

  async function load(keepSelection = true) {
    try {
      items = await api.get(
        `/works/${workId}/entities?archived=${activeCat === "archived" ? 1 : 0}` +
        (q ? `&q=${encodeURIComponent(q)}` : ""));
    } catch (e) { ui.toast(e.message, "err"); return; }
    const visible = activeCat === "all" || activeCat === "archived"
      ? items
      : items.filter((e) => e.category === activeCat);
    if (!keepSelection || !visible.some((e) => e.id === _ent.selected[workId])) {
      _ent.selected[workId] = visible.length ? visible[0].id : null;
    }
    renderTabs();
    renderList(visible);
    renderDetail(visible);
  }

  /* ---------- 顶部分类 Tab ---------- */

  function renderTabs() {
    tabsBox.innerHTML = "";
    const tabs = [{ key: "all", label: "全部" }, ...CATS, { key: "archived", label: "已归档", icon: "archive" }];
    for (const t of tabs) {
      const count = t.key === "archived"
        ? null
        : t.key === "all" ? items.length : items.filter((e) => e.category === t.key).length;
      tabsBox.append(ui.el("button", {
        class: "px-3 py-1.5 rounded-full font-label-md text-label-md transition-all " +
          (activeCat === t.key
            ? "bg-primary-container text-on-primary font-semibold"
            : "bg-surface-container-lowest text-on-surface-variant hover:text-on-surface hover:bg-surface-container"),
        onclick: () => { activeCat = t.key; load(false); },
      }, t.label + (count === null ? "" : ` (${count})`)));
    }
  }

  /* ---------- 左侧条目列表 ---------- */

  function catMeta(key) { return CATS.find((c) => c.key === key) || CATS[5]; }

  function renderList(visible) {
    listBox.innerHTML = "";
    if (!visible.length) {
      const meta = CATS.find((c) => c.key === activeCat);
      listBox.append(ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-lg flex flex-col items-center gap-space-sm text-center shadow-[0_4px_20px_rgba(6,21,35,0.03)]" },
        ui.icon(activeCat === "archived" ? "archive" : (meta ? meta.icon : "group"), "text-[36px] text-outline-variant"),
        ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant" },
          activeCat === "archived" ? "没有已归档的条目" : q ? `没有找到与「${q}」相关的条目` : "该分类暂无设定条目"),
        activeCat !== "archived" && ui.el("button", {
          class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md",
          onclick: () => createEntity(),
        }, meta ? `新建${meta.label}` : "新建条目")));
      return;
    }
    for (const e of visible) {
      const meta = catMeta(e.category);
      const tags = (e.tags || "").split(/[,，]/).map((t) => t.trim()).filter(Boolean);
      const selected = e.id === _ent.selected[workId];
      listBox.append(ui.el("div", {
        class: "rounded-xl p-space-md cursor-pointer transition-all duration-200 " +
          (selected
            ? "bg-primary-container text-on-primary shadow-md"
            : "bg-surface-container-lowest hover:bg-surface-container-low shadow-[0_4px_20px_rgba(6,21,35,0.03)] hover:shadow-md"),
        onclick: () => { _ent.selected[workId] = e.id; renderList(visible); renderDetail(visible); },
      },
        ui.el("div", { class: "flex items-start gap-space-sm" },
          ui.el("div", {
            class: "w-11 h-11 rounded-xl flex items-center justify-center shrink-0 " +
              (selected ? "bg-on-primary/10 text-on-primary" : "bg-surface-container-high text-on-surface"),
          }, ui.icon(meta.icon, "text-[22px]")),
          ui.el("div", { class: "flex flex-col min-w-0 flex-1" },
            ui.el("div", { class: "flex items-center justify-between gap-2" },
              ui.el("div", { class: "flex items-center gap-1.5 min-w-0" },
                ui.el("span", { class: "font-headline-sm text-headline-sm font-medium truncate " + (selected ? "text-on-primary" : "text-on-surface") }, e.name),
                ui.el("span", { class: "px-1.5 py-0.5 rounded font-label-sm text-label-sm shrink-0 " + (selected ? "bg-on-primary/15 text-on-primary" : "bg-surface-container text-on-surface-variant") }, meta.label)),
              ui.el("span", { class: "font-label-sm text-label-sm shrink-0 " + (selected ? "text-on-primary-container" : "text-on-surface-variant") },
                (e.updated_at || "").slice(5, 16))),
            ui.el("p", { class: "font-body-sm text-body-sm truncate mt-0.5 " + (selected ? "text-on-primary-container" : "text-on-surface-variant") },
              previewOf(e)),
            tags.length && ui.el("div", { class: "flex items-center gap-1.5 mt-1.5 flex-wrap" },
              tags.slice(0, 3).map((t) => ui.el("span", {
                class: "inline-flex items-center gap-1 font-label-sm text-label-sm " + (selected ? "text-on-primary-container" : "text-on-surface-variant"),
              }, ui.el("span", { class: "w-1.5 h-1.5 rounded-full " + (selected ? "bg-on-primary-container" : "bg-outline-variant") }), t)))))));
    }
  }

  function previewOf(e) {
    if (e.category === "character") {
      const f = e.fields || {};
      return [f.identity, f.personality].filter(Boolean).join(" · ") || (e.content || "").slice(0, 40) || "（尚未填写设定）";
    }
    return (e.content || "").slice(0, 40) || "（尚未填写设定）";
  }

  /* ---------- 右侧详情 ---------- */

  function renderDetail(visible) {
    detailBox.innerHTML = "";
    const e = visible.find((x) => x.id === _ent.selected[workId]);
    if (!e) {
      detailBox.append(ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-xl flex flex-col items-center gap-space-md text-center shadow-[0_4px_20px_rgba(6,21,35,0.03)]" },
        ui.icon("group", "text-[48px] text-outline-variant"),
        ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" }, "从左侧选择条目，或新建一条设定")));
      return;
    }
    const meta = catMeta(e.category);
    const fields = e.fields || {};
    const archived = !!e.archived;

    const nameInput = ui.el("input", {
      class: "font-display text-[28px] leading-tight text-primary font-semibold tracking-tight bg-transparent outline-none border-b border-transparent focus:border-primary w-full",
      value: e.name,
    });

    /* 字段编辑区：角色模板 / 通用大文本 */
    let bodySection;
    const fieldInputs = {};
    if (e.category === "character") {
      bodySection = ui.el("div", { class: "grid grid-cols-1 md:grid-cols-2 gap-space-sm" },
        CHAR_FIELDS.map((f) => {
          const ta = ui.el("textarea", {
            class: "w-full bg-transparent outline-none font-body-sm text-body-sm text-on-surface resize-y min-h-[64px]",
            placeholder: `填写${f.label}…`,
          }, fields[f.key] || "");
          fieldInputs[f.key] = ta;
          return ui.el("div", { class: "bg-surface-container-low/70 rounded-xl p-space-sm flex flex-col gap-1" },
            ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, f.label), ta);
        }));
    } else {
      fieldInputs.__content = ui.el("textarea", {
        class: "w-full bg-surface-container-low/70 rounded-xl p-space-md outline-none font-serif-content text-body-md text-body-md leading-relaxed resize-y min-h-[240px]",
        placeholder: "记录该设定的详细描述…",
      }, e.content || "");
      bodySection = fieldInputs.__content;
    }

    const tagsInput = ui.el("input", {
      class: "w-full px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-sm text-body-sm",
      placeholder: "标签，用逗号分隔（如 主角, 剑修, 金丹期）",
      value: e.tags || "",
    });

    const chaptersBox = ui.el("div", { class: "flex flex-col gap-2" });

    detailBox.append(ui.el("div", {
      class: "bg-surface-container-lowest rounded-2xl p-space-lg shadow-[0_4px_20px_rgba(6,21,35,0.03)] flex flex-col gap-space-lg relative overflow-hidden",
    },
      ui.el("div", { class: "absolute -right-20 -top-20 w-72 h-72 rounded-full bg-secondary-fixed/30 blur-3xl pointer-events-none" }),
      /* 头部 */
      ui.el("div", { class: "flex flex-col md:flex-row md:items-start justify-between gap-space-md relative" },
        ui.el("div", { class: "flex items-start gap-space-md min-w-0 flex-1" },
          ui.el("div", { class: "w-14 h-14 rounded-2xl bg-primary-container text-on-primary flex items-center justify-center shrink-0 shadow-md" },
            ui.icon(meta.icon, "text-[26px]")),
          ui.el("div", { class: "flex flex-col gap-1 min-w-0 flex-1" },
            nameInput,
            ui.el("div", { class: "flex flex-wrap items-center gap-space-xs" },
              ui.el("span", { class: "px-2 py-0.5 rounded-full bg-primary-fixed text-on-primary-fixed font-label-sm text-label-sm font-semibold" }, meta.label),
              archived && ui.el("span", { class: "px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant font-label-sm text-label-sm" }, "已归档"),
              ui.el("span", { class: "px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant font-label-sm text-label-sm" },
                `最后修订：${e.updated_at || "-"}`)))),
        ui.el("div", { class: "flex items-center gap-space-xs shrink-0" },
          ui.el("button", {
            class: "flex items-center gap-1.5 px-space-md py-2.5 rounded-xl bg-secondary-container text-on-secondary-container shadow-md hover:bg-secondary hover:text-on-secondary transition-all font-label-md text-label-md font-semibold",
            onclick: () => saveEntity(e),
          }, ui.icon("save", "text-[18px]"), "保存"),
          ui.el("button", {
            class: "p-2 rounded-xl bg-surface-container hover:bg-surface-container-high text-on-surface-variant transition-all",
            title: archived ? "取消归档" : "归档",
            onclick: async () => {
              try {
                await api.post(`/entities/${e.id}/archive`);
                ui.toast(archived ? "已取消归档" : "已归档", "ok");
                load(false);
              } catch (err) { ui.toast(err.message, "err"); }
            },
          }, ui.icon(archived ? "unarchive" : "archive", "text-[20px]")),
          ui.el("button", {
            class: "p-2 rounded-xl bg-surface-container hover:bg-error-container text-on-surface-variant hover:text-error transition-all",
            title: "删除",
            onclick: async () => {
              const ok = await ui.confirm("删除设定条目",
                `将永久删除「${e.name}」及其章节关联，且不可恢复。确定继续？`, "删除", true);
              if (!ok) return;
              try {
                await api.del(`/entities/${e.id}`);
                ui.toast("已删除", "ok");
                _ent.selected[workId] = null;
                load(false);
              } catch (err) { ui.toast(err.message, "err"); }
            },
          }, ui.icon("delete", "text-[20px]")))),
      /* 模板字段 / 正文 */
      ui.el("div", { class: "flex flex-col gap-2 relative" },
        ui.el("div", { class: "flex items-center gap-2" },
          ui.icon(e.category === "character" ? "badge" : "article", "text-[18px] text-secondary"),
          ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary" },
            e.category === "character" ? "角色设定档案" : "设定详情")),
        bodySection),
      /* 标签 */
      ui.el("div", { class: "flex flex-col gap-1.5 relative" },
        ui.el("div", { class: "flex items-center gap-2" },
          ui.icon("sell", "text-[18px] text-secondary"),
          ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary" }, "标签")),
        tagsInput),
      /* 关联章节 */
      ui.el("div", { class: "flex flex-col gap-2 relative" },
        ui.el("div", { class: "flex items-center gap-2" },
          ui.icon("menu_book", "text-[18px] text-secondary"),
          ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary" }, "章节引用与登场记录")),
        chaptersBox)));

    renderEntityChapters(e);

    async function saveEntity(ent) {
      const body = { name: nameInput.value.trim() || ent.name, tags: tagsInput.value.trim() };
      if (ent.category === "character") {
        body.fields_json = {};
        for (const f of CHAR_FIELDS) body.fields_json[f.key] = fieldInputs[f.key].value.trim();
        body.content = body.fields_json.background || "";
      } else {
        body.content = fieldInputs.__content.value;
      }
      try {
        await api.patch(`/entities/${ent.id}`, body);
        ui.toast("设定已保存", "ok");
        load();
      } catch (err) { ui.toast(err.message, "err"); }
    }

    async function renderEntityChapters(ent) {
      chaptersBox.innerHTML = "";
      let linked = [];
      try { linked = await api.get(`/entities/${ent.id}/chapters`); }
      catch (err) { ui.toast(err.message, "err"); return; }
      if (linked.length) {
        const chips = ui.el("div", { class: "flex flex-wrap gap-2" });
        for (const c of linked) {
          chips.append(ui.el("span", {
            class: "inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-surface-container-low font-label-sm text-label-sm text-on-surface",
          },
            ui.el("a", {
              class: "hover:text-secondary transition-colors cursor-pointer",
              onclick: () => { location.hash = `#/workbench/${workId}?chapter=${c.id}`; },
            }, `${c.volume_title} · ${c.title}`),
            ui.el("button", {
              class: "text-on-surface-variant hover:text-error transition-colors",
              title: "移除关联",
              onclick: async () => {
                try {
                  await api.del(`/entities/${ent.id}/chapters/${c.id}`);
                  renderEntityChapters(ent);
                } catch (err) { ui.toast(err.message, "err"); }
              },
            }, ui.icon("close", "text-[14px]"))));
        }
        chaptersBox.append(chips);
      } else {
        chaptersBox.append(ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant" }, "尚未关联任何章节。"));
      }
      /* 添加关联 */
      const all = [];
      for (const v of volumes) for (const c of v.chapters) all.push({ ...c, volume_title: v.title });
      const available = all.filter((c) => !linked.some((l) => l.id === c.id));
      if (available.length) {
        const sel = ui.el("select", {
          class: "px-3 py-1.5 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-sm text-body-sm",
        });
        for (const c of available) sel.append(ui.el("option", { value: c.id }, `${c.volume_title} · ${c.title}`));
        chaptersBox.append(ui.el("div", { class: "flex items-center gap-2" },
          sel,
          ui.el("button", {
            class: "flex items-center gap-1 px-3 py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md transition-colors",
            onclick: async () => {
              try {
                await api.post(`/entities/${ent.id}/chapters`, { chapter_id: Number(sel.value) });
                renderEntityChapters(ent);
                ui.toast("已关联章节", "ok");
              } catch (err) { ui.toast(err.message, "err"); }
            },
          }, ui.icon("add_link", "text-[16px]"), "添加关联")));
      }
    }
  }

  /* ---------- 新建 ---------- */

  async function createEntity() {
    const meta = CATS.find((c) => c.key === activeCat);
    const name = await ui.prompt("新建设定条目",
      `分类：${meta ? meta.label : "角色"} · 输入名称`);
    if (!name) return;
    try {
      const e = await api.post(`/works/${workId}/entities`, {
        category: meta ? meta.key : "character",
        name,
      });
      _ent.selected[workId] = e.id;
      ui.toast(`「${name}」已创建`, "ok");
      if (activeCat === "archived") activeCat = "all";
      load();
    } catch (err) { ui.toast(err.message, "err"); }
  }

  function debounce(fn, ms) {
    let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
  }

  await load(false);
});

/* 无 workId 时：作品选择列表 */
async function entitiesPickWork(view) {
  ui.setCrumb("万象谱");
  let works = [];
  try { works = await api.get("/works"); } catch (e) { ui.toast(e.message, "err"); }
  const list = ui.el("div", { class: "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-space-md" });
  view.append(
    ui.el("div", { class: "flex flex-col gap-space-lg" },
      ui.el("div", { class: "flex flex-col gap-1" },
        ui.el("span", { class: "font-label-sm text-label-sm text-secondary tracking-widest uppercase" }, "LORE ARCHIVE · 万象谱"),
        ui.el("h1", { class: "font-display text-display text-primary tracking-tight" }, "选择一部作品"),
        ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" }, "选择要管理设定条目（角色 / 地点 / 势力…）的作品。")),
      list));
  if (!works.length) {
    list.append(ui.el("div", { class: "col-span-full flex flex-col items-center gap-space-md py-space-xl text-center" },
      ui.icon("group", "text-[48px] text-outline-variant"),
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
      onclick: () => { location.hash = `#/entities/${w.id}`; },
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
