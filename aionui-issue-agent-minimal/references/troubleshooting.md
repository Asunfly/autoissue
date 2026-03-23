# Troubleshooting

1) Playwright 浏览器启动失败  
- 先执行 `python -m playwright install chromium`。
- 仍失败时，用 `--browser-binary` 指向系统浏览器，或改用 MCP。
 - 若不允许联网下载，可设置 `SKIP_PLAYWRIGHT_INSTALL=1` 并使用已缓存的浏览器。

2) Can't find free port / Unable to bind  
- 环境禁止绑定本地端口。改用 MCP 或换可运行环境。

3) 元素找不到  
- GitHub UI 变更。打开 `artifacts/*.html` 看当前 DOM，调整 selector 或改用 MCP。

4) 明明想再提一次，但脚本直接退出  
- `work_order.json` 里已有 `issue_number` 或 `issue_url`（去重保护）。清空这两个字段，或传 `--force`。

5) 点了 Create 后脚本报超时，但 GitHub 上其实已经有新 issue  
- `2026-03-23` 起，`skill` 会先用多信号确认（URL、canonical/og URL、页面标题里的 `Issue #<n>`）并追加最近 issue 幂等性探测，再决定是否重试。
- 如果仍出现疑似“假性超时”，先检查 `work_order.json` 是否已写回 `issue_number/issue_url`，以及 `artifacts/run.log` 中是否出现 `SUCCESS [page_title]`、`SUCCESS [github_api_recent_exact_title]` 之类的恢复日志。
- 如果页面信号和最近 issue 探测都失败，再看 `artifacts/submit_attempt_*.html` 判断是 GitHub UI 变化、网络异常，还是确实没有创建成功。
