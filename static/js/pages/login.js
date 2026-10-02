/* 墨语 MoYu - 登录与初始化页面 (login.js) */
registerPage("login", async (view) => {
  ui.setCrumb("身份认证");

  let status = { initialized: false, authenticated: false, enabled: false, is_desktop: false };
  try {
    status = await api.get("/auth/status");
  } catch (e) {
    console.error("获取认证状态失败", e);
  }

  // 如果是原生桌面版，或者未启用认证，或者已经认证过，直接跳转到书架
  if (status.is_desktop || !status.enabled || status.authenticated) {
    location.hash = "#/bookshelf";
    return;
  }

  const isFirstTime = !status.initialized;

  view.innerHTML = "";
  const container = ui.el("div", {
    class: "min-h-[75vh] flex items-center justify-center px-4 py-8"
  });

  const card = ui.el("div", {
    class: "w-full max-w-md bg-surface-container-lowest border border-border-feather rounded-2xl shadow-xl p-6 sm:p-8 flex flex-col gap-6"
  });

  // 标题与 LOGO 区域
  const header = ui.el("div", { class: "flex flex-col items-center text-center gap-2" },
    ui.el("div", { class: "w-14 h-14 rounded-2xl bg-primary text-on-primary flex items-center justify-center shadow-md mb-2" },
      ui.icon("auto_stories", "text-3xl")
    ),
    ui.el("h1", { class: "font-serif text-2xl font-bold text-on-surface" },
      isFirstTime ? "墨语 · 初始化设置" : "墨语 · 执笔人登录"
    ),
    ui.el("p", { class: "text-sm text-on-surface-variant leading-relaxed" },
      isFirstTime 
        ? "这是您首次访问云端墨语工作台，请设定管理员账号与访问密码，保障作品资产安全。" 
        : "请输入管理员账号与密码，进入墨语长篇创作书斋。"
    )
  );

  // 表单输入
  const userInput = ui.el("input", {
    type: "text",
    placeholder: isFirstTime ? "设置管理员用户名 (如 author)" : "用户名",
    value: isFirstTime ? "author" : "",
    class: "w-full px-4 py-3 rounded-xl border border-outline-variant bg-surface focus:outline-none focus:border-primary text-on-surface text-base transition-colors"
  });

  const pwdInput = ui.el("input", {
    type: "password",
    placeholder: isFirstTime ? "设置访问密码 (至少4位)" : "访问密码",
    class: "w-full px-4 py-3 rounded-xl border border-outline-variant bg-surface focus:outline-none focus:border-primary text-on-surface text-base transition-colors"
  });

  const pwdConfirmInput = isFirstTime ? ui.el("input", {
    type: "password",
    placeholder: "再次确认密码",
    class: "w-full px-4 py-3 rounded-xl border border-outline-variant bg-surface focus:outline-none focus:border-primary text-on-surface text-base transition-colors"
  }) : null;

  const errorAlert = ui.el("div", {
    class: "hidden text-sm text-error bg-error-container/40 border border-error/20 px-3 py-2 rounded-lg flex items-center gap-2"
  }, ui.icon("error", "text-base"), ui.el("span", { id: "login-error-msg" }, ""));

  function showError(msg) {
    errorAlert.classList.remove("hidden");
    const span = errorAlert.querySelector("#login-error-msg");
    if (span) span.textContent = msg;
  }

  const submitBtn = ui.el("button", {
    class: "w-full min-h-[48px] touch-target rounded-xl bg-primary hover:bg-primary-container text-on-primary font-medium text-base shadow-md transition-all flex items-center justify-center gap-2 cursor-pointer mt-2",
    onclick: async () => {
      errorAlert.classList.add("hidden");
      const u = userInput.value.trim();
      const p = pwdInput.value.trim();

      if (!u) {
        showError("请输入用户名");
        return;
      }
      if (!p || p.length < 4) {
        showError("密码长度至少为 4 位");
        return;
      }

      if (isFirstTime) {
        const pc = pwdConfirmInput.value.trim();
        if (p !== pc) {
          showError("两次输入的密码不一致，请仔细核对");
          return;
        }

        submitBtn.disabled = true;
        submitBtn.textContent = "正在完成初始化...";
        try {
          await api.post("/auth/init", { username: u, password: p });
          ui.toast("管理员账号初始化成功，欢迎进入墨语！", "ok");
          setTimeout(() => {
            location.hash = "#/bookshelf";
            location.reload();
          }, 600);
        } catch (e) {
          showError(e.message || "初始化失败");
          submitBtn.disabled = false;
          submitBtn.textContent = "立即初始化并登录";
        }
      } else {
        submitBtn.disabled = true;
        submitBtn.textContent = "正在验证登录...";
        try {
          await api.post("/auth/login", { username: u, password: p });
          ui.toast("登录成功！", "ok");
          setTimeout(() => {
            location.hash = "#/bookshelf";
            location.reload();
          }, 500);
        } catch (e) {
          showError(e.message || "用户名或密码错误");
          submitBtn.disabled = false;
          submitBtn.textContent = "登 录";
        }
      }
    }
  }, isFirstTime ? "立即初始化并登录" : "登 录");

  [userInput, pwdInput, pwdConfirmInput].filter(Boolean).forEach(inp => {
    inp.addEventListener("keydown", (e) => {
      if (e.key === "Enter") submitBtn.click();
    });
  });

  const form = ui.el("div", { class: "flex flex-col gap-4" },
    userInput,
    pwdInput,
    pwdConfirmInput,
    errorAlert,
    submitBtn
  );

  const footer = ui.el("div", { class: "text-center text-xs text-on-surface-variant/70 border-t border-border-feather pt-4" },
    "墨语 MoYu · 隐私安全的私有小说创作工作台"
  );

  card.append(header, form, footer);
  container.append(card);
  view.append(container);
});