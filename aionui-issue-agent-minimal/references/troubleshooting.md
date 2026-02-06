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
