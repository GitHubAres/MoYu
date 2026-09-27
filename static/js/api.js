/* API 客户端封装 */
const api = {
  async req(method, url, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const resp = await fetch("/api" + url, opts);
    if (!resp.ok) {
      let msg = resp.statusText;
      try { msg = (await resp.json()).detail || msg; } catch (e) {}
      throw new Error(msg);
    }
    if (resp.status === 204) return null;
    return resp.json();
  },
  get: (u) => api.req("GET", u),
  post: (u, b) => api.req("POST", u, b ?? {}),
  patch: (u, b) => api.req("PATCH", u, b),
  del: (u) => api.req("DELETE", u),
};
