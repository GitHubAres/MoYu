// 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
// Licensed under the MIT License. See LICENSE.
/* 热点雷达独立页面 (hotradar.js)
 * 职责：
 * 1. 监测全网网文平台（起点/番茄/晋江）公开热榜元数据；
 * 2. 支持平台切换、题材搜索、仅看收藏过滤；
 * 3. 一键立项建议（必须先预览草稿 + 用户二次确认方可正式入库，坚守红线）；
 * 4. 热点条目收藏与取消收藏，沉淀 MOYU:ASSETS 资产；
 * 5. 我的题材 vs 全网热点 对比视图回灌；
 * 6. 遵循 Literary Minimalist Ink 规范（黛青/朱砂、Noto Serif、响应式热区 >=44px）。
 */

router.register("hotradar", async function (container) {
  container.innerHTML = "";

  // 状态变量
  let currentPlatform = "";
  let currentGenre = "";
  let onlyCollected = false;
  let cachedItems = [];
  let userWorks = [];

  // 获取当前作者作品列表（用于我的题材 vs 全网热点 对比分析）
  try {
    const worksRes = await api.get("/works");
    userWorks = Array.isArray(worksRes) ? worksRes : (worksRes.items || []);
  } catch (e) {
    userWorks = [];
  }

  // 主布局框架
  const pageWrap = ui.el("div", {
    class: "flex flex-col gap-space-lg p-space-md md:p-space-xl max-w-7xl mx-auto w-full transition-colors duration-200"
  });

  // 1. 顶部 Header 区域
  const header = ui.el("div", {
    class: "flex flex-col md:flex-row md:items-center justify-between gap-space-md border-b border-outline-variant pb-space-md"
  });

  const headerLeft = ui.el("div", { class: "flex flex-col gap-1" },
    ui.el("div", { class: "flex items-center gap-2" },
      ui.icon("radar", { class: "text-primary text-[28px]" }),
      ui.el("h1", {
        class: "font-serif text-title-lg md:text-headline-sm font-bold text-on-surface tracking-wide"
      }, "全网热点雷达")
    ),
    ui.el("p", {
      class: "font-body-sm text-on-surface-variant"
    }, "监测全网公开爆款热榜，赋能创作前置灵感立项与工作流推演。数据每 6 小时自动同步。")
  );

  // 刷新按钮与对比视图切换
  let showCompareView = false;
  const compareToggleBtn = ui.el("button", {
    class: "min-h-[44px] px-4 py-2 rounded-xl border border-outline text-on-surface hover:bg-surface-container-high transition-all duration-200 flex items-center gap-1.5 font-label-md",
    onclick: () => {
      showCompareView = !showCompareView;
      compareToggleBtn.classList.toggle("bg-primary-container", showCompareView);
      compareToggleBtn.classList.toggle("text-on-primary-container", showCompareView);
      renderMainContent();
    }
  }, ui.icon("insights", { class: "text-[20px]" }), "我的题材 vs 全网热点");

  const refreshBtn = ui.el("button", {
    class: "min-h-[44px] px-4 py-2 rounded-xl bg-primary text-on-primary hover:bg-primary-dim transition-all duration-200 flex items-center gap-1.5 font-label-md shadow-sm",
    onclick: async () => {
      refreshBtn.disabled = true;
      refreshBtn.classList.add("opacity-60");
      ui.toast("正在拉取全网最新榜单，请稍候...", "info");
      try {
        const res = await api.post("/hotradar/refresh", {});
        if (res.ok) {
          ui.toast(res.message || "热榜刷新成功！", "ok");
          loadData();
        } else {
          ui.toast(String(res.message || "刷新过于频繁，请稍后再试"), "warn");
        }
      } catch (err) {
        ui.toast("刷新失败：" + String(err?.message || err), "err");
      } finally {
        refreshBtn.disabled = false;
        refreshBtn.classList.remove("opacity-60");
      }
    }
  }, ui.icon("sync", { class: "text-[20px]" }), "立即刷新");

  const headerRight = ui.el("div", { class: "flex items-center gap-3 flex-wrap" },
    compareToggleBtn,
    refreshBtn
  );

  header.append(headerLeft, headerRight);

  // 2. 筛选过滤栏 (平台 Tabs + 题材搜索 + 收藏过滤器)
  const filterBar = ui.el("div", {
    class: "flex flex-col md:flex-row md:items-center justify-between gap-space-md bg-surface-container-low p-space-md rounded-2xl border border-outline-variant"
  });

  const platforms = [
    { id: "", label: "全部平台" },
    { id: "起点", label: "起点中文网" },
    { id: "番茄", label: "番茄小说" },
    { id: "晋江", label: "晋江文学城" },
  ];

  const tabsWrap = ui.el("div", { class: "flex items-center gap-2 overflow-x-auto py-1" });
  platforms.forEach(p => {
    const btn = ui.el("button", {
      class: "min-h-[44px] px-4 py-2 rounded-lg font-label-md transition flex items-center gap-1",
      onclick: () => {
        currentPlatform = p.id;
        renderTabs();
        loadData();
      }
    }, p.label);
    btn.dataset.platform = p.id;
    tabsWrap.append(btn);
  });

  function renderTabs() {
    tabsWrap.querySelectorAll("button").forEach(b => {
      const active = b.dataset.platform === currentPlatform;
      b.className = "min-h-[44px] px-4 py-2 rounded-lg font-label-md transition flex items-center gap-1 " +
        (active ? "bg-primary text-on-primary shadow-sm" : "text-on-surface-variant hover:bg-surface-container-high");
    });
  }

  // 题材搜索与收藏过滤
  const searchInput = ui.el("input", {
    type: "text",
    placeholder: "搜索题材标签（如：玄幻/悬疑/系统）...",
    class: "min-h-[44px] px-3 py-2 rounded-lg border border-outline bg-surface text-on-surface font-body-sm focus:outline-none focus:ring-2 focus:ring-primary w-full md:w-64"
  });
  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      currentGenre = searchInput.value.trim();
      loadData();
    }
  });

  const searchBtn = ui.el("button", {
    class: "min-h-[44px] px-3 py-2 rounded-lg bg-surface-container-high text-on-surface hover:bg-surface-container-highest transition flex items-center",
    onclick: () => {
      currentGenre = searchInput.value.trim();
      loadData();
    }
  }, ui.icon("search", { class: "text-[20px]" }));

  const collectToggleBtn = ui.el("button", {
    class: "min-h-[44px] px-3 py-2 rounded-lg border border-outline-variant text-on-surface-variant hover:bg-surface-container-high transition flex items-center gap-1 font-label-sm",
    onclick: () => {
      onlyCollected = !onlyCollected;
      collectToggleBtn.classList.toggle("bg-tertiary-container", onlyCollected);
      collectToggleBtn.classList.toggle("text-on-tertiary-container", onlyCollected);
      collectToggleBtn.classList.toggle("border-tertiary", onlyCollected);
      loadData();
    }
  }, ui.icon("bookmark", { class: "text-[18px]" }), "仅看收藏");

  const filterRight = ui.el("div", { class: "flex items-center gap-2 flex-wrap" },
    searchInput,
    searchBtn,
    collectToggleBtn
  );

  filterBar.append(tabsWrap, filterRight);

  // 3. 核心内容容器（榜单流 或 对比视图）
  const contentContainer = ui.el("div", { class: "w-full" });

  pageWrap.append(header, filterBar, contentContainer);
  container.append(pageWrap);

  renderTabs();
  loadData();

  // 数据加载函数
  async function loadData() {
    contentContainer.innerHTML = "";
    contentContainer.append(ui.el("div", { class: "p-12 text-center text-on-surface-variant font-body-md" }, "正在加载热榜数据..."));

    const params = new URLSearchParams();
    if (currentPlatform) params.append("platform", currentPlatform);
    if (currentGenre) params.append("genre", currentGenre);
    if (onlyCollected) params.append("collected", "1");
    params.append("limit", "100");

    try {
      const res = await api.get("/hotradar/list?" + params.toString());
      if (!res.ok) throw new Error(String(res.message || "请求失败"));
      cachedItems = res.items || [];
      renderMainContent();
    } catch (err) {
      contentContainer.innerHTML = "";
      contentContainer.append(ui.el("div", {
        class: "p-8 text-center text-error bg-error-container/20 rounded-2xl border border-error/30"
      }, "热榜加载失败：" + String(err?.message || err)));
    }
  }

  function renderMainContent() {
    contentContainer.innerHTML = "";
    if (showCompareView) {
      contentContainer.append(buildCompareView());
    } else {
      contentContainer.append(buildCardGrid(cachedItems));
    }
  }

  // 视图 A：卡片网格流
  function buildCardGrid(items) {
    if (!items || items.length === 0) {
      return ui.el("div", {
        class: "flex flex-col items-center justify-center p-16 gap-3 bg-surface-container-lowest rounded-2xl border border-dashed border-outline-variant text-center"
      },
        ui.icon("filter_alt_off", { class: "text-4xl text-on-surface-variant opacity-60" }),
        ui.el("div", { class: "font-serif text-title-md text-on-surface font-semibold" }, "暂无匹配热点"),
        ui.el("p", { class: "font-body-sm text-on-surface-variant max-w-sm" },
          onlyCollected ? "您尚未收藏该筛选条件下的热点条目。可以在榜单中点击书签图标收藏热点。" : "当前筛选条件下暂无热榜数据，建议点击右上角「立即刷新」同步全网热榜。"
        )
      );
    }

    const grid = ui.el("div", {
      class: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-space-md"
    });

    items.forEach(item => {
      grid.append(createTopicCard(item));
    });

    return grid;
  }

  // 单卡片渲染
  function createTopicCard(item) {
    const isCollected = !!item.collected;
    const card = ui.el("div", {
      class: "flex flex-col justify-between p-space-md rounded-2xl bg-surface border border-outline-variant hover:border-primary/50 hover:shadow-md transition-all duration-200 gap-space-sm group"
    });

    // 头部：排名 + 平台徽标 + 收藏按钮
    const cardTop = ui.el("div", { class: "flex items-center justify-between" });

    const rankBadgeClass = item.rank === 1 ? "bg-error text-on-error font-bold" :
      item.rank === 2 ? "bg-amber-600 text-white font-bold" :
      item.rank === 3 ? "bg-amber-500 text-white font-bold" :
      "bg-surface-container-high text-on-surface-variant font-medium";

    const leftBadges = ui.el("div", { class: "flex items-center gap-2" },
      ui.el("span", {
        class: "px-2 py-0.5 rounded-md text-xs " + rankBadgeClass
      }, "TOP " + item.rank),
      ui.el("span", {
        class: "px-2 py-0.5 rounded-md text-xs font-semibold " +
          (item.platform === "起点" ? "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200" :
           item.platform === "番茄" ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200" :
           "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200")
      }, item.platform)
    );

    const bookmarkBtn = ui.el("button", {
      class: "min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg hover:bg-surface-container-high transition " +
        (isCollected ? "text-primary" : "text-on-surface-variant/60 hover:text-on-surface"),
      title: isCollected ? "取消收藏" : "收藏至创作资产",
      onclick: async (e) => {
        e.stopPropagation();
        try {
          const res = await api.post("/hotradar/collect", { topic_id: item.id });
          if (res.ok) {
            item.collected = res.collected;
            ui.toast(String(res.message || "操作成功"), "ok");
            loadData();
          }
        } catch (err) {
          ui.toast("收藏操作失败：" + String(err?.message || err), "err");
        }
      }
    }, ui.icon(isCollected ? "bookmark" : "bookmark_border", { class: "text-[20px]" }));

    cardTop.append(leftBadges, bookmarkBtn);

    // 中间：标题 + 题材标签 + 热度/作者
    const cardBody = ui.el("div", { class: "flex flex-col gap-2 my-1" },
      ui.el("h3", {
        class: "font-serif text-title-md font-bold text-on-surface line-clamp-1 group-hover:text-primary transition-colors"
      }, item.title),
      ui.el("div", { class: "flex items-center gap-2 flex-wrap" },
        (item.genre_tags || []).slice(0, 4).map(tag =>
          ui.el("span", {
            class: "px-2 py-0.5 rounded bg-surface-container text-on-surface-variant text-xs"
          }, tag)
        )
      ),
      ui.el("div", { class: "flex items-center justify-between text-xs text-on-surface-variant pt-1" },
        ui.el("span", {}, item.author ? "作者：" + item.author : "热榜作品"),
        ui.el("span", { class: "font-mono font-medium text-tertiary" }, "热度: " + (item.heat ? item.heat.toLocaleString() : "爆款"))
      )
    );

    // 底部：操作按钮（详情 + 一键立项）
    const cardBottom = ui.el("div", {
      class: "flex items-center justify-between gap-2 pt-2 border-t border-outline-variant/60"
    });

    const detailsBtn = ui.el("button", {
      class: "min-h-[44px] px-3 py-1.5 rounded-lg text-xs font-label-md text-on-surface-variant hover:bg-surface-container-high transition flex items-center gap-1",
      onclick: () => showTopicDetails(item)
    }, ui.icon("visibility", { class: "text-[16px]" }), "详情");

    const outlineBtn = ui.el("button", {
      class: "min-h-[44px] px-3 py-1.5 rounded-lg text-xs font-label-md bg-primary-container text-on-primary-container hover:bg-primary-container/80 transition flex items-center gap-1 font-semibold",
      onclick: () => startOutlineFromTopic(item)
    }, ui.icon("drive_file_rename_outline", { class: "text-[16px]" }), "一键立项");

    cardBottom.append(detailsBtn, outlineBtn);
    card.append(cardTop, cardBody, cardBottom);
    return card;
  }

  // 弹窗：热点详情展示
  function showTopicDetails(item) {
    const modal = ui.modal(
      "《" + item.title + "》· 热点详情",
      ui.el("div", { class: "flex flex-col gap-space-md p-space-sm" },
        ui.el("div", { class: "flex items-center gap-2" },
          ui.el("span", { class: "px-2 py-0.5 rounded bg-primary-container text-on-primary-container text-xs font-bold" }, item.platform),
          ui.el("span", { class: "font-label-md text-sm text-on-surface-variant" }, "当前排名：第 " + item.rank + " 名"),
          ui.el("span", { class: "font-label-md text-sm text-on-surface-variant" }, "热度：" + (item.heat || "-"))
        ),
        ui.el("div", { class: "text-sm text-on-surface-variant" }, item.author ? "原作作者：" + item.author : "平台公开热榜作品"),
        ui.el("div", { class: "flex flex-col gap-1" },
          ui.el("span", { class: "font-label-sm text-xs font-semibold text-on-surface" }, "题材标签："),
          ui.el("div", { class: "flex flex-wrap gap-1" },
            (item.genre_tags || []).map(t => ui.el("span", { class: "px-2 py-1 rounded bg-surface-container-high text-xs" }, t))
          )
        ),
        ui.el("div", { class: "text-xs text-outline mt-2" }, "数据同步时间：" + (item.fetched_at || "-"))
      ),
      [
        ui.el("button", {
          class: "min-h-[44px] px-4 py-2 rounded-xl bg-primary text-on-primary font-label-md transition",
          onclick: () => {
            modal.close();
            startOutlineFromTopic(item);
          }
        }, "从该热点立项"),
        ui.el("button", {
          class: "min-h-[44px] px-4 py-2 rounded-xl bg-surface-container-high text-on-surface font-label-md transition",
          onclick: () => modal.close()
        }, "关闭")
      ]
    );
  }

  // 弹窗：一键立项流程（严格遵循安全红线：必须生成草稿预览、由作者确认后方可写入 works 表）
  async function startOutlineFromTopic(item) {
    ui.toast("正在装配立项建议草稿...", "info");
    try {
      const res = await api.post("/hotradar/to-outline", { topic_id: item.id });
      if (!res.ok || !res.draft) {
        throw new Error(res.message || "未能生成立项草稿");
      }
      const draft = res.draft;

      // 呈现确认草稿表单弹窗
      const titleInput = ui.el("input", {
        type: "text",
        value: draft.suggested_title,
        class: "w-full min-h-[44px] px-3 py-2 rounded-lg border border-outline bg-surface text-on-surface font-body-sm focus:ring-2 focus:ring-primary focus:outline-none"
      });

      const genreInput = ui.el("input", {
        type: "text",
        value: draft.genre,
        class: "w-full min-h-[44px] px-3 py-2 rounded-lg border border-outline bg-surface text-on-surface font-body-sm focus:ring-2 focus:ring-primary focus:outline-none"
      });

      const introInput = ui.el("textarea", {
        rows: 4,
        class: "w-full p-3 rounded-lg border border-outline bg-surface text-on-surface font-body-sm focus:ring-2 focus:ring-primary focus:outline-none",
      }, draft.direction + "\n\n【目标读者】" + draft.target_readers + "\n\n【故事简介】" + draft.one_sentence_story);

      const formBody = ui.el("div", { class: "flex flex-col gap-3 p-1 max-w-xl" },
        ui.el("div", { class: "text-xs text-on-surface-variant bg-surface-container-low p-2 rounded border border-outline-variant" },
          "参考爆款：" + draft.reference_work + " · 此内容为 AI/系统根据榜单推演的立项建议，请确认或修改后点击「创建作品」入库。"
        ),
        ui.el("div", { class: "flex flex-col gap-1" },
          ui.el("label", { class: "text-xs font-semibold text-on-surface" }, "作品名称："),
          titleInput
        ),
        ui.el("div", { class: "flex flex-col gap-1" },
          ui.el("label", { class: "text-xs font-semibold text-on-surface" }, "主要流派题材："),
          genreInput
        ),
        ui.el("div", { class: "flex flex-col gap-1" },
          ui.el("label", { class: "text-xs font-semibold text-on-surface" }, "立项故事梗概与方向："),
          introInput
        )
      );

      const confirmModal = ui.modal(
        "立项确认与作品草稿入库",
        formBody,
        [
          ui.el("button", {
            class: "min-h-[44px] px-4 py-2 rounded-xl bg-primary text-on-primary font-label-md transition shadow-sm",
            onclick: async () => {
              const newTitle = titleInput.value.trim();
              if (!newTitle) {
                ui.toast("作品名称不能为空", "warn");
                return;
              }
              try {
                // 写入 works 表正式创建作品
                const work = await api.post("/works", {
                  title: newTitle,
                  genre: genreInput.value.trim(),
                  intro: introInput.value.trim(),
                });
                confirmModal.close();
                ui.toast("立项成功！已为您创建新作品《" + work.title + "》", "ok");
                // 跳转到故事大纲或工作台
                location.hash = "#/workbench?work_id=" + work.id;
              } catch (err) {
                ui.toast("作品创建失败：" + String(err?.message || err), "err");
              }
            }
          }, "确认并创建新作品"),
          ui.el("button", {
            class: "min-h-[44px] px-4 py-2 rounded-xl bg-surface-container-high text-on-surface font-label-md transition",
            onclick: () => confirmModal.close()
          }, "取消")
        ]
      );
    } catch (err) {
      ui.toast("生成立项建议失败：" + String(err?.message || err), "err");
    }
  }

  // 视图 B：我的题材 vs 全网热点 对比视图（M8 反向回灌）
  function buildCompareView() {
    const wrap = ui.el("div", { class: "flex flex-col gap-space-lg" });

    // 统计全网热榜中 Top 题材频次
    const genreStats = {};
    cachedItems.forEach(item => {
      (item.genre_tags || []).forEach(t => {
        genreStats[t] = (genreStats[t] || 0) + 1;
      });
    });

    const topGenres = Object.entries(genreStats)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10);

    // 统计作者现有作品流派
    const myGenres = new Set();
    userWorks.forEach(w => {
      if (w.genre) {
        w.genre.split(/[,/，、 ]/).forEach(g => {
          if (g.trim()) myGenres.add(g.trim());
        });
      }
    });

    // 顶部卡片
    const overviewCard = ui.el("div", {
      class: "p-space-lg rounded-2xl bg-surface-container-low border border-outline-variant flex flex-col md:flex-row items-center justify-between gap-4"
    },
      ui.el("div", { class: "flex flex-col gap-1" },
        ui.el("h3", { class: "font-serif text-title-md font-bold text-on-surface" }, "题材生态洞察 · 差异化定位"),
        ui.el("p", { class: "text-sm text-on-surface-variant" },
          "对比您的现有在创作品与当前三大平台爆款热门题材分布，发现红海与蓝海切入契机。"
        )
      ),
      ui.el("div", { class: "flex items-center gap-4 text-center" },
        ui.el("div", { class: "p-3 rounded-xl bg-surface border border-outline-variant" },
          ui.el("div", { class: "text-xl font-bold text-primary font-mono" }, String(userWorks.length)),
          ui.el("div", { class: "text-xs text-on-surface-variant" }, "我的作品数")
        ),
        ui.el("div", { class: "p-3 rounded-xl bg-surface border border-outline-variant" },
          ui.el("div", { class: "text-xl font-bold text-tertiary font-mono" }, String(topGenres.length)),
          ui.el("div", { class: "text-xs text-on-surface-variant" }, "热门题材数")
        )
      )
    );

    // 对比列表
    const listCard = ui.el("div", {
      class: "p-space-lg rounded-2xl bg-surface border border-outline-variant flex flex-col gap-space-md"
    },
      ui.el("h4", { class: "font-label-lg font-bold text-on-surface" }, "当前全网 TOP10 热门题材 vs 我的创作覆盖：")
    );

    topGenres.forEach(([genre, count], idx) => {
      const isCovered = Array.from(myGenres).some(mg => mg.includes(genre) || genre.includes(mg));
      const row = ui.el("div", {
        class: "flex items-center justify-between p-3 rounded-xl bg-surface-container-low hover:bg-surface-container transition"
      },
        ui.el("div", { class: "flex items-center gap-3" },
          ui.el("span", { class: "font-mono text-sm font-bold text-on-surface-variant w-6" }, "#" + (idx + 1)),
          ui.el("span", { class: "font-serif font-bold text-on-surface text-base" }, genre),
          ui.el("span", { class: "text-xs text-on-surface-variant font-mono" }, "上榜频次: " + count + " 本")
        ),
        ui.el("div", { class: "flex items-center gap-2" },
          isCovered ?
            ui.el("span", { class: "px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200 flex items-center gap-1" },
              ui.icon("check_circle", { class: "text-[14px]" }), "我的题材已覆盖") :
            ui.el("span", { class: "px-2.5 py-1 rounded-full text-xs font-semibold bg-surface-container-high text-on-surface-variant flex items-center gap-1" },
              ui.icon("radio_button_unchecked", { class: "text-[14px]" }), "蓝海待探索")
        )
      );
      listCard.append(row);
    });

    wrap.append(overviewCard, listCard);
    return wrap;
  }
});
