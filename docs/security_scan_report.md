# MoYu 全历史敏感信息扫描报告

扫描时间: 2026-09-28T13:01:46.450129
扫描仓库: D:\KimiCode工作区\moyu
扫描模式数: 9

历史补丁行数: 16252

## url_with_creds：发现 2 处
- commit `8836168b` | `static/vendor/tailwind.js`
  ```
  +${ae([v])}`)}f.add(p);for(let v of s.get(p))for(let g of a.get(v))c.push(p),u(g,c),c.pop();m.add(p),f.delete(p),h.push(p)}}for(let p of l)u(p);for(let p of h)"nodes"in p&&O(p.nodes,c=>{if(c.kind!=="a
  ```
- commit `8836168b` | `static/vendor/tailwind.js`
  ```
  +${z}`)}}))h.get(w)?.(A);for(let w of u)w(A);if(p){let w=[];for(let[L,z]of A.theme.entries()){if(z.options&2)continue;let I=n(xe(L),z.value);I.src=z.src,w.push(I)}let K=A.theme.getKeyframes();for(let 
  ```

**结论：共计命中 2 处，均为 `static/vendor/tailwind.js` 压缩后的第三方代码中的正则误报（字符串片段形似 `https://...`），未发现真实泄露的 API Key、密码、私钥或带凭据 URL。**