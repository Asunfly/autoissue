---
name: github-issue-autosubmit-aionui
description: 自动把用户整理好的 Issue 内容提交到固定仓库 iOfficeAI/AionUi。默认用 Python + Selenium 打开 GitHub、等待用户登录、选择模板、填表、点击 Create。支持 macOS/Windows/Ubuntu；通过 work_order.json 传入变量；也可选择 Chrome DevTools MCP 流程（不依赖本脚本）。
---

# GitHub Issue AutoSubmit (AionUi Minimal, v20)

## 适用场景
- 你已经准备好结构化的 Issue 内容（对应 `assets/templates/*.yml` 的字段 `id`）
- 你想把这些内容自动填写到 GitHub Issue Form 并提交到固定仓库 `iOfficeAI/AionUi`
- 可被对话式 Agent 调用，也可脱离 Agent **直接手动运行**

## 能力边界（重要）
- ✅ 支持：Bug / Feature（Issue Forms 模板驱动回填），手动登录等待，失败截图/HTML/日志落盘
- ✅ 支持：`--no-submit`（仅填表不点击 Create）、`--headless`、`--force`（忽略去重保护）
- ✅ 支持：Bug 的 `platform` 自动推断（`"platform":"auto"`/缺省时写回为模板可选值）
- ❌ 不支持（最简分支）：自动上传附件（需要上传请改用 MCP 或手动上传）

## 输入（work_order.json）
- Schema：见 `references/work_order_schema.md`
- 示例：
  - Bug：`assets/examples/work_order_bug_example.json`
  - Feature：`assets/examples/work_order_feature_example.json`

## 运行
参考 `README.md`（入口脚本、产物路径、常见问题）。

## 文件结构（你在仓库里能看到的）
- `run_windows.cmd` / `run_macos_linux.sh`：跨平台入口（创建 venv、安装依赖、调用 Python）
- `scripts/python/submit_aionui_issue.py`：核心提交脚本（读取模板、校验、打开 GitHub、回填、提交）
- `assets/templates/*.yml`：GitHub Issue Forms 模板（字段 id/必填/options 的事实来源）
- `assets/examples/*.json`：work_order 示例
- `references/*.md`：平台/driver/排障说明

## 与 Agent Prompt 的关系（重要）
- **Skill 不会读取/依赖 `AGENT_PROMPT.md`**；Skill 的输入只有 `work_order.json` + CLI 参数。
- `AGENT_PROMPT.md` 仅用于“对话层”的内容抽取与决策（何时生成/何时提交），属于可编辑的上层策略文件；Skill 可以被替换成任意实现，只要保持 `work_order.json` 协议与 CLI 行为一致。

## 入口脚本（跨平台）
- Windows：`run_windows.cmd [work_order.json 路径] [python 参数...]`
- macOS/Linux：`bash run_macos_linux.sh [work_order.json 路径] [python 参数...]`

入口脚本会把额外参数透传给 `scripts/python/submit_aionui_issue.py`。

## 常用参数（透传给 Python）
- `--no-submit`：仅填表，不点击 Create（调试推荐）
- `--headless`：无界面模式（服务器/CI）
- `--user-data-dir <dir>`：复用 GitHub 登录态（强烈建议）
- `--profile-dir <name>`：指定 user-data-dir 内的 profile
- `--driver-path <path>`：指定 chromedriver（网络受限时推荐）
- `--login-wait-sec <sec>`：等待手动登录的最长时间
- `--timeout-sec <sec>`：元素等待超时
- `--pause-before-submit-sec <sec>`：填表后暂停检查再提交
- `--force`：忽略 `issue_number/issue_url` 的去重保护，强制再次提交

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
- 字段填写采用 best-effort，不会为单个字段长时间等待。
- 点击 Create 后若仍停留在创建页面（可能校验失败），最多重试 3 次。
- 每次失败会在 `artifacts/` 记录截图与 HTML，之后关闭浏览器并退出。


## YAML 驱动回填

- 模板文件位于 `assets/templates/`。
- 推荐 work_order.json 使用模板 field `id` 作为键。


## Driver 获取策略（默认允许网络兜底）

- 默认不要求用户预装 driver：若未提供 `--driver-path`，Selenium Manager 可能会自动下载（需要网络）。
- 若用户环境网络受限，请改为安装本地 chromedriver 并通过 `--driver-path` 指定。


## 防止重复提交死循环

- `work_order.json` 增加字段：`issue_number`、`issue_url`（默认空）。
- 脚本提交成功后会回写这两个字段；如果 `issue_number/issue_url` 已存在且未指定 `--force`，脚本将直接退出，避免重复创建。


## 产物位置

- `work_order.json`：由 agent 生成，放在你的工作目录（你能看到/回顾）。
- `artifacts/`：脚本运行产物，默认与 work_order.json 同目录（包含截图、HTML、校验报告等）。
- `.venv`：在 skill 目录内创建（隔离依赖）。
- `chrome_user_data`：默认存放在用户配置目录（复用登录态，避免反复登录）。


- 日志：`artifacts/run.log`（脚本会把 stdout/stderr tee 到该文件，便于 runner 不显示输出时排查）。

- 入口状态文件：Windows 写 `artifacts/cmd_status.txt`；macOS/Linux 写 `artifacts/sh_status.txt`。
