/* API 客户端封装 */
const api = {
  async req(method, url, body, customOpts = {}) {
    const opts = { method, headers: {}, ...customOpts };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const timeoutMs = opts.timeout ?? 45000;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    let resp;
    try {
      resp = await fetch("/api" + url, {
        ...opts,
        signal: opts.signal || controller.signal,
      });
    } catch (err) {
      if (err.name === "AbortError") {
        throw new Error("请求超时（超过 " + Math.round(timeoutMs / 1000) + " 秒未响应），请检查服务状态");
      }
      throw new Error("网络连接失败，请确认墨语后台服务是否正常运行");
    } finally {
      clearTimeout(timeoutId);
    }

    if (!resp.ok) {
      let msg = resp.statusText;
      try { msg = (await resp.json()).detail || msg; } catch (e) {}
      throw new Error(msg);
    }
    if (resp.status === 204 || resp.status === 205) return null;
    return resp.json();
  },
  get: (u, opts) => api.req("GET", u, undefined, opts),
  post: (u, b, opts) => api.req("POST", u, b ?? {}, opts),
  patch: (u, b, opts) => api.req("PATCH", u, b, opts),
  del: (u, opts) => api.req("DELETE", u, undefined, opts),
};
