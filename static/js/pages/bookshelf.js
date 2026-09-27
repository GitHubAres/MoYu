/* 书架页（对应设计稿 _1） */
registerPage("bookshelf", async (view) => {
  ui.setCrumb("书架作品");
  ui.setActions(
    ui.el("button", {
      class: "flex items-center gap-1 px-space-sm py-1.5 rounded-full bg-surface-container hover:bg-surface-container-high text-on-surface transition-all",
      onclick: () => { location.hash = "#/io"; },
    }, ui.icon("upload_file", "text-[18px]"), ui.el("span", { class: "font-label-md text-label-md" }, "导入作品")),
    ui.el("button", {
      class: "flex items-center gap-1 px-space-sm py-1.5 rounded-full bg-primary text-on-primary shadow-[0_2px_12px_rgba(6,21,35,0.2)] hover:bg-primary-container transition-all",
      onclick: createWorkDialog,
    }, ui.icon("add", "text-[18px]"), ui.el("span", { class: "font-label-md text-label-md" }, "新建长篇作品")),
  );

  const hour = new Date().getHours();
  const greet = hour < 6 ? "夜深了" : hour < 12 ? "早安" : hour < 18 ? "午安" : "晚上好";

  const grid = ui.el("div", { class: "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-space-md" });
  const searchInput = ui.el("input", {
    class: "w-full bg-transparent outline-none font-body-sm text-body-sm",
    placeholder: "搜索作品…",
  });
  searchInput.addEventListener("input", debounce(() => load(searchInput.value.trim()), 300));

  view.append(
    ui.el("div", { class: "flex flex-col gap-space-lg" },
      ui.el("div", { class: "flex flex-col gap-1" },
        ui.el("span", { class: "font-label-sm text-label-sm text-secondary tracking-widest uppercase" }, "CREATOR DASHBOARD · 本地"),
        ui.el("h1", { class: "font-display text-display text-primary tracking-tight" }, `${greet}，执笔人`),
        ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" }, "晨光熹微，灵思自生。今天的故事正等待与你相逢。")),
      ui.el("div", { class: "flex flex-col xl:flex-row gap-space-lg items-start" },
        ui.el("div", { class: "flex-1 min-w-0 flex flex-col gap-space-md w-full" },
          ui.el("div", { class: "flex items-center gap-2 bg-surface-container-lowest rounded-xl px-space-md py-space-sm shadow-[0_4px_20px_rgba(6,21,35,0.03)]" },
            ui.icon("search", "text-[20px] text-on-surface-variant"), searchInput),
          grid),
        notesPanel())));

  /* ---------- 灵感便签侧栏 ---------- */
  function notesPanel() {
    const list = ui.el("div", { class: "flex flex-col gap-2 max-h-[420px] overflow-y-auto" });
    const input = ui.el("textarea", {
      class: "w-full px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-sm text-body-sm resize-none",
      rows: "3", placeholder: "捕捉掠过脑海的伏笔、绝妙对白或世界法则…",
    });
    const panel = ui.el("div", {
      class: "w-full xl:w-72 shrink-0 bg-surface-container-lowest rounded-xl p-space-md shadow-[0_4px_20px_rgba(6,21,35,0.03)] flex flex-col gap-space-sm",
    },
      ui.el("div", { class: "flex items-center justify-between" },
        ui.el("div", { class: "flex items-center gap-1" },
          ui.icon("lightbulb", "text-[18px] text-secondary"),
          ui.el("span", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, "灵感便签")),
        ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "随手记")),
      input,
      ui.el("button", {
        class: "self-end px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-md text-label-md hover:bg-primary-container transition-colors",
        onclick: async () => {
          const text = input.value.trim();
          if (!text) return;
          await api.post("/notes", { content: text });
          input.value = "";
          loadNotes();
        },
      }, "记录"),
      list);

    async function loadNotes() {
      list.innerHTML = "";
      let notes;
      try { notes = await api.get("/notes"); } catch (e) { return; }
      if (!notes.length) {
        list.append(ui.el("div", { class: "text-center py-space-md font-label-sm text-label-sm text-on-surface-variant" },
          "暂无便签——灵感稍纵即逝，记下第一句吧"));
        return;
      }
      for (const n of notes) {
        list.append(ui.el("div", {
          class: "group p-space-sm rounded-lg bg-surface-container-low hover:bg-surface-container-high transition-colors flex flex-col gap-1",
        },
          ui.el("div", { class: "font-body-sm text-body-sm text-on-surface whitespace-pre-wrap" }, n.content),
          ui.el("div", { class: "flex items-center justify-between" },
            ui.el("span", { class: "font-label-sm text-label-sm text-outline" }, (n.created_at || "").slice(5, 16)),
            ui.el("div", { class: "flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity" },
              ui.el("button", {
                class: "p-1 rounded text-on-surface-variant hover:text-primary", title: "编辑",
                onclick: async () => {
                  const t = await ui.prompt("编辑便签", "", n.content);
                  if (t === null) return;
                  await api.patch(`/notes/${n.id}`, { content: t });
                  loadNotes();
                },
              }, ui.icon("edit", "text-[14px]")),
              ui.el("button", {
                class: "p-1 rounded text-on-surface-variant hover:text-error", title: "删除",
                onclick: async () => {
                  if (!await ui.confirm("删除便签", "删除后不可恢复，确定？", "删除", true)) return;
                  await api.del(`/notes/${n.id}`);
                  loadNotes();
                },
              }, ui.icon("delete", "text-[14px]"))))));
      }
    }
    loadNotes();
    return panel;
  }

  async function createWorkDialog() {
    const title = await ui.prompt("新建作品", "请输入书名");
    if (!title) return;
    try {
      const w = await api.post("/works", { title });
      const vol = await api.post("/volumes", { work_id: w.id, title: "卷一" });
      const ch = await api.post("/chapters", { volume_id: vol.id, title: "第一章" });
      ui.toast(`《${title}》已创建`, "ok");
      location.hash = `#/workbench/${w.id}?chapter=${ch.id}`;
    } catch (e) { ui.toast(e.message, "err"); }
  }

  async function load(q = "") {
    grid.innerHTML = "";
    let works;
    try { works = await api.get("/works" + (q ? "?q=" + encodeURIComponent(q) : "")); }
    catch (e) { ui.toast(e.message, "err"); return; }

    if (!works.length) {
      grid.append(ui.el("div", {
        class: "col-span-full flex flex-col items-center gap-space-md py-space-xl text-center",
      },
        ui.icon("auto_stories", "text-[48px] text-outline-variant"),
        ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" },
          q ? `没有找到与「${q}」相关的作品` : "书架还是空的，从创建第一部作品开始吧"),
        !q && ui.el("div", { class: "flex gap-2" },
          ui.el("button", { class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md", onclick: createWorkDialog }, "创建作品"),
          ui.el("button", { class: "px-4 py-2 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md", onclick: () => location.hash = "#/io" }, "导入作品"),
          ui.el("button", {
            class: "px-4 py-2 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md text-on-surface-variant",
            onclick: async () => {
              try {
                const r = await api.post("/seed/demo");
                ui.toast(r.message, r.ok ? "ok" : "info");
                load();
              } catch (e) { ui.toast(e.message, "err"); }
            },
          }, "创建示例作品"))));
      return;
    }

    for (const w of works) {
      grid.append(workCard(w));
    }
  }

  function workCard(w) {
    const card = ui.el("div", {
      class: "bg-surface-container-lowest rounded-xl p-space-md shadow-[0_4px_20px_rgba(6,21,35,0.03)] flex flex-col gap-space-sm hover:shadow-[0_8px_28px_rgba(6,21,35,0.08)] transition-shadow",
    },
      ui.el("div", { class: "flex gap-space-sm" },
        w.cover_image
          ? ui.el("img", {
              src: `/api/images/${w.cover_image}/file`, alt: w.title || "封面",
              class: "w-14 h-20 rounded-lg shrink-0 object-cover",
            })
          : ui.el("div", {
              class: "w-14 h-20 rounded-lg shrink-0 flex items-center justify-center text-on-primary font-headline-sm text-headline-sm font-bold",
              style: `background:linear-gradient(135deg, ${w.cover_color}, #1B2A38)`,
            }, (w.title || "书")[0]),
        ui.el("div", { class: "flex flex-col min-w-0 flex-1" },
          ui.el("div", { class: "flex items-center gap-2" },
            ui.el("span", { class: "px-2 py-0.5 rounded-full bg-primary-fixed text-on-primary-fixed font-label-sm text-label-sm" }, w.status || "连载中"),
            ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, w.updated_at || "")),
          ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold truncate mt-1" }, w.title),
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" },
            `${w.genre || "未分类"} · ${ui.fmtWords(w.total_words)} 字`))),
      w.last_chapter && ui.el("div", { class: "text-on-surface-variant font-body-sm text-body-sm bg-surface-container-low rounded-lg px-space-sm py-space-xs" },
        "最近：" + w.last_chapter.title),
      ui.el("div", { class: "flex items-center gap-2 pt-1" },
        ui.el("button", {
          class: "flex-1 flex items-center justify-center gap-1 py-2 rounded-lg bg-secondary-container text-on-secondary-container font-label-md text-label-md hover:bg-secondary transition-colors",
          onclick: async () => {
            const chId = w.last_chapter ? w.last_chapter.id : await firstChapter(w.id);
            location.hash = chId ? `#/workbench/${w.id}?chapter=${chId}` : `#/workbench/${w.id}`;
          },
        }, ui.icon("edit", "text-[16px]"), "继续写作"),
        ui.el("button", {
          class: "p-2 rounded-lg bg-surface-container-low text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-colors",
          title: "重命名",
          onclick: async () => {
            const t = await ui.prompt("重命名作品", "书名", w.title);
            if (!t) return;
            await api.patch(`/works/${w.id}`, { title: t });
            load(searchInput.value.trim());
          },
        }, ui.icon("edit_square", "text-[18px]")),
        ui.el("button", {
          class: "p-2 rounded-lg bg-surface-container-low text-on-surface-variant hover:text-error hover:bg-error-container transition-colors",
          title: "删除",
          onclick: async () => {
            const ok = await ui.confirm("删除作品", `将删除《${w.title}》及其全部卷、章节、大纲与设定，且不可恢复。确定继续？`, "删除", true);
            if (!ok) return;
            await api.del(`/works/${w.id}`);
            ui.toast("已删除", "ok");
            load(searchInput.value.trim());
          },
        }, ui.icon("delete", "text-[18px]"))));
    return card;
  }

  async function firstChapter(workId) {
    const tree = await api.get(`/works/${workId}/tree`);
    for (const v of tree) if (v.chapters.length) return v.chapters[0].id;
    return null;
  }

  function debounce(fn, ms) {
    let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
  }

  await load();
});
