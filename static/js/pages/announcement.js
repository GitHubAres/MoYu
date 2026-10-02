/* 墨语 MoYu - 公告模块 (v1.5.0)
   1. 迷你 Markdown 渲染器（白名单标签 + 仅 https: URL 协议防 XSS）
   2. 启动浮层组件（z-[95]，normal/force 两级交互）
   3. 公告中心页面（#/announcements）
*/

(function () {
  /* ================= 1. 迷你安全 Markdown 渲染器 ================= */
  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function sanitizeHttpsUrl(url) {
    if (!url) return "";
    const trimmed = String(url).trim();
    // 严格白名单：仅允许 https:// 开头的链接，坚决剥除 javascript: / http: / data: 等
    if (/^https:\/\/[a-zA-Z0-9\-._~:/?#[\]@!$&'()*+,;=%]+$/i.test(trimmed)) {
      return trimmed;
    }
    return "";
  }

  function renderInline(text) {
    let escaped = escapeHtml(text);

    // 粗体：**text**
    escaped = escaped.replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-primary">$1</strong>');

    // 链接：[text](url) -> 仅允许 https: 协议
    escaped = escaped.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function (match, linkText, rawUrl) {
      const safeUrl = sanitizeHttpsUrl(rawUrl);
      if (safeUrl) {
        return `<a href="${safeUrl}" target="_blank" rel="noopener noreferrer" class="text-secondary underline underline-offset-2 hover:opacity-80 transition-opacity inline-flex items-center gap-0.5">${linkText}</a>`;
      }
      return linkText; // 协议不合规时降级为纯文本，无 XSS 风险
    });

    return escaped;
  }

  function renderMiniMarkdown(md) {
    if (!md) return "";
    const lines = String(md).replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n");
    const output = [];
    let inList = false;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();

      if (!line) {
        if (inList) {
          output.push("</ul>");
          inList = false;
        }
        continue;
      }

      // ## 二级标题
      if (line.startsWith("## ")) {
        if (inList) { output.push("</ul>"); inList = false; }
        output.push(`<h2 class="font-headline-sm text-headline-sm font-semibold text-primary mt-3 mb-1.5">${renderInline(line.slice(3))}</h2>`);
        continue;
      }

      // ### 三级标题
      if (line.startsWith("### ")) {
        if (inList) { output.push("</ul>"); inList = false; }
        output.push(`<h3 class="font-body-md text-body-md font-semibold text-primary mt-2.5 mb-1">${renderInline(line.slice(4))}</h3>`);
        continue;
      }

      // - 列表项 或 * 列表项
      if (line.startsWith("- ") || line.startsWith("* ")) {
        if (!inList) {
          output.push('<ul class="my-1.5 space-y-1">');
          inList = true;
        }
        output.push(`<li class="list-disc ml-5 text-body-sm text-on-surface leading-relaxed">${renderInline(line.slice(2))}</li>`);
        continue;
      }

      // 普通段落
      if (inList) { output.push("</ul>"); inList = false; }
      output.push(`<p class="my-1.5 text-body-sm text-on-surface leading-relaxed">${renderInline(line)}</p>`);
    }

    if (inList) { output.push("</ul>"); }
    return output.join("");
  }

  /* ================= 2. 启动公告浮层组件 ================= */
  function showAnnouncementModal(ann) {
    if (!ann) return;

    // 检查是否有现有公告浮层，避免并发重复弹窗
    const existing = document.getElementById("moyu-announcement-modal");
    if (existing) existing.remove();

    const isForce = ann.level === "force";

    // 遮罩层：高 z-index (z-[95])，高于现有任何普通弹窗
    const modalWrap = ui.el("div", {
      id: "moyu-announcement-modal",
      class: "fixed inset-0 z-[95] flex items-center justify-center p-4 bg-ink-black/40 backdrop-blur-sm transition-all duration-200 select-none animate-fade-in",
    });

    // 卡片内容器
    const card = ui.el("div", {
      class: "bg-surface-container-lowest text-primary rounded-2xl shadow-2xl border border-outline-variant/30 max-w-lg w-full flex flex-col overflow-hidden max-h-[85vh] transition-all",
    });

    // 头部：级别标识、标题、版本号
    const badgeCls = isForce
      ? "bg-error-container text-on-error-container"
      : "bg-secondary-container text-on-secondary-container";
    const badgeText = isForce ? "重要公告" : "系统更新";

    const head = ui.el("div", { class: "p-space-xl pb-space-sm flex flex-col gap-1 border-b border-outline-variant/20" },
      ui.el("div", { class: "flex items-center justify-between" },
        ui.el("span", { class: `px-2 py-0.5 rounded text-[11px] font-semibold ${badgeCls}` }, badgeText),
        ann.version_tag && ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant font-mono" }, `v${ann.version_tag}`)),
      ui.el("h2", { class: "font-headline-md text-headline-md font-semibold text-primary mt-1" }, ann.title || "系统公告"));

    // 中部：Markdown 渲染正文（可滚动）
    const bodyBox = ui.el("div", {
      class: "px-space-xl py-space-md overflow-y-auto max-h-72 select-text font-sans divide-y divide-outline-variant/10",
    });
    bodyBox.innerHTML = renderMiniMarkdown(ann.body_md);

    // 底部：动作操作栏
    const actions = ui.el("div", {
      class: "p-space-xl pt-space-sm flex flex-wrap items-center justify-between gap-space-md border-t border-outline-variant/20 bg-surface-container-low/30",
    });

    // 外链
    const safeLink = sanitizeHttpsUrl(ann.link_url);
    if (safeLink) {
      actions.append(
        ui.el("a", {
          href: safeLink,
          target: "_blank",
          rel: "noopener noreferrer",
          class: "font-label-md text-label-md text-secondary hover:underline inline-flex items-center gap-1 min-h-[44px]",
        }, ui.icon("open_in_new", "text-[16px]"), ann.link_text || "了解更多")
      );
    } else {
      actions.append(ui.el("span")); // 占位保持右对齐
    }

    const btnGroup = ui.el("div", { class: "flex items-center gap-space-sm" });

    function closeModal() {
      window.removeEventListener("keydown", onKeyDown);
      modalWrap.remove();
    }

    if (!isForce) {
      // normal 级：点击「我知道了」记录确认，不再提示
      const okBtn = ui.el("button", {
        class: "px-space-lg py-2 rounded-xl bg-primary text-on-primary hover:bg-primary-container transition-all font-label-md text-label-md shadow-sm min-h-[44px]",
        onclick: async () => {
          closeModal();
          try { await api.post(`/announcements/${ann.id}/ack`, { ack_type: "confirm" }); } catch (_) {}
        },
      }, "我知道了");
      btnGroup.append(okBtn);
    } else {
      // force 级：每次启动都弹，提供「知道了」与「7 天内不再显示」
      const dismissBtn = ui.el("button", {
        class: "text-on-surface-variant hover:text-primary transition-colors font-label-sm text-label-sm px-3 py-2 min-h-[44px]",
        onclick: async () => {
          closeModal();
          try {
            // 本地记录 7 天
            localStorage.setItem("moyu_announcement_dismiss_" + ann.id, String(Date.now() + 7 * 86400 * 1000));
            await api.post(`/announcements/${ann.id}/ack`, { ack_type: "dismiss_forever" });
          } catch (_) {}
        },
      }, "7 天内不再显示");

      const viewBtn = ui.el("button", {
        class: "px-space-lg py-2 rounded-xl bg-primary text-on-primary hover:bg-primary-container transition-all font-label-md text-label-md shadow-sm min-h-[44px]",
        onclick: async () => {
          closeModal();
          try { await api.post(`/announcements/${ann.id}/ack`, { ack_type: "view" }); } catch (_) {}
        },
      }, "知道了，本次不再提示");

      btnGroup.append(dismissBtn, viewBtn);
    }

    actions.append(btnGroup);
    card.append(head, bodyBox, actions);
    modalWrap.append(card);

    // 交互关闭逻辑
    function onKeyDown(e) {
      if (e.key === "Escape") {
        if (!isForce) {
          closeModal();
          api.post(`/announcements/${ann.id}/ack`, { ack_type: "confirm" }).catch(() => {});
        }
      }
    }
    window.addEventListener("keydown", onKeyDown);

    // 遮罩点击：仅在 normal 模式下生效，force 模式防误触禁止点击背景关闭
    modalWrap.addEventListener("click", (e) => {
      if (e.target === modalWrap && !isForce) {
        closeModal();
        api.post(`/announcements/${ann.id}/ack`, { ack_type: "confirm" }).catch(() => {});
      }
    });

    const root = document.getElementById("modal-root") || document.body;
    root.append(modalWrap);
  }

  async function checkOnBoot() {
    try {
      const res = await api.get("/announcements/latest");
      if (!res || !res.ok || !res.announcement) return;
      const ann = res.announcement;

      // 1. normal 级：若已 ack，则静默不再弹
      if (ann.level === "normal" && ann.acked) {
        return;
      }

      // 2. force 级：检查 7 天内不再显示标志
      if (ann.level === "force") {
        const dismissUntil = localStorage.getItem("moyu_announcement_dismiss_" + ann.id);
        if (dismissUntil && Number(dismissUntil) > Date.now()) {
          return;
        }
        if (ann.ack_type === "dismiss_forever") {
          return;
        }
      }

      // 3. 弹出公告浮层
      showAnnouncementModal(ann);
    } catch (e) {
      console.debug("Announcement checkOnBoot error (silent):", e);
    }
  }

  window.announcement = {
    checkOnBoot,
    showModal: showAnnouncementModal,
    renderMiniMarkdown,
    sanitizeHttpsUrl,
  };

  /* ================= 3. M3 公告中心页面 (#/announcements) ================= */
  registerPage("announcements", async (view) => {
    ui.setCrumb("公告中心");

    const header = ui.el("div", { class: "flex flex-col gap-1 pb-space-lg" },
      ui.el("span", { class: "font-label-sm text-label-sm uppercase tracking-widest text-secondary font-semibold" }, "Announcements · 系统动态"),
      ui.el("h1", { class: "font-display text-display text-primary tracking-tight" }, "系统公告与版本特性"),
      ui.el("p", { class: "font-body-md text-body-md text-on-surface-variant" },
        "查看墨语 MoYu 历史版本特性说明、重要公告与系统维护通知。"));

    const listContainer = ui.el("div", { class: "flex flex-col gap-space-lg max-w-4xl" });

    async function loadList() {
      listContainer.innerHTML = "";
      listContainer.append(
        ui.el("div", { class: "p-space-xl text-center text-on-surface-variant font-body-sm text-body-sm" }, "正在加载公告列表...")
      );

      try {
        const res = await api.get("/announcements");
        listContainer.innerHTML = "";
        const list = res.announcements || [];

        if (list.length === 0) {
          listContainer.append(
            ui.el("div", { class: "p-space-xl rounded-xl bg-surface-container-low text-center text-on-surface-variant font-body-sm text-body-sm" },
              ui.icon("article", "text-[32px] text-outline mb-2"),
              ui.el("p", {}, "暂无历史公告记录。"))
          );
          return;
        }

        for (const item of list) {
          const isForce = item.level === "force";
          const badgeCls = isForce
            ? "bg-error-container text-on-error-container"
            : "bg-secondary-container text-on-secondary-container";
          const badgeText = isForce ? "重要公告" : "版本更新";

          const readBadge = item.acked
            ? ui.el("span", { class: "font-label-sm text-label-sm text-outline px-2 py-0.5 rounded bg-surface-container" }, "已读")
            : ui.el("span", { class: "font-label-sm text-label-sm text-secondary font-semibold px-2 py-0.5 rounded bg-secondary-container" }, "未读");

          const card = ui.el("article", {
            class: "p-space-xl rounded-xl bg-surface-container-lowest border border-outline-variant/30 shadow-sm flex flex-col gap-space-md transition-all hover:shadow-md",
          });

          // 头部栏
          const topBar = ui.el("div", { class: "flex items-start justify-between gap-space-md" },
            ui.el("div", { class: "flex flex-col gap-1" },
              ui.el("div", { class: "flex items-center gap-2" },
                ui.el("span", { class: `px-2 py-0.5 rounded text-[11px] font-semibold ${badgeCls}` }, badgeText),
                item.version_tag && ui.el("span", { class: "font-label-sm text-label-sm font-mono text-on-surface-variant" }, `v${item.version_tag}`),
                ui.el("span", { class: "font-label-sm text-label-sm text-on-surface-variant" }, (item.fetched_at || item.starts_at || "").slice(0, 16))),
              ui.el("h2", { class: "font-headline-sm text-headline-sm text-primary font-semibold mt-0.5" }, item.title)),
            readBadge);

          // 正文区
          const bodyEl = ui.el("div", {
            class: "p-space-md rounded-lg bg-surface-container-low/40 select-text font-sans text-body-sm text-primary leading-relaxed",
          });
          bodyEl.innerHTML = renderMiniMarkdown(item.body_md);

          // 底部链接与操作
          const bottomBar = ui.el("div", { class: "flex items-center justify-between pt-space-xs" });
          const safeLink = sanitizeHttpsUrl(item.link_url);
          if (safeLink) {
            bottomBar.append(
              ui.el("a", {
                href: safeLink,
                target: "_blank",
                rel: "noopener noreferrer",
                class: "font-label-md text-label-md text-secondary hover:underline inline-flex items-center gap-1",
              }, ui.icon("open_in_new", "text-[16px]"), item.link_text || "查看完整日志")
            );
          } else {
            bottomBar.append(ui.el("span"));
          }

          if (!item.acked) {
            const markBtn = ui.el("button", {
              class: "text-on-surface-variant hover:text-primary transition-colors font-label-sm text-label-sm px-2 py-1 min-h-[36px]",
              onclick: async () => {
                try {
                  await api.post(`/announcements/${item.id}/ack`, { ack_type: "confirm" });
                  item.acked = true;
                  readBadge.textContent = "已读";
                  readBadge.className = "font-label-sm text-label-sm text-outline px-2 py-0.5 rounded bg-surface-container";
                  markBtn.remove();
                } catch (_) {}
              },
            }, "标为已读");
            bottomBar.append(markBtn);
          }

          card.append(topBar, bodyEl, bottomBar);
          listContainer.append(card);
        }
      } catch (err) {
        listContainer.innerHTML = "";
        listContainer.append(
          ui.el("div", { class: "p-space-lg rounded-xl bg-surface-container-low text-error font-body-sm text-body-sm" },
            `加载公告列表失败: ${err.message || "未知错误"}`)
        );
      }
    }

    view.append(header, listContainer);
    loadList();
  });
})();
