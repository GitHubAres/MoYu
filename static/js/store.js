/* 墨语 MoYu · 全局统一状态中心与跨模块事件总线 (Global Store & Event Bus) */

window.store = (() => {
  /* ---------- 1. 轻量跨模块事件总线 ---------- */
  const listeners = new Map();
  const pageListeners = new Map();

  const events = {
    on(event, handler) {
      if (!listeners.has(event)) listeners.set(event, new Set());
      listeners.get(event).add(handler);
      return () => events.off(event, handler);
    },
    off(event, handler) {
      if (listeners.has(event)) listeners.get(event).delete(handler);
    },
    onPage(pageName, event, handler) {
      const key = `${pageName}:${event}`;
      if (pageListeners.has(key)) {
        events.off(event, pageListeners.get(key));
      }
      pageListeners.set(key, handler);
      events.on(event, handler);
    },
    emit(event, payload) {
      if (listeners.has(event)) {
        listeners.get(event).forEach((fn) => {
          try { fn(payload); } catch (err) { console.error("[Store Event Error]", event, err); }
        });
      }
    },
  };

  /* ---------- 2. 当前作品状态 ---------- */
  let activeWorkId = null;
  let activeWork = null;

  const work = {
    getId: () => activeWorkId,
    get: () => activeWork,
    set(w) {
      activeWork = w;
      activeWorkId = w ? w.id : null;
      events.emit("work:changed", activeWork);
    },
  };

  /* ---------- 3. 剧情三位一体状态中心 (大纲 ↔ 时间线 ↔ 伏笔) ---------- */
  const plotCache = {
    workId: null,
    tree: [],
    timelineEvents: [],
    foreshadows: [],
    lastLoadedAt: 0,
  };

  const plot = {
    async load(workId, force = false) {
      if (!workId) return null;
      const now = Date.now();
      if (!force && plotCache.workId === workId && (now - plotCache.lastLoadedAt < 10000)) {
        return {
          tree: plotCache.tree,
          timelineEvents: plotCache.timelineEvents,
          foreshadows: plotCache.foreshadows,
        };
      }

      try {
        const [tree, timeline, foreshadows] = await Promise.all([
          api.get(`/works/${workId}/outline`).catch(() => []),
          api.get(`/works/${workId}/timeline`).catch(() => []),
          api.get(`/works/${workId}/foreshadows`).catch(() => []),
        ]);
        plotCache.workId = workId;
        plotCache.tree = Array.isArray(tree) ? tree : [];
        plotCache.timelineEvents = Array.isArray(timeline) ? timeline : [];
        plotCache.foreshadows = Array.isArray(foreshadows) ? foreshadows : [];
        plotCache.lastLoadedAt = now;
        return {
          tree: plotCache.tree,
          timelineEvents: plotCache.timelineEvents,
          foreshadows: plotCache.foreshadows,
        };
      } catch (err) {
        console.error("[Store Plot Load Error]", err);
        return null;
      }
    },

    getFlatOutlineNodes() {
      const flat = [];
      (function walk(nodes) {
        if (!Array.isArray(nodes)) return;
        for (const n of nodes) {
          flat.push({ id: n.id, title: n.title, synopsis: n.synopsis, status: n.status });
          if (n.children) walk(n.children);
        }
      })(plotCache.tree);
      return flat;
    },

    notifyChanged(workId, extra = {}) {
      if (plotCache.workId === workId) {
        plotCache.lastLoadedAt = 0; // 使缓存失效
      }
      events.emit("plot:changed", { workId, ...extra });
    },
  };

  return {
    events,
    work,
    plot,
  };
})();
