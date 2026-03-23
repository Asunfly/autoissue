# aionui-issue-agent-minimal

这个目录现在按提交方式拆分：
- `skill`：本地 Playwright 自动提交
- `chrome_mcp`：浏览器 MCP 填表
- `github_mcp`：GitHub MCP 创建 issue，附件单独上传

当前文档对应 `schema v24`；`2026-03-23` 这次更新只增强了 `skill` 提交确认与重试恢复逻辑，没有变更 `work_order.json` 结构。

## 你最常跑的只有 skill

### Windows
- `run_windows.cmd "D:\\path\\to\\work_order.json" --no-submit`

### macOS / Linux
- `bash run_macos_linux.sh /path/to/work_order.json --no-submit`

## skill 实际链路
- `run_windows.cmd` / `run_macos_linux.sh`
- `scripts/python/skill_bootstrap.py`
- `scripts/python/skill_submit_aionui_issue.py`

## 其他两条独立链路
- `chrome_mcp`
  - `scripts/python/chrome_mcp_build_bundle.py --work-order /path/to/work_order.json`
- `github_mcp`
  - 有本地图片附件时先执行：
    - `scripts/python/github_mcp_upload_attachments.py --work-order /path/to/work_order.json --login <github_login>`
  - 再执行：
    - `scripts/python/github_mcp_build_payload.py --work-order /path/to/work_order.json`

## work_order.json
- 必须与 `assets/templates/*.yml` 的字段 id 对齐
- 示例在 `assets/examples/`
- schema 在 `references/work_order_schema.md`
- `skill` 路径仍保留重复提交保护：如果 `issue_number` 或 `issue_url` 已存在，会直接跳过，除非显式传 `--force`
- 附件应优先显式写入 `attachments`；如果当前 `work_id` 工作目录里还有未列出的图片文件，脚本会在进入提交器前自动补回 `attachments`，但会排除 `artifacts/.venv/chromium_user_data` 等内部目录

## skill 提交恢复
- 点击 Create 后，`skill` 会同时检查 URL、页面 canonical/og URL、页面标题或标题区里的 `Issue #<number>` 信号，而不是只盯 URL。
- 若重定向较慢，脚本会先静默等待 15-45 秒（受 `--timeout-sec` 约束），再对仓库最近创建的 issue 做一次按标题精确匹配的幂等性探测。
- 只有这些信号都失败时才会真正进入下一次重试，用来规避“GitHub 已创建 issue，但本地误判失败”的假性超时。

## 产物
- `work_order.json`
- `artifacts/`
- `.venv/`
- `chromium_user_data/`

## 参考
- 三种方式的统筹规则：`AGENT_PROMPT.md`
- skill 说明：`SKILL.md`
