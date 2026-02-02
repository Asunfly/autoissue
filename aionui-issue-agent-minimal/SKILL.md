---
name: github-issue-autosubmit-aionui
description: 自动把用户整理好的 Issue 内容提交到固定仓库 iOfficeAI/AionUi。默认用 Python + Browser-use 打开 GitHub、等待用户登录、选择模板、填表、可选上传附件、点击 Create。支持 macOS/Windows/Ubuntu；通过 work_order.json 传入变量；也可选择 Chrome DevTools MCP 流程（不依赖本脚本）。
---

# GitHub Issue AutoSubmit (AionUi Minimal, v19)

## 适用场景
- 用户说“帮我提个 bug/提个 issue/一键提交”，目标仓库固定 `iOfficeAI/AionUi`
- 你已在对话中生成好了结构化 issue 内容（title / version / description / steps / expected / attachments）

## 输入（work_order.json）
见 `assets/example_work_order_bug.json`。

## 运行
参考 `README.md`。

## 运行策略
- 默认：有界面模式，Browser-use 会停在登录态判断处，等待用户手动登录。
- 建议：加 `--user-data-dir` 复用登录态，减少反复登录。

## 注意
- GitHub 页面 class 经常变化，Browser-use 依赖可见文本/语义定位与视觉能力。
- 如页面结构变化，优先用 MCP 方式实时抓取元素 uid 来适配。


## 稳定运行建议（强制 venv 隔离）

- macOS/Linux：优先执行 `run_macos_linux.sh`（会在 skill 目录创建 `.venv` 并安装依赖）
- Windows：优先执行 `run_windows.cmd`（会在 skill 目录创建 `.venv` 并安装依赖）


## Platform 必填字段支持

- 若 GitHub Issue Forms 存在必填 `Platform` 下拉，脚本将自动选择当前系统对应的选项。
- 也可在 `work_order.json` 增加 `platform` 明确指定（例如 `Windows` / `Linux` / `macOS (Apple Silicon)` / `macOS (Intel)`）。


## 不阻塞填写 & 失败处理

- 字段填写采用 best-effort，不会为单个字段长时间等待。
- Agent 会记录运行历史到 `artifacts/agent_history.json`，便于回溯失败原因。
- 若提交后仍停留在创建页面，请根据历史记录与页面提示手动修正。



## 提交方式与对话控制

- 默认：skill（本地脚本 + Browser-use）。
- 仅当用户明确指定 MCP，或 skill 失败且用户仍坚持发布时，才切换 MCP。

\1提交流程建议（对话层控制）

- 是否提交由 **Agent 对话意图** 决定：
  - 未明确提交：仅输出草稿并询问“现在发布提交吗？”
  - 明确提交：生成 `work_order.json`，直接运行脚本创建 issue
- `work_order.json` 不再需要 `dry_run` 字段。
- 调试时可用 `--no-submit`（仅填表不点 Create）。


## YAML 驱动回填

- 模板文件位于 `assets/templates/`。
- 推荐 work_order.json 使用模板 field `id` 作为键。


## LLM 与运行环境

- 需要配置 LLM 凭据（`OPENAI_API_KEY` 或 `BROWSER_USE_API_KEY` 或 Azure OpenAI 变量）。
- 可用 `--llm-model` 指定 Browser-use 模型名称（如 `openai_gpt_4o_mini`）。
- 默认会安装 Playwright Chromium；如需跳过可设置 `SKIP_PLAYWRIGHT_INSTALL=1`。


## 防止重复提交死循环

- `work_order.json` 增加字段：`issue_number`、`issue_url`（默认空）。
- 脚本提交成功后会回写这两个字段；如果 `issue_number` 已存在，脚本将直接退出，避免重复创建。


## 产物位置

- `work_order.json`：由 agent 生成，放在你的工作目录（你能看到/回顾）。
- `artifacts/`：脚本运行产物，默认与 work_order.json 同目录（包含 Agent 历史、上下文、校验报告等）。
- `.venv`：在 skill 目录内创建（隔离依赖）。
- `chrome_user_data`：默认存放在用户配置目录（复用登录态，避免反复登录）。


- 日志：`artifacts/run.log`（脚本会把 stdout/stderr tee 到该文件，便于 runner 不显示输出时排查）。

- 入口状态文件：Windows 写 `artifacts/cmd_status.txt`；macOS/Linux 写 `artifacts/sh_status.txt`。
