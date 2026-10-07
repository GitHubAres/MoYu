
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
  const statsBox = ui.el("div", { class: "grid grid-cols-2 md:grid-cols-4 gap-2 sm:gap-space-md" });
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
      ui.el("div", { class: "flex flex-col gap-space-md w-full" },
          statsBox,
          ui.el("div", { class: "flex items-center gap-2 bg-surface-container-lowest rounded-xl px-space-md py-space-sm shadow-[0_4px_20px_rgba(6,21,35,0.03)]" },
            ui.icon("search", "text-[20px] text-on-surface-variant"), searchInput),
          grid)));

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


  function renderStats(s) {
    s = s || {};
    const items = [
      { label: "累计字数", value: ui.fmtWords(s.total_words || 0), icon: "auto_stories" },
      { label: "今日字数", value: ui.fmtWords(s.today_words || 0), icon: "edit_note" },
      { label: "作品总数", value: s.work_count || 0, icon: "collections_bookmark" },
      { label: "章节总数", value: s.chapter_count || 0, icon: "menu_book" },
    ];
    statsBox.innerHTML = "";
    for (const it of items) {
      statsBox.append(ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-md shadow-[0_4px_20px_rgba(6,21,35,0.03)] flex items-center gap-space-sm" },
        ui.el("div", { class: "w-10 h-10 rounded-full bg-secondary-container flex items-center justify-center text-on-secondary-container" },
          ui.icon(it.icon, "text-[20px]")),
        ui.el("div", { class: "flex flex-col" },
          ui.el("span", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, String(it.value)),
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, it.label))));
    }
  }

  async function load(q = "") {
    grid.innerHTML = "";
    let stats, works;
    try { stats = await api.get("/stats/dashboard"); } catch (e) { stats = {}; }
    renderStats(stats);
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
            onclick: async (e) => {
              const btn = e.currentTarget;
              if (btn && btn.disabled) return;
              if (btn) btn.disabled = true;
              try {
                const r = await api.post("/seed/demo");
                ui.toast(r.message, r.ok ? "ok" : "info");
                load();
              } catch (e) {
                ui.toast(e.message, "err");
                if (btn) btn.disabled = false;
              }
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
            try {
              let chId = w.last_chapter && w.last_chapter.id ? w.last_chapter.id : null;
              if (!chId) chId = await firstChapter(w.id);
              location.hash = chId ? `#/workbench/${w.id}?chapter=${chId}` : `#/workbench/${w.id}`;
            } catch (e) {
              ui.toast("打开作品失败：" + e.message, "err");
              location.hash = `#/workbench/${w.id}`;
            }
          },
        }, ui.icon("edit", "text-[16px]"), "继续写作"),
        ui.el("button", {
          class: "p-2 rounded-lg bg-surface-container-low text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-colors",
          title: "编辑属性",
          onclick: () => editWorkDialog(w),
        }, ui.icon("tune", "text-[18px]")),
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
            try {
              await api.del(`/works/${w.id}`);
              ui.toast("已删除", "ok");
              load(searchInput.value.trim());
            } catch (e) {
              ui.toast("删除作品失败：" + (e.message || "网络异常"), "err");
            }
          },
        }, ui.icon("delete", "text-[18px]"))));
    return card;
  }

  
  async function editWorkDialog(w) {
    const GENRES = ["玄幻", "仙侠", "都市", "科幻", "历史", "言情", "悬疑", "其他"];
    const STATUSES = ["连载中", "已完结", "暂停", "草稿"];
    const PRESET_COLORS = ["#1B2A38", "#D9483B", "#5D4037", "#1B5E20", "#0D47A1", "#4A148C", "#263238"];

    const root = document.getElementById("modal-root");
    const genreSel = ui.el("select", { class: "w-full px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-md text-body-md" });
    genreSel.append(ui.el("option", { value: "" }, "未分类"));
    for (const g of GENRES) genreSel.append(ui.el("option", { value: g, selected: w.genre === g ? "selected" : null }, g));
    const statusSel = ui.el("select", { class: "w-full px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-md text-body-md" });
    for (const s of STATUSES) statusSel.append(ui.el("option", { value: s, selected: w.status === s ? "selected" : null }, s));
    const introInput = ui.el("textarea", { class: "w-full px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-sm text-body-sm resize-none", rows: "4", placeholder: "作品简介…" }, w.intro || "");
    const colorInput = ui.el("input", { type: "color", class: "w-12 h-10 rounded cursor-pointer border-0 bg-transparent", value: w.cover_color || "#1B2A38" });
    const colorPresets = ui.el("div", { class: "flex gap-2 flex-wrap" });
    for (const c of PRESET_COLORS) {
      colorPresets.append(ui.el("button", {
        class: "w-8 h-8 rounded-full border-2 border-outline-variant/30 hover:scale-110 transition-transform",
        style: `background:${c}`,
        onclick: (e) => { e.preventDefault(); colorInput.value = c; },
      }));
    }

    const fileInput = ui.el("input", { type: "file", accept: "image/*", class: "hidden" });
    const fileLabel = ui.el("label", {
      class: "flex items-center gap-2 px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather cursor-pointer hover:bg-surface-container transition-colors",
    },
      ui.icon("upload", "text-[18px] text-on-surface-variant"),
      ui.el("span", { class: "font-body-sm text-body-sm text-on-surface-variant" }, "点击选择封面图片（jpg/png，最大 5MB）"));
    fileLabel.append(fileInput);
    fileInput.addEventListener("change", () => {
      const file = fileInput.files && fileInput.files[0];
      fileLabel.querySelector("span").textContent = file ? `已选：${file.name}` : "点击选择封面图片（jpg/png，最大 5MB）";
    });

    let resolve;
    const result = new Promise((res) => { resolve = res; });
    const close = (val) => { overlay.remove(); resolve(val); };
    const overlay = ui.el("div", {
      class: "fixed inset-0 z-[90] bg-ink-black/40 backdrop-blur-sm flex items-center justify-center",
      onclick: (e) => { if (e.target === overlay) close(null); },
    },
      ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-lg w-[480px] max-w-[calc(100vw-2rem)] mx-2 sm:mx-0 shadow-[0_12px_32px_rgba(27,42,56,0.12)] flex flex-col gap-space-md" },
        ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, `编辑《${w.title}》`),
        ui.el("div", { class: "flex flex-col gap-1" },
          ui.el("label", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "分类"),
          genreSel),
        ui.el("div", { class: "flex flex-col gap-1" },
          ui.el("label", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "连载状态"),
          statusSel),
        ui.el("div", { class: "flex flex-col gap-1" },
          ui.el("label", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "简介"),
          introInput),
        ui.el("div", { class: "flex flex-col gap-1" },
          ui.el("label", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "封面底色"),
          ui.el("div", { class: "flex items-center gap-3" }, colorInput, colorPresets)),
        ui.el("div", { class: "flex flex-col gap-1" },
          ui.el("label", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "封面上传"),
          fileLabel),
        ui.el("div", { class: "flex justify-end gap-2" },
          ui.el("button", { class: "px-4 py-2 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md", onclick: () => close(null) }, "取消"),
          ui.el("button", {
            class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md",
            onclick: async () => {
              try {
                const file = fileInput.files && fileInput.files[0];
                if (file) {
                  const form = new FormData();
                  form.append("file", file);
                  const resp = await fetch(`/api/works/${w.id}/cover-upload`, { method: "POST", body: form });
                  if (!resp.ok) {
                    let msg = resp.statusText;
                    try { msg = (await resp.json()).detail || msg; } catch (_) {}
                    throw new Error(msg);
                  }
                }
                const body = {
                  genre: genreSel.value,
                  status: statusSel.value,
                  intro: introInput.value.trim(),
                  cover_color: colorInput.value,
                };
                await api.patch(`/works/${w.id}`, body);
                ui.toast("作品属性已更新", "ok");
                close(true);
                load(searchInput.value.trim());
              } catch (e) { ui.toast(e.message, "err"); }
            },
          }, "保存"))));
    root.append(overlay);
    return result;
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
