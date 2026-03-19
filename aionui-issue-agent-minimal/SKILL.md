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
