# AI 联调记录

日期：2026-09-27 ｜ 服务商：Kimi（月之暗面，`https://api.moonshot.cn/v1`）｜ 模型：`kimi-k2.6`

## 实测结果

| 链路 | 结果 | 说明 |
|---|---|---|
| 测试连接 /ai/test | ✅ | 模型列表可用 |
| 续写（非流式） | ✅ | 单次约 14s，文风连贯 |
| 改写润色（SSE 流式，2 候选） | ✅ | start/delta/done 帧完整，候选顺序输出，usage 正常返回（1950 tokens） |
| 大纲生成 | ✅ | 内容质量可用 |
| 一致性检查 /audit/run | ✅（修复后） | 见下方问题 1、2 |
| Token 用量累计 | ✅ | token_used 正常累加 |

## 发现并已修复的兼容性问题

1. **模型名 404**：预设的 `kimi-k2-0905-preview` 在该账号不可用（账号仅开放 `kimi-k2.6`、`kimi-k2.7-code`），上游返回 404「接口路径不存在」。已将设置页 Kimi 预设模型改为 `kimi-k2.6`。
   - 教训：不同账号可用模型不同，/ai/test 通过 ≠ 模型可用。
2. **temperature 限制**：`kimi-k2.6` 只允许 `temperature=1`，audit 模块原先硬编码 `0.2` 导致 400「invalid temperature: only 1 is allowed for this model」。已移除该参数（所有模块默认不传 temperature，兼容性最好）。
3. **空壳问题条目**：模型在"没发现问题"时偶尔返回每章一条空壳对象（只有 chapter_title，issue 为空）而非空数组。已在解析层过滤 `issue` 为空的条目，此时前端显示"未发现明显矛盾"。

## 注意

- 并行开发期间多个测试流程会改写 app_settings 的 ai_* 配置（mock 切来切去），联调前请确认设置页配置仍为真实 Key。
- DeepSeek / 智谱 / 通义 / OpenAI 未实测；协议均为 OpenAI 兼容，风险点在各自的 SSE 细节与参数限制（如遇 400 优先排查 temperature 等可选参数）。
