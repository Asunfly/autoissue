# Troubleshooting

1) SessionNotCreatedException：Chrome 与 ChromeDriver 主版本不匹配  
- 安装匹配版本 driver，并 `--driver-path` 指定。

2) Can't find free port / Unable to bind  
- 环境禁止绑定本地端口（Selenium 需要）。改用 MCP 或换可运行环境。

3) 元素找不到  
- GitHub UI 变更。打开 `artifacts/*.html` 看当前 DOM，调整 selector 或改用 MCP。

4) 明明想再提一次，但脚本直接退出  
- `work_order.json` 里已有 `issue_number` 或 `issue_url`（去重保护）。清空这两个字段，或传 `--force`。
