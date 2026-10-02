/* 丹青阁 · 作品图片创作中心：作为炼丹炉 Tab4 被调用（window.GalleryTab.render(el)） */
window.GalleryTab = (() => {
  const KIND_META = {
    cover: { label: "封面", icon: "book_2" },
    illustration: { label: "插图", icon: "image" },
  };

  async function render(el) {
    el.innerHTML = "";
    let settings = {}, works = [];
    try {
      [settings, works] = await Promise.all([api.get("/settings"), api.get("/works")]);
    } catch (e) {
      ui.toast(e.message, "err");
    }

    const root = ui.el("div", { class: "flex flex-col gap-space-lg" });
    el.append(root);

    /* ---------- 未配置生图接口：引导卡 ---------- */
    if (!((settings.img_api_key || "").trim() && (settings.img_base_url || "").trim())) {
      root.append(ui.el("div", {
        class: "flex flex-col items-center gap-space-md py-space-xl px-space-lg rounded-xl bg-surface-container-lowest shadow-sm text-center",
      },
        ui.icon("palette", "text-[48px] text-outline-variant"),
        ui.el("h3", { class: "font-headline-md text-headline-md text-primary font-semibold" }, "丹青阁尚未备齐颜料"),
        ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant max-w-md" },
          "生成封面与插图需要配置一个兼容 OpenAI Images 协议的生图接口（推荐 SiliconFlow，可到 platform.siliconflow.cn 申请 Key）。配置完成后即可在此为作品作画。"),
        ui.el("button", {
          class: "flex items-center gap-1.5 px-space-md py-2 rounded-lg bg-primary text-on-primary hover:bg-primary-container transition-all font-label-md text-label-md",
          onclick: () => { location.hash = "#/settings"; },
        }, ui.icon("settings", "text-[18px]"), "前往系统设置配置")));
      return;
    }

    if (!works.length) {
      root.append(ui.el("div", {
        class: "flex flex-col items-center gap-space-md py-space-xl rounded-xl bg-surface-container-lowest shadow-sm text-center",
      },
        ui.icon("auto_stories", "text-[48px] text-outline-variant"),
        ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" }, "书架还没有作品，请先创建作品再来作画。"),
        ui.el("button", {
          class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md",
          onclick: () => { location.hash = "#/bookshelf"; },
        }, "去书架看看")));
      return;
    }

    /* ---------- 状态 ---------- */
    let work = works[0];
    let kind = "cover";
    let images = [];
    let coverId = String(work.cover_image || "");

    const inputCls = "w-full px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-sm text-body-sm";

    /* ---------- 顶部：创作台 ---------- */
    const workSel = ui.el("select", { class: inputCls + " max-w-xs cursor-pointer" },
      works.map((w) => ui.el("option", { value: String(w.id) }, w.title)));
    workSel.value = String(work.id);

    const kindBtns = {};
    function renderKind() {
      for (const k of Object.keys(KIND_META)) {
        const on = k === kind;
        kindBtns[k].className = `flex items-center gap-1 px-space-md py-1.5 rounded-full font-label-md text-label-md transition-all ${
          on ? "bg-primary text-on-primary shadow-sm" : "text-on-surface-variant hover:bg-surface-container-high"}`;
      }
    }
    for (const [k, meta] of Object.entries(KIND_META)) {
      kindBtns[k] = ui.el("button", { onclick: () => { kind = k; renderKind(); } },
        ui.icon(meta.icon, "text-[16px]"), meta.label);
    }
    renderKind();

    const promptTa = ui.el("textarea", {
      class: inputCls + " min-h-[88px] resize-y",
      placeholder: "描述想要的画面：主体、场景、光线、色调、画风… 例如「雨夜古城，青衣剑客立于飞檐之上，冷蓝色调，水墨质感」",
    });

    const suggestBtn = ui.el("button", {
      class: "flex items-center gap-1 px-3 py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md text-on-surface-variant transition-all disabled:opacity-50",
      onclick: async () => {
        suggestBtn.disabled = true;
        const orig = suggestBtn.textContent;
        suggestBtn.textContent = "AI 构思中…";
        try {
          const r = await api.post("/gallery/prompt-suggest", { work_id: work.id, kind });
          promptTa.value = r.prompt || "";
          ui.toast("描述已生成，可直接修改", "ok");
        } catch (e) { ui.toast(e.message, "err"); }
        suggestBtn.disabled = false;
        suggestBtn.textContent = orig;
      },
    }, ui.icon("auto_awesome", "text-[16px]"), "AI 代写描述");

    const genBtnLabel = ui.el("span", {}, "开始作画");
    const genBtn = ui.el("button", {
      class: "flex items-center gap-1.5 px-space-lg py-2 rounded-lg bg-secondary text-on-secondary hover:bg-secondary-container transition-all font-label-md text-label-md shadow-sm disabled:opacity-50",
      onclick: doGenerate,
    }, ui.icon("brush", "text-[18px]"), genBtnLabel);

    const sizeHint = ui.el("span", { class: "font-label-sm text-label-sm text-outline" },
      `尺寸 ${settings.img_size || "1024x1024"}（在系统设置中调整）· 模型 ${settings.img_model || "未设置"}`);
    const taskLinkEl = ui.el("a", {
      class: "hidden flex items-center gap-1 text-secondary hover:underline font-label-sm text-label-sm",
      href: "#/tasks",
      onclick: (e) => { e.preventDefault(); location.hash = "#/tasks"; },
    }, "查看任务记录");

    async function doGenerate() {
      const prompt = promptTa.value.trim();
      if (!prompt) { ui.toast("请先填写画面描述", "err"); promptTa.focus(); return; }
      genBtn.disabled = true;
      genBtnLabel.textContent = "正在作画，请稍候…";
      try {
        const img = await api.post("/gallery/generate", { work_id: work.id, kind, prompt });
        ui.toast(`${KIND_META[kind].label}已生成`, "ok");
        if (img.task_id) {
          taskLinkEl.textContent = `查看任务记录 #${img.task_id}`;
          taskLinkEl.classList.remove("hidden");
        }
        await loadImages();
        // 第一张封面自动设为作品封面
        if (kind === "cover" && !coverId) await setCover(img.id, true);
      } catch (e) {
        if (/尚未配置生图/.test(e.message)) {
          ui.toast("生图接口未配置，请到系统设置完善", "err");
        } else {
          ui.toast(e.message, "err");
        }
      }
      genBtn.disabled = false;
      genBtnLabel.textContent = "开始作画";
    }

    root.append(ui.el("section", { class: "p-space-xl rounded-xl bg-surface-container-lowest shadow-sm flex flex-col gap-space-md" },
      ui.el("div", { class: "flex flex-wrap items-center gap-space-md" },
        ui.el("div", { class: "flex items-center gap-space-sm" },
          ui.icon("palette", "text-[20px] text-secondary"),
          ui.el("h2", { class: "font-headline-md text-headline-md text-primary font-semibold" }, "丹青阁"),
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, "为作品生成封面与插图")),
        ui.el("div", { class: "flex items-center gap-2 ml-auto" },
          ui.el("label", { class: "font-label-md text-label-md text-on-surface-variant font-medium" }, "作品"),
          workSel,
          ui.el("div", { class: "flex items-center gap-1 p-1 rounded-full bg-surface-container-low" },
            kindBtns.cover, kindBtns.illustration))),
      ui.el("div", { class: "flex flex-col gap-1.5" },
        ui.el("div", { class: "flex items-center justify-between" },
          ui.el("label", { class: "font-label-md text-label-md text-on-surface-variant font-medium" }, "画面描述"),
          suggestBtn),
        promptTa),
      ui.el("div", { class: "flex items-center gap-space-md flex-wrap" },
        genBtn, sizeHint, taskLinkEl)));

    /* ---------- 画廊 ---------- */
    const gridBox = ui.el("div", {});
    root.append(gridBox);

    async function loadWork() {
      try {
        const w = await api.get(`/works/${work.id}`);
        coverId = String(w.cover_image || "");
      } catch (e) { coverId = ""; }
    }

    async function loadImages() {
      try {
        images = await api.get(`/works/${work.id}/images`);
      } catch (e) { ui.toast(e.message, "err"); images = []; }
      renderGrid();
    }

    async function setCover(imageId, silent = false) {
      try {
        await api.post(`/works/${work.id}/cover`, { image_id: imageId });
        coverId = String(imageId);
        renderGrid();
        if (!silent) ui.toast("已设为作品封面", "ok");
      } catch (e) { ui.toast(e.message, "err"); }
    }

    function imageCard(img) {
      const isCover = String(img.id) === coverId;
      const meta = KIND_META[img.kind] || KIND_META.illustration;
      return ui.el("div", {
        class: "group bg-surface-container-lowest rounded-xl overflow-hidden shadow-sm hover:shadow-[0_8px_28px_rgba(6,21,35,0.08)] transition-shadow flex flex-col",
      },
        ui.el("div", { class: "relative aspect-square bg-surface-container-low overflow-hidden" },
          ui.el("img", {
            src: `/api/images/${img.id}/file`, alt: img.prompt || "作品图片",
            class: "w-full h-full object-cover", loading: "lazy",
          }),
          isCover && ui.el("span", {
            class: "absolute top-2 left-2 px-2 py-0.5 rounded-full bg-secondary text-on-secondary font-label-sm text-label-sm shadow-sm",
          }, "当前封面")),
        ui.el("div", { class: "p-space-sm flex flex-col gap-1.5 flex-1" },
          ui.el("div", { class: "flex items-center gap-2" },
            ui.el("span", { class: "px-2 py-0.5 rounded-full bg-primary-fixed text-on-primary-fixed font-label-sm text-label-sm" }, meta.label),
            ui.el("span", { class: "font-label-sm text-label-sm text-outline ml-auto" }, (img.created_at || "").slice(5, 16))),
          ui.el("p", {
            class: "font-label-sm text-label-sm text-on-surface-variant line-clamp-2 flex-1",
            title: img.prompt || "",
          }, img.prompt || "（无描述）"),
          ui.el("div", { class: "flex items-center gap-1 pt-1" },
            ui.el("button", {
              class: `flex-1 flex items-center justify-center gap-1 py-1.5 rounded-lg font-label-md text-label-md transition-colors ${
                isCover ? "bg-secondary-fixed text-on-secondary-fixed-variant" : "bg-surface-container hover:bg-secondary-fixed hover:text-on-secondary-fixed-variant"}`,
              onclick: () => { if (!isCover) setCover(img.id); },
              title: isCover ? "已是封面" : "设为封面",
            }, ui.icon(isCover ? "check_circle" : "book_2", "text-[16px]"), isCover ? "已是封面" : "设为封面"),
            ui.el("a", {
              class: "p-1.5 rounded-lg bg-surface-container-low text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-colors",
              href: `/api/images/${img.id}/file`, download: `moyu_image_${img.id}.png`, title: "下载",
            }, ui.icon("download", "text-[16px]")),
            ui.el("button", {
              class: "p-1.5 rounded-lg bg-surface-container-low text-on-surface-variant hover:text-error hover:bg-error-container transition-colors",
              title: "删除",
              onclick: async () => {
                const ok = await ui.confirm("删除图片", "将删除这张图片及其文件，且不可恢复。确定继续？", "删除", true);
                if (!ok) return;
                try {
                  await api.del(`/images/${img.id}`);
                  if (String(img.id) === coverId) coverId = "";
                  ui.toast("已删除", "ok");
                  loadImages();
                } catch (e) { ui.toast(e.message, "err"); }
              },
            }, ui.icon("delete", "text-[16px]")))));
    }

    function renderGrid() {
      gridBox.innerHTML = "";
      if (!images.length) {
        gridBox.append(ui.el("div", {
          class: "flex flex-col items-center gap-space-md py-space-xl rounded-xl bg-surface-container-lowest shadow-sm text-center",
        },
          ui.icon("imagesmode", "text-[48px] text-outline-variant"),
          ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant" },
            `《${work.title}》还没有图片——在上方写下画面描述，生成第一张${KIND_META[kind].label}吧`)));
        return;
      }
      gridBox.append(ui.el("div", { class: "grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-space-md" },
        images.map(imageCard)));
    }

    workSel.addEventListener("change", async () => {
      work = works.find((w) => String(w.id) === workSel.value) || works[0];
      await loadWork();
      await loadImages();
    });

    await loadWork();
    await loadImages();
  }

  return { render };
})();
