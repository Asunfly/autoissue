---
name: github-issue-autosubmit-aionui
description: AionUi issue 提交 skill。此 skill 只负责本地 Playwright 提交器（skill 路径）；chrome_mcp 和 github_mcp 由 AGENT_PROMPT 统筹并调用各自独立脚本。
---

# AionUi Issue Skill

## 定位
- 这个 `SKILL.md` 只描述 `skill` 提交器
- `AGENT_PROMPT.md` 负责三种提交方式的统筹、选择和失败回落
- `chrome_mcp` 和 `github_mcp` 不是本 skill 的通用流程，不复用这里的运行入口

## 输入
- 统一输入：`work_order.json`
- 字段约束：见 `references/work_order_schema.md`
- `work_order.json` 一次只对应一个 issue
- 附件优先读取 `work_order.json.attachments`；若当前 `work_id` 工作目录里还有未列出的图片文件，脚本会在进入提交器前自动补回 `attachments`（排除 `artifacts/.venv/chromium_user_data` 等内部目录）

## skill 路径
- 入口：
  - Windows：`run_windows.cmd [work_order.json] [args...]`
  - macOS/Linux：`bash run_macos_linux.sh [work_order.json] [args...]`
- 实际链路：
  - `run_*` → `scripts/python/skill_bootstrap.py` → `scripts/python/skill_submit_aionui_issue.py`

## 公开参数
- `--no-submit`
- `--prepare-attachments-only`
- `--headless`
- `--user-data-dir <dir>`
- `--profile-dir <name>`
- `--browser-binary <path>`
- `--login-wait-sec <sec>`
- `--timeout-sec <sec>`
- `--pause-before-submit-sec <sec>`
- `--force`

## 保留的防护逻辑
- `skill_submit_aionui_issue.py` 仍保留 `issue_number / issue_url` 的重复提交保护
- `--force` 仍然只在你明确要重提同一个 work_order 时使用
- 附件过滤、运行态写回、事件历史回写仍保留

## 2026-03-23 提交恢复更新
- 这次更新只增强 `skill` 提交器的确认与重试逻辑，`work_order.json` 的 `schema_version` 仍是 `v24`
- 点击 Create 后不再只依赖 URL 跳转；会同时检查当前 URL、canonical/og URL、页面标题或标题区里的 `Issue #<number>` 信号
- 若 GitHub 重定向较慢，会先静默等待 15-45 秒（受 `--timeout-sec` 约束），然后再按标题去仓库最近创建的 issue 里做一次幂等性探测
- 只有页面信号和最近 issue 探测都失败时才会真正重试，尽量避免重复点击 Create 造成重复提交

## 相关但独立的脚本
- `scripts/python/chrome_mcp_build_bundle.py`
  - 只给 `chrome_mcp` 生成字段清单
- `scripts/python/github_mcp_build_payload.py`
  - 只给 `github_mcp` 生成 `title/body`
- `scripts/python/github_mcp_upload_attachments.py`
  - 只在 `github_mcp` 且存在本地图片附件时使用

## 当前目录建议
- 主入口：
  - `scripts/python/skill_bootstrap.py`
  - `scripts/python/skill_submit_aionui_issue.py`
- 公共支持：
  - `scripts/python/issue_payload_support.py`
- 模板与示例：
  - `assets/templates/*.yml`
  - `assets/examples/*.json`

## 说明
- 已删除旧的 base64 附件准备脚本，避免和 `github_mcp` 新链路混淆
- 如果需要整体流程、三种提交器矩阵或回落规则，请看 `AGENT_PROMPT.md`
