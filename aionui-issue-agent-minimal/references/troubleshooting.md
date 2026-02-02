# Troubleshooting

1) 无法启动浏览器 / Playwright 安装失败
- 检查网络或设置 `SKIP_PLAYWRIGHT_INSTALL=1` 并确保本机已有可用浏览器。
- 可用 `--browser-binary` 指定 Chrome/Chromium 路径。

2) 无法提交 / 仍停留在创建页面
- 可能是必填字段校验失败或模板变化。
- 查看 `artifacts/agent_history.json` 与浏览器页面提示，修正 work_order.json 后重试。

3) 登录无法完成
- 确认打开的是 GitHub 登录页面，完成登录后回到模板页继续。

4) 元素找不到
- GitHub UI 变更。可使用 MCP 方式抓取元素 uid 进行适配。
