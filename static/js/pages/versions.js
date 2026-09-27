/* 版本快照页（对应设计稿 _9）：左时间线 + 双栏差异对比 + 底部恢复操作条 */
registerPage("versions", async (view, { segs, params }) => {
  const workId = segs[0] ? Number(segs[0]) : null;
  const chapterId = params.get("chapter") ? Number(params.get("chapter")) : null;

  const SRC = {
    auto: ["自动保存", "bg-surface-container text-on-surface-variant", "schedule"],
    manual: ["手动快照", "bg-secondary-fixed text-on-secondary-fixed", "bookmark"],
    ai: ["AI 采纳", "bg-tertiary-fixed text-on-tertiary-fixed", "auto_awesome"],
    restore: ["恢复", "bg-primary-fixed text-on-primary-fixed", "history"],
    restore_backup: ["恢复留存", "bg-error-container text-on-error-container", "archive"],
  };

  if (!chapterId) return renderPicker();
  return renderChapter();

  /* ---------- 两级选择：作品 → 章节 ---------- */
  async function renderPicker() {
    ui.setCrumb("版本快照");
    if (!workId) {
      const works = await api.get("/works");
      view.append(
        ui.el("div", { class: "flex flex-col gap-1 mb-space-lg" },
          ui.el("span", { class: "font-label-sm text-label-sm text-secondary tracking-widest uppercase" }, "VERSION TIMELINE"),
          ui.el("h1", { class: "font-display text-display text-primary tracking-tight" }, "版本快照"),
          ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" }, "选择一部作品，查看章节的历史版本与差异。")),
        works.length
          ? ui.el("div", { class: "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-space-md" },
              works.map((w) => ui.el("button", {
                class: "text-left bg-surface-container-lowest rounded-xl p-space-md shadow-[0_4px_20px_rgba(6,21,35,0.03)] hover:shadow-[0_8px_28px_rgba(6,21,35,0.08)] transition-shadow flex flex-col gap-1",
                onclick: () => { location.hash = `#/versions/${w.id}`; },
              },
                ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold truncate" }, w.title),
                ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" },
                  `${w.genre || "未分类"} · ${ui.fmtWords(w.total_words)} 字`))))
          : emptyState("auto_stories", "书架还是空的，先去创建一部作品吧"));
      return;
    }
    const [work, tree] = await Promise.all([api.get(`/works/${workId}`), api.get(`/works/${workId}/tree`)]);
    ui.setCrumb("版本快照", `《${work.title}》`);
    const list = ui.el("div", { class: "flex flex-col gap-space-md" });
    let hasChapter = false;
    for (const v of tree) {
      const rows = v.chapters.map((c) => {
        hasChapter = true;
        return ui.el("button", {
          class: "w-full flex items-center justify-between px-space-md py-space-sm rounded-xl bg-surface-container-lowest hover:bg-surface-container-low transition-colors text-left",
          onclick: () => { location.hash = `#/versions/${workId}?chapter=${c.id}`; },
        },
          ui.el("span", { class: "font-body-md text-body-md text-on-surface" }, c.title),
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" },
            `${ui.fmtWords(c.word_count)} 字 · ${(c.updated_at || "").slice(0, 16)}`));
      });
      list.append(ui.el("div", { class: "flex flex-col gap-1" },
        ui.el("span", { class: "font-label-md text-label-md text-on-surface-variant px-space-xs" }, v.title),
        rows.length ? rows : ui.el("p", { class: "px-space-xs font-body-sm text-body-sm text-outline" }, "本卷暂无章节")));
    }
    view.append(
      ui.el("button", {
        class: "flex items-center gap-1 font-label-md text-label-md text-secondary mb-space-md",
        onclick: () => { location.hash = "#/versions"; },
      }, ui.icon("arrow_back", "text-[16px]"), "返回作品列表"),
      ui.el("h1", { class: "font-headline-lg text-headline-lg text-primary tracking-tight mb-space-md" }, `《${work.title}》选择章节`),
      hasChapter ? list : emptyState("edit_note", "这部作品还没有章节"));
  }

  /* ---------- 版本时间线 + 双栏 diff ---------- */
  async function renderChapter() {
    try { await api.post(`/chapters/${chapterId}/versions/prune`); } catch (e) { /* 清理失败不阻塞 */ }
    const [chapter, versions] = await Promise.all([
      api.get(`/chapters/${chapterId}`),
      api.get(`/chapters/${chapterId}/versions`),
    ]);
    let work = null;
    if (workId) { try { work = await api.get(`/works/${workId}`); } catch (e) {} }
    ui.setCrumb(...["版本快照", work && `《${work.title}》`, chapter.title].filter(Boolean));
    ui.setActions(
      ui.el("button", {
        class: "flex items-center gap-1 px-space-sm py-1.5 rounded-full bg-primary text-on-primary shadow-[0_2px_12px_rgba(6,21,35,0.2)] hover:bg-primary-container transition-all",
        onclick: async () => {
          try {
            await api.post(`/chapters/${chapterId}/snapshot`);
            ui.toast("手动快照已创建", "ok");
            router.dispatch();
          } catch (e) { ui.toast(e.message, "err"); }
        },
      }, ui.icon("bookmark_add", "text-[18px]"), ui.el("span", { class: "font-label-md text-label-md" }, "手动创建快照")));

    const state = {
      left: versions.length ? versions[0].id : "current",
      right: "current",
      cache: { current: { label: "当前正文", meta: `${ui.fmtWords(chapter.word_count)} 字 · 实时`, content: chapter.content } },
    };

    const timeline = ui.el("div", { class: "flex flex-col gap-space-xs relative" });
    const diffStage = ui.el("div", { class: "flex flex-col gap-space-sm" });
    const restoreBar = ui.el("div");

    view.append(
      ui.el("div", { class: "flex flex-col gap-1 pb-space-lg" },
        ui.el("div", { class: "flex items-center gap-space-xs font-label-sm text-label-sm text-on-surface-variant" },
          ui.el("span", { class: "font-semibold text-cinnabar-accent" }, "版本时光机"),
          ui.el("span", null, "•"),
          ui.el("span", null, "恢复前自动留存 · 操作可撤销")),
        ui.el("div", { class: "flex items-center gap-space-sm" },
          ui.el("h1", { class: "font-headline-lg text-headline-lg text-primary tracking-tight truncate" }, chapter.title),
          ui.el("span", { class: "px-space-sm py-0.5 rounded-full bg-surface-container text-on-surface-variant font-label-md text-label-md shrink-0" },
            `共 ${versions.length} 份快照`))),
      ui.el("div", { class: "w-full grid grid-cols-12 gap-space-lg items-start" },
        ui.el("div", { class: "col-span-12 lg:col-span-4 flex flex-col gap-space-sm" },
          ui.el("div", { class: "p-space-md rounded-2xl bg-surface-container-lowest shadow-sm flex items-center gap-space-xs" },
            ui.icon("history", "text-[20px] text-secondary"),
            ui.el("span", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, "版本演进历程")),
          timeline),
        ui.el("div", { class: "col-span-12 lg:col-span-8 flex flex-col gap-space-sm" }, diffStage)),
      restoreBar);

    renderTimeline();
    await renderDiff();

    function sideOptions(selValue) {
      const opts = [ui.el("option", { value: "current" }, "当前正文（实时）")];
      for (const v of versions) {
        const o = ui.el("option", { value: String(v.id) }, `#${v.id} ${v.label || SRC[v.source]?.[0] || v.source} · ${(v.created_at || "").slice(5, 16)}`);
        opts.push(o);
      }
      const sel = ui.el("select", {
        class: "bg-surface-container rounded-lg px-2 py-1 font-label-md text-label-md outline-none max-w-[220px]",
      }, opts);
      sel.value = String(selValue);
      return sel;
    }

    async function sideData(key) {
      if (!state.cache[key]) {
        const v = await api.get(`/versions/${key}`);
        const src = SRC[v.source] || [v.source, "", "history"];
        state.cache[key] = {
          label: `版本 #${v.id}${v.label ? " · " + v.label : ""}`,
          meta: `${src[0]} · ${(v.created_at || "").slice(0, 16)} · ${ui.fmtWords(v.word_count)} 字`,
          content: v.content,
        };
      }
      return state.cache[key];
    }

    async function renderDiff() {
      diffStage.innerHTML = "";
      const leftSel = sideOptions(state.left);
      const rightSel = sideOptions(state.right);
      leftSel.addEventListener("change", async () => { state.left = toKey(leftSel.value); renderTimeline(); await renderDiff(); });
      rightSel.addEventListener("change", async () => { state.right = toKey(rightSel.value); await renderDiff(); });

      const L = await sideData(state.left);
      const R = await sideData(state.right);
      const { leftRows, rightRows, added, removed } = diffLines(L.content, R.content);

      const pane = (badge, badgeCls, data, rows, ring) => ui.el("div", {
        class: `p-space-lg rounded-2xl bg-surface-container-lowest shadow-sm flex flex-col gap-space-md min-w-0 ${ring || ""}`,
      },
        ui.el("div", { class: "flex items-center justify-between pb-space-sm border-b border-surface-container gap-2" },
          ui.el("div", { class: "flex items-center gap-space-xs min-w-0" },
            ui.el("span", { class: `px-space-xs py-0.5 rounded font-label-sm text-label-sm shrink-0 ${badgeCls}` }, badge),
            ui.el("span", { class: "font-label-md text-label-md font-semibold text-primary truncate" }, data.label)),
          ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant shrink-0" }, data.meta)),
        rows.length
          ? ui.el("div", { class: "flex flex-col gap-3 font-body-md text-body-md leading-loose" }, rows)
          : ui.el("p", { class: "font-body-sm text-body-sm text-outline" }, "（空内容）"));

      diffStage.append(
        ui.el("div", { class: "p-space-md rounded-2xl bg-surface-container-lowest shadow-sm flex flex-wrap items-center justify-between gap-space-sm" },
          ui.el("div", { class: "flex items-center gap-space-xs font-label-md text-label-md text-on-surface" },
            ui.icon("compare_arrows", "text-[18px] text-secondary"),
            ui.el("span", { class: "font-semibold" }, "双栏差异对比")),
          ui.el("div", { class: "flex items-center gap-space-xs font-label-sm text-label-sm text-on-surface-variant" },
            leftSel, ui.icon("arrow_forward", "text-[14px]"), rightSel),
          ui.el("div", { class: "flex items-center gap-space-md font-body-sm text-body-sm" },
            ui.el("span", { class: "flex items-center gap-1" },
              ui.el("span", { class: "w-2.5 h-2.5 rounded-full", style: "background:#16a34a" }),
              ui.el("span", { class: "text-on-surface-variant" }, "新增"),
              ui.el("span", { class: "font-semibold text-on-surface" }, `+${ui.fmtWords(added)} 字`)),
            ui.el("span", { class: "flex items-center gap-1" },
              ui.el("span", { class: "w-2.5 h-2.5 rounded-full", style: "background:#D9483B" }),
              ui.el("span", { class: "text-on-surface-variant" }, "删除"),
              ui.el("span", { class: "font-semibold text-on-surface" }, `-${ui.fmtWords(removed)} 字`)))),
        ui.el("div", { class: "w-full grid grid-cols-1 md:grid-cols-2 gap-space-md" },
          pane("回溯目标", "bg-surface-container-high text-on-surface-variant", L, leftRows),
          pane(state.right === "current" ? "当前正文" : "对比版本", "bg-secondary-fixed text-on-secondary-fixed", R, rightRows, "ring-1 ring-secondary/20")));

      renderRestoreBar();
    }

    function renderRestoreBar() {
      restoreBar.innerHTML = "";
      if (state.left === "current") return;
      const data = state.cache[state.left];
      restoreBar.append(ui.el("div", {
        class: "sticky bottom-6 w-full mt-space-lg p-space-md rounded-2xl bg-primary text-on-primary shadow-[0_12px_32px_rgba(6,21,35,0.18)] flex flex-wrap items-center justify-between gap-space-sm z-30",
      },
        ui.el("div", { class: "flex items-center gap-space-xs font-body-sm text-body-sm text-inverse-primary min-w-0" },
          ui.icon("swap_horizontal_circle", "text-[20px] text-cinnabar-accent"),
          ui.el("span", null, "将把当前章节正文回退至："),
          ui.el("span", { class: "text-on-primary font-semibold underline decoration-cinnabar-accent underline-offset-4 truncate" },
            `${data.label}（${data.meta}）`),
          ui.el("span", { class: "font-label-sm text-label-sm text-inverse-primary/80 shrink-0" }, "｜操作可撤销")),
        ui.el("button", {
          class: "flex items-center gap-space-xs px-space-lg py-space-xs rounded-xl bg-secondary-container hover:bg-secondary text-on-secondary font-label-md text-label-md font-semibold shadow-md transition-all",
          onclick: async () => {
            const ok = await ui.confirm("恢复版本",
              `将把「${chapter.title}」回退至 ${data.label}。\n当前正文会自动留存为一份“恢复前自动留存”快照，可随时再次恢复。`, "恢复");
            if (!ok) return;
            try {
              await api.post(`/versions/${state.left}/restore`);
              ui.toast("已恢复至历史版本，原正文已留存为快照", "ok");
              router.dispatch();
            } catch (e) { ui.toast(e.message, "err"); }
          },
        }, ui.icon("history", "text-[18px]"), "恢复至该历史版本")));
    }

    function renderTimeline() {
      timeline.innerHTML = "";
      timeline.append(ui.el("div", { class: "absolute left-6 top-6 bottom-6 w-0.5 bg-surface-container-high z-0" }));
      const cur = state.left === "current";
      timeline.append(ui.el("div", {
        class: `relative z-10 p-space-md rounded-2xl cursor-pointer transition-all shadow-sm ${cur ? "bg-primary-container text-on-primary-container" : "bg-surface-container-lowest hover:bg-surface-container-low"}`,
        onclick: async () => { state.left = "current"; renderTimeline(); await renderDiff(); },
      },
        ui.el("div", { class: "flex items-start gap-space-sm" },
          ui.el("div", { class: "w-5 h-5 rounded-full bg-secondary-container text-on-secondary-container flex items-center justify-center shrink-0 mt-0.5" },
            ui.el("span", { class: "w-2 h-2 rounded-full bg-surface-container-lowest" })),
          ui.el("div", { class: "flex-1 min-w-0" },
            ui.el("div", { class: "flex items-center justify-between gap-2" },
              ui.el("span", { class: `font-label-md text-label-md font-semibold ${cur ? "text-on-primary" : "text-primary"}` }, "当前活动草稿（实时）"),
              ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, (chapter.updated_at || "").slice(5, 16))),
            ui.el("div", { class: "flex items-center gap-space-xs mt-1" },
              ui.el("span", { class: `px-space-xs py-0.5 rounded font-label-sm text-label-sm ${cur ? "bg-primary text-on-primary" : "bg-surface-container text-on-surface-variant"}` }, "正在编辑"),
              ui.el("span", { class: "font-label-sm text-label-sm" }, `${ui.fmtWords(chapter.word_count)} 字`))))));

      for (const v of versions) {
        const sel = state.left === v.id;
        const src = SRC[v.source] || [v.source, "bg-surface-container text-on-surface-variant", "history"];
        timeline.append(ui.el("div", {
          class: `relative z-10 p-space-md rounded-2xl cursor-pointer transition-all shadow-sm group ${sel ? "bg-primary-container text-on-primary-container" : "bg-surface-container-lowest hover:bg-surface-container-low"}`,
          onclick: async () => { state.left = v.id; renderTimeline(); await renderDiff(); },
        },
          ui.el("div", { class: "flex items-start gap-space-sm" },
            ui.el("div", { class: `w-5 h-5 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${sel ? "bg-cinnabar-accent text-on-error" : "bg-surface-container-high text-on-surface-variant"}` },
              ui.icon(src[2], "text-[13px]")),
            ui.el("div", { class: "flex-1 min-w-0" },
              ui.el("div", { class: "flex items-center justify-between gap-2" },
                ui.el("span", { class: `font-label-md text-label-md font-medium truncate ${sel ? "text-on-primary" : "text-primary"}` },
                  `版本 #${v.id}${v.label ? " · " + v.label : ""}`),
                ui.el("span", { class: `font-label-sm text-label-sm shrink-0 ${sel ? "text-inverse-primary" : "text-on-surface-variant"}` },
                  (v.created_at || "").slice(5, 16))),
              ui.el("div", { class: "flex items-center gap-space-xs mt-1 flex-wrap" },
                ui.el("span", { class: `px-space-xs py-0.5 rounded font-label-sm text-label-sm ${sel ? "bg-primary text-on-primary" : src[1]}` }, src[0]),
                ui.el("span", { class: `font-label-sm text-label-sm ${sel ? "text-inverse-primary" : "text-on-surface-variant"}` },
                  `${ui.fmtWords(v.word_count)} 字`)),
              v.preview && ui.el("p", { class: `font-body-sm text-body-sm mt-2 line-clamp-1 ${sel ? "text-inverse-primary" : "text-on-surface-variant"}` }, v.preview)),
            ui.el("button", {
              class: `p-1 rounded-lg shrink-0 opacity-0 group-hover:opacity-100 transition-opacity ${sel ? "text-inverse-primary hover:text-on-primary" : "text-on-surface-variant hover:text-error"}`,
              title: "删除该快照",
              onclick: async (e) => {
                e.stopPropagation();
                const ok = await ui.confirm("删除快照", `将删除版本 #${v.id}，且不可恢复。确定继续？`, "删除", true);
                if (!ok) return;
                try {
                  await api.del(`/versions/${v.id}`);
                  ui.toast("快照已删除", "ok");
                  if (state.left === v.id) state.left = "current";
                  router.dispatch();
                } catch (err) { ui.toast(err.message, "err"); }
              },
            }, ui.icon("delete", "text-[16px]")))));
      }
      if (!versions.length) {
        timeline.append(ui.el("div", { class: "relative z-10 p-space-md rounded-2xl bg-surface-container-low/60 text-center font-body-sm text-body-sm text-on-surface-variant" },
          "还没有历史快照，点右上角「手动创建快照」留存第一份。"));
      }
    }

    function toKey(v) { return v === "current" ? "current" : Number(v); }
  }

  /* ---------- 行级 diff（LCS） ---------- */
  function diffLines(a, b) {
    const A = (a || "").split("\n"), B = (b || "").split("\n");
    let ops;
    if (A.length * B.length > 2000000) {
      ops = [...A.map((t) => ({ type: "del", text: t })), ...B.map((t) => ({ type: "add", text: t }))];
    } else {
      const m = A.length, n = B.length;
      const dp = new Uint32Array((m + 1) * (n + 1));
      for (let i = m - 1; i >= 0; i--) {
        for (let j = n - 1; j >= 0; j--) {
          dp[i * (n + 1) + j] = A[i] === B[j]
            ? dp[(i + 1) * (n + 1) + j + 1] + 1
            : Math.max(dp[(i + 1) * (n + 1) + j], dp[i * (n + 1) + j + 1]);
        }
      }
      ops = [];
      let i = 0, j = 0;
      while (i < m && j < n) {
        if (A[i] === B[j]) { ops.push({ type: "eq", text: A[i] }); i++; j++; }
        else if (dp[(i + 1) * (n + 1) + j] >= dp[i * (n + 1) + j + 1]) { ops.push({ type: "del", text: A[i] }); i++; }
        else { ops.push({ type: "add", text: B[j] }); j++; }
      }
      while (i < m) ops.push({ type: "del", text: A[i++] });
      while (j < n) ops.push({ type: "add", text: B[j++] });
    }
    const leftRows = [], rightRows = [];
    let added = 0, removed = 0;
    for (const op of ops) {
      if (op.type === "eq") {
        leftRows.push(row(op.text)); rightRows.push(row(op.text));
      } else if (op.type === "del") {
        removed += op.text.replace(/\s/g, "").length;
        leftRows.push(row(op.text, "diff-del"));
      } else {
        added += op.text.replace(/\s/g, "").length;
        rightRows.push(row(op.text, "diff-add"));
      }
    }
    return { leftRows, rightRows, added, removed };

    function row(text, cls) {
      return ui.el("p", { class: cls ? `${cls} px-space-xs rounded text-on-surface` : "text-on-surface-variant" }, text || " ");
    }
  }

  function emptyState(icon, text) {
    return ui.el("div", { class: "flex flex-col items-center gap-space-md py-space-xl text-center" },
      ui.icon(icon, "text-[48px] text-outline-variant"),
      ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" }, text));
  }
});
