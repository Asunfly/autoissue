# aionui-issue-agent-minimal

这个目录现在按提交方式拆分：
- `skill`：本地 Playwright 自动提交
- `chrome_mcp`：浏览器 MCP 填表
- `github_mcp`：GitHub MCP 创建 issue，附件单独上传

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

## 产物
- `work_order.json`
- `artifacts/`
- `.venv/`
- `chromium_user_data/`

## 参考
- 三种方式的统筹规则：`AGENT_PROMPT.md`
- skill 说明：`SKILL.md`
