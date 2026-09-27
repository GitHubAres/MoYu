/* 人物关系图谱页：SVG 力导向布局（环形初始化 + 斥力/引力迭代），支持缩放/平移/拖拽节点 */
registerPage("graph", async (view, { segs }) => {
  const workId = segs[0] ? Number(segs[0]) : null;

  const CATS = {
    character: { label: "角色", color: "#0051d5", icon: "person" },
    place: { label: "地点", color: "#2e7d32", icon: "location_on" },
    faction: { label: "势力", color: "#7c3aed", icon: "temple_buddhist" },
    item: { label: "物品", color: "#e67e22", icon: "colorize" },
    term: { label: "术语", color: "#74777c", icon: "menu_book" },
    custom: { label: "自定义", color: "#1b2a38", icon: "category" },
  };
  const catOf = (c) => CATS[c] || CATS.custom;
  const REL_SUGGESTIONS = ["师徒", "敌对", "挚友", "道侣", "血亲", "所属", "持有", "守护", "仇杀", "故交"];

  if (!workId) return pickWork();
  return renderGraph();

  /* ---------- 无 workId：作品选择列表 ---------- */
  async function pickWork() {
    ui.setCrumb("关系图谱");
    const works = await api.get("/works");
    view.append(
      ui.el("div", { class: "flex flex-col gap-1 mb-space-lg" },
        ui.el("span", { class: "font-label-sm text-label-sm text-secondary tracking-widest uppercase" }, "RELATION GRAPH"),
        ui.el("h1", { class: "font-display text-display text-primary tracking-tight" }, "人物关系图谱"),
        ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" }, "选择一部作品，一览角色、势力与物品的勾连脉络。")),
      works.length
        ? ui.el("div", { class: "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-space-md" },
            works.map((w) => ui.el("button", {
              class: "text-left bg-surface-container-lowest rounded-xl p-space-md shadow-[0_4px_20px_rgba(6,21,35,0.03)] hover:shadow-[0_8px_28px_rgba(6,21,35,0.08)] transition-shadow flex flex-col gap-1",
              onclick: () => { location.hash = `#/graph/${w.id}`; },
            },
              ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold truncate" }, w.title),
              ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" },
                `${w.genre || "未分类"} · ${ui.fmtWords(w.total_words)} 字`))))
        : ui.el("div", { class: "flex flex-col items-center gap-space-md py-space-xl text-center" },
            ui.icon("auto_stories", "text-[48px] text-outline-variant"),
            ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" }, "书架还是空的，先去创建一部作品吧")));
  }

  /* ---------- 图谱页 ---------- */
  async function renderGraph() {
    const [work, graph, works] = await Promise.all([
      api.get(`/works/${workId}`),
      api.get(`/works/${workId}/graph`),
      api.get("/works"),
    ]);
    const { nodes, edges } = graph;

    ui.setCrumb("关系图谱", `《${work.title}》`);
    ui.setActions(
      ui.el("button", {
        class: "flex items-center gap-1 px-space-sm py-1.5 rounded-full bg-primary text-on-primary shadow-[0_2px_12px_rgba(6,21,35,0.2)] hover:bg-primary-container transition-all",
        onclick: () => relationDialog(),
      }, ui.icon("add", "text-[18px]"), ui.el("span", { class: "font-label-md text-label-md" }, "新增关系")));

    /* 顶部信息条：作品切换 + 统计 */
    const sel = ui.el("select", {
      class: "px-3 py-1.5 rounded-lg bg-surface-container-low border border-border-feather outline-none font-body-sm text-body-sm",
      onchange: (e) => { location.hash = `#/graph/${e.target.value}`; },
    }, works.map((w) => ui.el("option", { value: String(w.id) }, w.title)));
    sel.value = String(workId);

    view.append(
      ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-md shadow-[0_2px_12px_rgba(6,21,35,0.03)] flex flex-wrap items-center gap-space-md mb-space-lg" },
        ui.el("div", { class: "flex items-center gap-space-xs" },
          ui.el("span", { class: "inline-flex items-center justify-center w-8 h-8 rounded-lg bg-surface-container text-primary" },
            ui.icon("hub", "text-[20px]")),
          ui.el("div", { class: "flex flex-col" },
            ui.el("span", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, `《${work.title}》`),
            ui.el("span", { class: "font-label-sm text-label-sm text-outline" }, "全景脉络 · 人物关系图谱"))),
        ui.el("div", { class: "h-8 w-[1px] bg-surface-container-highest hidden sm:block" }),
        ui.el("label", { class: "flex items-center gap-space-xs font-label-sm text-label-sm text-on-surface-variant" }, "切换作品", sel),
        ui.el("div", { class: "flex items-center gap-2 font-body-sm text-body-sm ml-auto" },
          ui.el("span", { class: "px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed font-label-sm text-label-sm" }, `${nodes.length} 节点`),
          ui.el("span", { class: "px-2 py-0.5 rounded-full bg-primary-fixed text-on-primary-fixed font-label-sm text-label-sm" }, `${edges.length} 关系`),
          /* 图例 */
          Object.keys(CATS).filter((k) => nodes.some((n) => (CATS[n.category] ? n.category : "custom") === k))
            .map((k) => ui.el("span", { class: "hidden md:inline-flex items-center gap-1 font-label-sm text-label-sm text-on-surface-variant" },
              ui.el("span", { class: "w-2.5 h-2.5 rounded-full", style: `background:${CATS[k].color}` }), CATS[k].label)))));

    /* 空状态：无实体 */
    if (!nodes.length) {
      view.append(ui.el("div", { class: "flex flex-col items-center gap-space-md py-space-xl text-center" },
        ui.icon("hub", "text-[48px] text-outline-variant"),
        ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" }, "这部作品还没有设定条目。图谱以设定库中的角色 / 地点 / 势力等为节点。"),
        ui.el("button", {
          class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md",
          onclick: () => { location.hash = `#/entities/${workId}`; },
        }, "前往设定库添加条目")));
      return;
    }

    /* 画布容器（相对定位，承载侧卡与提示浮层） */
    const wrap = ui.el("div", {
      class: "relative bg-surface-container-lowest rounded-xl shadow-[0_2px_12px_rgba(6,21,35,0.03)] overflow-hidden",
    });

    const W = 1100, H = 620;
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "w-full block touch-none select-none cursor-grab");
    svg.setAttribute("height", "620");
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const world = document.createElementNS("http://www.w3.org/2000/svg", "g");
    svg.append(world);
    wrap.append(svg);
    view.append(wrap);

    /* ---------- 力导向布局：环形初始化 + 迭代 ---------- */
    const pos = new Map(); // id -> {x, y}
    const cx = W / 2, cy = H / 2;
    const R = Math.min(W, H) / 2 - 90;
    nodes.forEach((n, i) => {
      const a = (2 * Math.PI * i) / nodes.length - Math.PI / 2;
      pos.set(n.id, { x: cx + R * Math.cos(a), y: cy + R * Math.sin(a) });
    });
    const IDEAL = 170;
    for (let iter = 0; iter < 240; iter++) {
      const disp = new Map(nodes.map((n) => [n.id, { x: 0, y: 0 }]));
      /* 斥力（全对） */
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = pos.get(nodes[i].id), b = pos.get(nodes[j].id);
          let dx = a.x - b.x, dy = a.y - b.y;
          let d2 = dx * dx + dy * dy;
          if (d2 < 1) { dx = Math.random() - 0.5; dy = Math.random() - 0.5; d2 = 1; }
          const f = Math.min(16000 / d2, 40);
          const d = Math.sqrt(d2);
          disp.get(nodes[i].id).x += (dx / d) * f;
          disp.get(nodes[i].id).y += (dy / d) * f;
          disp.get(nodes[j].id).x -= (dx / d) * f;
          disp.get(nodes[j].id).y -= (dy / d) * f;
        }
      }
      /* 引力（沿边） */
      for (const e of edges) {
        const a = pos.get(e.from_id), b = pos.get(e.to_id);
        if (!a || !b) continue;
        const dx = b.x - a.x, dy = b.y - a.y;
        const d = Math.max(Math.hypot(dx, dy), 1);
        const f = (d - IDEAL) * 0.04;
        disp.get(e.from_id).x += (dx / d) * f * d / 20;
        disp.get(e.from_id).y += (dy / d) * f * d / 20;
        disp.get(e.to_id).x -= (dx / d) * f * d / 20;
        disp.get(e.to_id).y -= (dy / d) * f * d / 20;
      }
      /* 向心 + 应用位移（降温） */
      const cool = 1 - iter / 240;
      for (const n of nodes) {
        const p = pos.get(n.id), d = disp.get(n.id);
        p.x += Math.max(-12, Math.min(12, d.x)) * cool + (cx - p.x) * 0.015;
        p.y += Math.max(-12, Math.min(12, d.y)) * cool + (cy - p.y) * 0.015;
      }
    }

    /* ---------- 渲染 ---------- */
    const svgEl = (tag, attrs, ...children) => {
      const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
      for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
      for (const c of children.flat(Infinity)) if (c != null) el.append(c);
      return el;
    };
    const svgText = (attrs, text) => {
      const t = svgEl("text", attrs);
      t.textContent = text;
      return t;
    };

    const nodeById = new Map(nodes.map((n) => [n.id, n]));
    let selEdge = null, selNode = null; // 当前选中

    const edgeEls = edges.map((e) => {
      const a = pos.get(e.from_id), b = pos.get(e.to_id);
      if (!a || !b) return null;
      const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      const line = svgEl("line", {
        x1: a.x, y1: a.y, x2: b.x, y2: b.y,
        stroke: "#c4c6cc", "stroke-width": 1.6, class: "graph-edge",
      });
      const hit = svgEl("line", {
        x1: a.x, y1: a.y, x2: b.x, y2: b.y,
        stroke: "transparent", "stroke-width": 14, style: "cursor:pointer",
      });
      const lab = e.label
        ? svgText({ x: mx, y: my - 5, "text-anchor": "middle", "font-size": 11, fill: "#74777c", style: "pointer-events:none" }, e.label)
        : null;
      const g = svgEl("g", {}, line, hit, lab);
      hit.addEventListener("click", (ev) => { ev.stopPropagation(); selectEdge(e, g); });
      world.append(g);
      return { e, g, line, lab };
    }).filter(Boolean);

    const nodeEls = nodes.map((n) => {
      const p = pos.get(n.id);
      const cat = catOf(n.category);
      const g = svgEl("g", { transform: `translate(${p.x},${p.y})`, style: "cursor:grab" },
        svgEl("circle", { r: 24, fill: cat.color, opacity: 0.12 }),
        svgEl("circle", { r: 17, fill: cat.color, stroke: "#ffffff", "stroke-width": 2.5 }),
        svgText({ "text-anchor": "middle", dy: "0.36em", "font-size": 13, fill: "#ffffff", "font-weight": 600, style: "pointer-events:none" }, (n.name || "?")[0]),
        svgText({ "text-anchor": "middle", y: 34, "font-size": 12, fill: "#1b1c1d", "font-weight": 500, style: "pointer-events:none" },
          n.name.length > 7 ? n.name.slice(0, 7) + "…" : n.name));
      g.setAttribute("data-nid", n.id);
      world.append(g);
      return { n, g };
    });
    const nodeElById = new Map(nodeEls.map((x) => [x.n.id, x]));

    function refreshEdges() {
      for (const { e, line, lab, g } of edgeEls) {
        const a = pos.get(e.from_id), b = pos.get(e.to_id);
        for (const l of g.querySelectorAll("line")) {
          l.setAttribute("x1", a.x); l.setAttribute("y1", a.y);
          l.setAttribute("x2", b.x); l.setAttribute("y2", b.y);
        }
        if (lab) { lab.setAttribute("x", (a.x + b.x) / 2); lab.setAttribute("y", (a.y + b.y) / 2 - 5); }
      }
    }

    /* ---------- 缩放 / 平移 / 节点拖拽 ---------- */
    let k = 1, tx = 0, ty = 0;
    const applyView = () => world.setAttribute("transform", `translate(${tx},${ty}) scale(${k})`);
    const toWorld = (ev) => {
      const r = svg.getBoundingClientRect();
      return { x: (ev.clientX - r.left - tx) / k, y: (ev.clientY - r.top - ty) / k };
    };

    svg.addEventListener("wheel", (ev) => {
      ev.preventDefault();
      const r = svg.getBoundingClientRect();
      const mx = ev.clientX - r.left, my = ev.clientY - r.top;
      const nk = Math.max(0.3, Math.min(3, k * (ev.deltaY < 0 ? 1.12 : 1 / 1.12)));
      tx = mx - ((mx - tx) / k) * nk;
      ty = my - ((my - ty) / k) * nk;
      k = nk;
      applyView();
    }, { passive: false });

    let drag = null; // {type:'pan'} | {type:'node', n}
    svg.addEventListener("pointerdown", (ev) => {
      const g = ev.target.closest("g[data-nid]");
      if (g) {
        svg.setPointerCapture(ev.pointerId);
        const n = nodeElById.get(Number(g.getAttribute("data-nid")));
        drag = { type: "node", rec: n, moved: false, start: toWorld(ev), orig: { ...pos.get(n.n.id) } };
        g.style.cursor = "grabbing";
      } else {
        drag = { type: "pan", sx: ev.clientX, sy: ev.clientY, stx: tx, sty: ty, moved: false };
        svg.style.cursor = "grabbing";
      }
    });
    svg.addEventListener("pointermove", (ev) => {
      if (!drag) return;
      if (drag.type === "pan") {
        if (Math.abs(ev.clientX - drag.sx) + Math.abs(ev.clientY - drag.sy) > 3) drag.moved = true;
        tx = drag.stx + (ev.clientX - drag.sx);
        ty = drag.sty + (ev.clientY - drag.sy);
        applyView();
      } else {
        drag.moved = true;
        const w = toWorld(ev);
        pos.get(drag.rec.n.id).x = drag.orig.x + (w.x - drag.start.x);
        pos.get(drag.rec.n.id).y = drag.orig.y + (w.y - drag.start.y);
        drag.rec.g.setAttribute("transform", `translate(${pos.get(drag.rec.n.id).x},${pos.get(drag.rec.n.id).y})`);
        refreshEdges();
      }
    });
    svg.addEventListener("pointerup", (ev) => {
      if (!drag) return;
      const d = drag; drag = null;
      svg.style.cursor = "grab";
      if (d.type === "node") {
        d.rec.g.style.cursor = "grab";
        if (!d.moved) selectNode(d.rec.n);
      } else if (!d.moved) {
        clearSelection();
      }
    });

    /* ---------- 选中：边 / 节点 ---------- */
    function clearSelection() {
      selEdge = selNode = null;
      edgeEls.forEach(({ line }) => { line.setAttribute("stroke", "#c4c6cc"); line.setAttribute("stroke-width", 1.6); });
      nodeEls.forEach(({ g }) => g.querySelectorAll("circle")[1].setAttribute("stroke", "#ffffff"));
      edgeBar.remove(); nodeCard.remove();
    }

    /* 边选中浮条 */
    let edgeBar = ui.el("div");
    function selectEdge(e, g) {
      clearSelection();
      selEdge = e;
      g.querySelector("line").setAttribute("stroke", "#D9483B");
      g.querySelector("line").setAttribute("stroke-width", 3);
      const a = nodeById.get(e.from_id), b = nodeById.get(e.to_id);
      edgeBar = ui.el("div", {
        class: "absolute left-1/2 -translate-x-1/2 top-4 z-10 flex items-center gap-space-sm bg-surface-container-lowest rounded-full px-4 py-2 shadow-[0_8px_24px_rgba(27,42,56,0.12)] border border-border-feather",
      },
        ui.icon("link", "text-[18px] text-cinnabar-accent"),
        ui.el("span", { class: "font-body-sm text-body-sm text-on-surface" },
          `${a ? a.name : "?"} —[${e.label || "关系"}]→ ${b ? b.name : "?"}`),
        ui.el("button", {
          class: "p-1.5 rounded-lg hover:bg-error-container hover:text-error text-on-surface-variant transition-colors", title: "编辑标签",
          onclick: async () => {
            const label = await ui.prompt("修改关系标签", "如：师徒 / 敌对 / 持有", e.label || "");
            if (label === null) return;
            try {
              await api.patch(`/relations/${e.id}`, { label });
              ui.toast("关系已更新", "ok");
              router.dispatch();
            } catch (err) { ui.toast(err.message, "err"); }
          },
        }, ui.icon("edit", "text-[18px]")),
        ui.el("button", {
          class: "p-1.5 rounded-lg hover:bg-error-container hover:text-error text-on-surface-variant transition-colors", title: "删除关系",
          onclick: async () => {
            const ok = await ui.confirm("删除关系", `将删除「${a ? a.name : "?"} → ${b ? b.name : "?"}」的${e.label ? `「${e.label}」` : ""}关系，且不可恢复。`, "删除", true);
            if (!ok) return;
            try {
              await api.del(`/relations/${e.id}`);
              ui.toast("已删除", "ok");
              router.dispatch();
            } catch (err) { ui.toast(err.message, "err"); }
          },
        }, ui.icon("delete", "text-[18px]")),
        ui.el("button", {
          class: "p-1.5 rounded-lg hover:bg-surface-container-high text-on-surface-variant transition-colors", title: "取消选中",
          onclick: () => clearSelection(),
        }, ui.icon("close", "text-[18px]")));
      wrap.append(edgeBar);
    }

    /* 节点详情侧卡 */
    let nodeCard = ui.el("div");
    function selectNode(n) {
      clearSelection();
      selNode = n;
      nodeElById.get(n.id).g.querySelectorAll("circle")[1].setAttribute("stroke", "#D9483B");
      const cat = catOf(n.category);
      const rels = edges.filter((e) => e.from_id === n.id || e.to_id === n.id);
      const tags = Array.isArray(n.tags) ? n.tags : String(n.tags || "").split(",").filter(Boolean);
      nodeCard = ui.el("aside", {
        class: "absolute top-4 right-4 z-10 w-[300px] max-w-[85%] bg-surface-container-lowest rounded-xl p-space-md shadow-[0_12px_32px_rgba(27,42,56,0.14)] border border-border-feather flex flex-col gap-space-sm",
      },
        ui.el("div", { class: "flex items-start justify-between gap-2" },
          ui.el("div", { class: "flex items-center gap-space-xs min-w-0" },
            ui.el("span", { class: "inline-flex items-center justify-center w-9 h-9 rounded-full text-white shrink-0", style: `background:${cat.color}` },
              ui.icon(cat.icon, "text-[18px]")),
            ui.el("div", { class: "min-w-0" },
              ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold truncate" }, n.name),
              ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, cat.label))),
          ui.el("button", {
            class: "p-1 rounded-lg hover:bg-surface-container-high text-on-surface-variant shrink-0",
            onclick: () => clearSelection(),
          }, ui.icon("close", "text-[18px]"))),
        tags.length
          ? ui.el("div", { class: "flex flex-wrap gap-1" },
              tags.map((t) => ui.el("span", { class: "px-2 py-0.5 rounded-full bg-surface-container font-label-sm text-label-sm text-on-surface-variant" }, t)))
          : null,
        /* 详情侧卡的内容摘要由设定条目接口补齐 */
        ui.el("p", { class: "font-body-sm text-body-sm text-on-surface-variant line-clamp-4", id: "graph-node-content" }, "加载中…"),
        rels.length
          ? ui.el("div", { class: "flex flex-col gap-1 border-t border-surface-container pt-space-xs" },
              ui.el("span", { class: "font-label-sm text-label-sm text-outline" }, `相关关系（${rels.length}）`),
              rels.map((e) => {
                const other = e.from_id === n.id ? nodeById.get(e.to_id) : nodeById.get(e.from_id);
                const dir = e.from_id === n.id ? "→" : "←";
                return ui.el("div", { class: "flex items-center gap-1 font-body-sm text-body-sm text-on-surface-variant" },
                  ui.el("span", { class: "flex-1 truncate" }, `${dir} ${other ? other.name : "?"}${e.label ? ` · ${e.label}` : ""}`),
                  ui.el("button", {
                    class: "p-1 rounded hover:bg-error-container hover:text-error transition-colors shrink-0", title: "删除关系",
                    onclick: async () => {
                      const ok = await ui.confirm("删除关系", `将删除该条关系（${other ? other.name : "?"}${e.label ? ` · ${e.label}` : ""}），且不可恢复。`, "删除", true);
                      if (!ok) return;
                      try {
                        await api.del(`/relations/${e.id}`);
                        ui.toast("已删除", "ok");
                        router.dispatch();
                      } catch (err) { ui.toast(err.message, "err"); }
                    },
                  }, ui.icon("delete", "text-[16px]")));
              }))
          : ui.el("p", { class: "font-label-sm text-label-sm text-outline border-t border-surface-container pt-space-xs" }, "该节点暂无关系"),
        ui.el("button", {
          class: "mt-1 flex items-center justify-center gap-1 px-3 py-2 rounded-lg bg-secondary-fixed text-on-secondary-fixed hover:bg-secondary-fixed-dim font-label-md text-label-md transition-colors",
          onclick: () => { location.hash = `#/entities/${workId}`; },
        }, ui.icon("badge", "text-[18px]"), "前往设定库"));
      wrap.append(nodeCard);
      /* 补充内容摘要 */
      api.get(`/entities/${n.id}`).then((full) => {
        const p = nodeCard.querySelector("#graph-node-content");
        if (p) p.textContent = full.content ? full.content.slice(0, 160) : "（暂无设定内容）";
      }).catch(() => {
        const p = nodeCard.querySelector("#graph-node-content");
        if (p) p.textContent = "";
      });
    }

    /* 操作提示 + 无关系提示 */
    view.append(ui.el("div", { class: "flex flex-wrap items-center gap-space-md mt-space-sm font-label-sm text-label-sm text-on-surface-variant" },
      ui.el("span", { class: "inline-flex items-center gap-1" }, ui.icon("mouse", "text-[16px]"), "滚轮缩放 · 空白拖拽平移 · 节点可拖动换位"),
      ui.el("span", { class: "inline-flex items-center gap-1" }, ui.icon("touch_app", "text-[16px]"), "点击节点查看详情 · 点击连线管理关系"),
      !edges.length
        ? ui.el("span", { class: "inline-flex items-center gap-1 text-cinnabar-accent" }, ui.icon("info", "text-[16px]"), "尚无关系，点击右上角「新增关系」")
        : null));

    /* ---------- 新增关系弹窗 ---------- */
    function relationDialog() {
      if (nodes.length < 2) { ui.toast("至少需要两个设定条目才能建立关系", "err"); return; }
      const inputCls = "w-full px-3 py-2 rounded-lg bg-surface-container-low border border-border-feather focus:border-primary outline-none font-body-md text-body-md";
      const opt = (n) => ui.el("option", { value: String(n.id) }, `${n.name}（${catOf(n.category).label}）`);
      const fromSel = ui.el("select", { class: inputCls }, nodes.map(opt));
      const toSel = ui.el("select", { class: inputCls }, nodes.map(opt));
      if (nodes[1]) toSel.value = String(nodes[1].id);
      const labelIn = ui.el("input", { class: inputCls, placeholder: "如：师徒 / 敌对 / 持有", list: "rel-suggest" });
      const suggest = ui.el("datalist", { id: "rel-suggest" }, REL_SUGGESTIONS.map((s) => ui.el("option", { value: s })));

      const close = (ok) => {
        overlay.remove();
        if (!ok) return;
        const from_id = Number(fromSel.value), to_id = Number(toSel.value);
        if (from_id === to_id) { ui.toast("不能与自身建立关系", "err"); return; }
        (async () => {
          try {
            await api.post(`/works/${workId}/relations`, { from_id, to_id, label: labelIn.value.trim() });
            ui.toast("关系已创建", "ok");
            router.dispatch();
          } catch (err) { ui.toast(err.message, "err"); }
        })();
      };
      const field = (label, node) => ui.el("label", { class: "flex flex-col gap-1" },
        ui.el("span", { class: "font-label-md text-label-md text-on-surface-variant" }, label), node);
      const overlay = ui.el("div", {
        class: "fixed inset-0 z-[90] bg-ink-black/40 backdrop-blur-sm flex items-center justify-center",
        onclick: (e) => { if (e.target === overlay) close(false); },
      },
        ui.el("div", { class: "bg-surface-container-lowest rounded-xl p-space-lg w-[460px] max-w-[92vw] shadow-[0_12px_32px_rgba(27,42,56,0.12)] flex flex-col gap-space-md" },
          ui.el("h3", { class: "font-headline-sm text-headline-sm text-primary font-semibold" }, "新增关系"),
          field("起点实体", fromSel),
          ui.el("div", { class: "flex justify-center text-on-surface-variant" }, ui.icon("arrow_downward", "text-[18px]")),
          field("终点实体", toSel),
          field("关系标签", labelIn), suggest,
          ui.el("div", { class: "flex justify-end gap-2" },
            ui.el("button", { class: "px-4 py-2 rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md", onclick: () => close(false) }, "取消"),
            ui.el("button", { class: "px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md", onclick: () => close(true) }, "创建"))));
      document.getElementById("modal-root").append(overlay);
      labelIn.focus();
    }
  }
});
