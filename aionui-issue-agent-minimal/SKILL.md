---
name: github-issue-autosubmit-aionui
description: 自动把用户整理好的 Issue 内容提交到固定仓库 iOfficeAI/AionUi。默认用 Python + Selenium 打开 GitHub、等待用户登录、选择模板、填表、可选上传附件、点击 Create。支持 macOS/Windows/Ubuntu；通过 work_order.json 传入变量；也可选择 Chrome DevTools MCP 流程（不依赖本脚本）。
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
- 默认：有界面模式，脚本会停在登录态判断处，等待用户手动登录。
- 建议：加 `--user-data-dir` 复用登录态，减少反复登录。

## 注意
- GitHub 页面 class 经常变化，脚本尽量使用 `aria-label`/`data-testid`/可见文本定位。
- 如页面结构变化，优先用 MCP 方式实时抓取元素 uid 来适配。


## 稳定运行建议（强制 venv 隔离）

- macOS/Linux：优先执行 `run_macos_linux.sh`（会在 skill 目录创建 `.venv` 并安装依赖）
- Windows：优先执行 `run_windows.cmd`（会在 skill 目录创建 `.venv` 并安装依赖）


## Platform 必填字段支持

- 若 GitHub Issue Forms 存在必填 `Platform` 下拉，脚本将自动选择当前系统对应的选项。
- 也可在 `work_order.json` 增加 `platform` 明确指定（例如 `Windows` / `Linux` / `macOS (Apple Silicon)` / `macOS (Intel)`）。


## 不阻塞填写 & 失败重试

- v5：字段填写采用 best-effort，不会为单个字段长时间等待。
- 点击 Create 后若仍停留在创建页面（可能校验失败），最多重试 3 次。
- 每次失败会在 `artifacts/` 记录截图与 HTML，之后关闭浏览器并退出。



## 提交方式与对话控制

- 默认：skill（本地脚本 + Selenium）。
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


## Driver 获取策略（默认允许网络兜底）

- 默认不要求用户预装 driver：若未提供 `--driver-path`，Selenium Manager 可能会自动下载（需要网络）。
- 若用户环境网络受限，请改为安装本地 chromedriver 并通过 `--driver-path` 指定。


## 防止重复提交死循环

- `work_order.json` 增加字段：`issue_number`、`issue_url`（默认空）。
- 脚本提交成功后会回写这两个字段；如果 `issue_number` 已存在，脚本将直接退出，避免重复创建。


## 产物位置

- `work_order.json`：由 agent 生成，放在你的工作目录（你能看到/回顾）。
- `artifacts/`：脚本运行产物，默认与 work_order.json 同目录（包含截图、HTML、校验报告等）。
- `.venv`：在 skill 目录内创建（隔离依赖）。
- `chrome_user_data`：默认存放在用户配置目录（复用登录态，避免反复登录）。


- 日志：`artifacts/run.log`（脚本会把 stdout/stderr tee 到该文件，便于 runner 不显示输出时排查）。

- 入口状态文件：Windows 写 `artifacts/cmd_status.txt`；macOS/Linux 写 `artifacts/sh_status.txt`。
