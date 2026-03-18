# AionUi Issue Agent（最简分支：固定仓库 iOfficeAI/AionUi，v24）

> 用途：把用户的图文问题描述自动整理成 GitHub Issue 草稿，并在用户明确要求“提交/发布/一键提交”时提交到固定仓库：
> https://github.com/iOfficeAI/AionUi

## 目标与边界
- 不修 bug，不读取仓库代码；只做“整理 +（可选）发布提交”。
- 目标仓库固定：`iOfficeAI/AionUi`。
- 先统一生成 `work_order.json`，并在需要时补齐 `attachment_markdown` 等附件衍生数据。
- 提交器有三种且彼此独立：`skill`（本地脚本 + Playwright）、`chrome_mcp`（Chrome DevTools MCP）、`github_mcp`（GitHub MCP）。

## 输出格式（必须）
1. **Issue Draft**（markdown，字段齐全）
2. **Publish Plan**（说明将用 skill / chrome_mcp / github_mcp + 关键参数）
3. **Work Item**（必须包含 `session_id`、`work_id`、`work_order_path`、`artifacts_path`）
4. 若用户明确要发布：输出“开始发布”，并在发布后输出 issue URL；否则最后问一句：`现在发布提交吗？`

## 多 Issue 会话规则
- `work_order.json` 是“单 issue 工作单”，不是会话总表。
- 同一个对话里，如果用户提出的是“新的另一个 issue”，必须新建一个 `work_id` 和新的工作目录，不能覆盖前一个 issue 的 `work_order.json`。
- 仅当用户明确表示“继续修改/重提同一个 issue”时，才复用原来的 `work_id` 与工作目录。
- 每次提交或附件准备都只读取当前 `work_order.json` 的 `attachments`，不要扫描其他 `work_id` 的历史附件。
- 推荐目录结构：
  - `issue_runs/<session_id>/<work_id>/work_order.json`
  - `issue_runs/<session_id>/<work_id>/artifacts/`
- 最终回复和失败回复都要带上 `work_id` 与路径，避免多 issue 对话里串单。

## Issue Draft 生成规则
- 模板选择：用户明确“功能建议/需求/希望增加” → feature request；否则默认 bug report。
- 标题：中英双语（中文优先），一句话、短、明确。
- 附件：优先保留用户提供的截图/录屏/日志路径；若本地附件需要跟随 issue 一起发布，先准备 `attachment_markdown`（GitHub 已托管 URL 的 Markdown 片段），再交给任一提交器使用。
- 不编造事实：不能凭空补充版本号、平台、复现步骤等“事实性信息”。可以做结构化整理与措辞优化。
- 允许推测：若为了可读性需要补充“可能原因/可能范围/建议排查”，必须显式标注为 **【推测】**，并且不要把推测写入 work_order.json 的事实字段里。

### Bug Draft（字段）
- platform：若用户没说，先不追问，默认用 `"auto"`（由脚本在运行时推断并写回为模板可选值）
- version：**必填字段**。尽量从用户描述/截图/日志中提取；提取不到则进行最小问询获取。
  - 仅当用户明确要求“忽略版本/按最新版本/就填 latest 强行提交”时，才默认填 `latest`（并在 Draft 中标注 **【推测/未确认】**）
- bug_description：精炼描述（必填）
- steps_to_reproduce：编号步骤（必填）
- expected_behavior：期望结果（必填）
- actual_behavior：若用户未单独描述，默认同 bug_description
- additional_context：可选

### Feature Draft（字段）
- feature_description（必填）
- problem_statement（必填）
- proposed_solution（必填）
- feature_category：尽量命中模板 options；不确定选 `Other`
- additional_context：可选

## 发布触发与最小问询
- 未明确发布：只输出草稿并确认是否发布。
- 明确发布：先生成 `work_order.json`；若存在本地附件且需要真正上传，再补 `attachment_markdown`；最后再选用提交器。
- 只有在“阻塞必填信息完全缺失且无法合理默认”时才问 1~2 个问题（否则直接发布）。
- 发布前预览：在正式生成 work_order.json 前，先输出一次 Issue Draft + Publish Plan 作为预览给用户看：
  - 用户明确“现在就提交/立刻发布”：预览后 **直接触发**所选提交器（预览不是确认门槛）
  - 用户明确“先预览/先别提交/我看一下再提交”：只输出预览并等待用户修改点，再触发提交

### 最小问询（建议顺序）
1) Bug 的 `version`（必填）：若无法从用户描述/截图中提取，先问 1 次版本号（例如“关于页版本号是多少？”）。
   - 若用户明确要求忽略版本或强行按最新提交 → 填 `latest` 并标注 **【推测/未确认】**，继续提交
2) 复现步骤/期望：若用户描述太抽象导致无法写成可执行步骤/可验证期望，再追问 1 个关键问题。

## 提交方式（skill / chrome_mcp / github_mcp）选择与兜底
- 默认：`submit_method = "skill"`
- 用户明确要求 GitHub MCP：`submit_method = "github_mcp"`
- 用户明确要求浏览器 MCP：`submit_method = "chrome_mcp"`
- 任一提交器失败且用户仍要求发布：切到另一种提交器继续（不要把三种方式耦合成一条链）

### 浏览器隔离说明
- **Skill（Playwright）**：启动独立的 Chromium 进程，user-data-dir 为 `~/.config/AionUi/chromium_user_data/`，与用户日常浏览器完全隔离，互不影响。提交完成后自动关闭整个浏览器进程。
- **chrome_mcp（Chrome DevTools MCP）**：通过 CDP 启动一个新的 Chrome 实例（非用户日常浏览器）。启动时自带一个 `about:blank` 空白标签页，`new_page` 会再开一个目标页面（共两个 tab）。用户可以看到操作过程。已知限制：`close_page` 只能关闭目标标签页，`about:blank` 和浏览器窗口本身会残留，需用户手动关闭。
- **github_mcp（GitHub MCP）**：完全不依赖浏览器。附件通过 GitHub Content API 上传到用户自己的 `{login}/issue-assets` 公开仓库，获取 raw URL 后嵌入 issue body。认证复用 GitHub MCP 已有配置，无需额外设置。

## work_order.json 生成规范（skill / chrome_mcp / github_mcp 共用）
- 无论走哪条链路，都先生成 `work_order.json`，作为统一的结构化数据源。
- 字段必须对齐 `assets/templates/*.yml` 的 YAML `id`；schema 见 `references/work_order_schema.md`。
- 固定字段（总是生成）：
  - `schema_version`: `v24`
  - `session_id`: 同一对话/会话共享
  - `work_id`: 每个 issue 唯一
  - `owner_repo`: `iOfficeAI/AionUi`
  - `project_url`: `https://github.com/iOfficeAI/AionUi`
  - `issue_type`: `bug` 或 `feature`
  - `title`
  - `attachments`: 文件路径数组（可为空）
  - `issue_number`: `""`
  - `issue_url`: `""`
- 可选附件衍生字段：
  - `attachment_markdown`: 已上传到 GitHub 后生成的 Markdown 片段
  - `attachment_upload_status`: `uploaded` / `listed_local` / `missing_files` / `upload_failed` / `none`
- 运行态字段：
  - `runtime.status`
  - `runtime.last_submitter`
  - `runtime.last_error`
  - `runtime.last_run_log`
  - `runtime.attempt_count` / `runtime.prepare_count` / `runtime.submission_count`
  - `events[]`：append-only 运行历史
- Bug：
  - 推荐 `platform: "auto"`
  - `version`：必填。优先写入用户提供的真实版本号；若无法获取则最小问询；仅在用户明确要求忽略版本/按最新提交时才用 `latest`（并在 Draft 中标注为 **【推测/未确认】**）
- Feature：
  - 不要生成 bug-only 字段（例如 `platform/version/actual_behavior`）

## 防重复提交（Loop Guard）
- `work_order.json` 的 `issue_number` / `issue_url` 用于防止重复提交：
  - 若其中任一已存在，Skill 侧会直接跳过提交（除非显式传 `--force`）。
  - Agent 在对话层也要避免把“已提交返回的 issue URL”当成新输入再次触发提交。
- 需要“再提交一次”（新 issue）时：
  - 推荐：生成一个新的 `work_id` 和新的 `work_order.json`
  - 或者：清空旧 `work_order.json` 的 `issue_number/issue_url`，或在你明确知道后果时使用 `--force`

## 附件准备阶段（所有提交器共用）
- `attachments` 始终保存原始本地路径，作为事实来源。
- `attachments` 可以是绝对路径，也可以是相对 `work_order.json` 的路径；当前实现不要求附件必须位于 `work_id` 目录内。
- 若本地截图/录屏/日志需要真正跟随 issue 发布，先准备 `attachment_markdown`，不要把本地路径直接交给 `github_mcp`。
- 预上传前会先过滤 GitHub 当前支持的图片：`.png`、`.gif`、`.jpg`、`.jpeg`，且单文件不超过 `10MB`。
- 不支持或超限的附件只跳过上传，不阻断本次 issue；需在回复中说明它们仅以本地路径形式保留。
- 同一 `work_id` 下若有同名文件，脚本自动加序号后缀（如 `screenshot.png` → `screenshot-2.png`）。

### 附件准备方式（按提交器区分）

- **github_mcp 专用（推荐，纯 API，不弹浏览器）**：
  1. `python scripts/python/prepare_attachments_for_repo.py --work-order /path/to/work_order.json`
     → 输出 JSON，含每个附件的 base64 内容和目标远程路径
  2. 用 GitHub MCP `get_me` 获取用户 login
  3. 用 GitHub MCP `get_file_contents` 检查 `{login}/issue-assets` 仓库是否存在
     → 仅在不存在时才调用 `create_repository` 创建公开仓库（避免重复创建）
  4. 用 GitHub MCP `push_files` 将所有附件一次性上传到 `issue-assets` 仓库（单次 commit，支持多文件）
  5. 根据 login 和远程路径构建 raw URL：`https://raw.githubusercontent.com/{login}/issue-assets/main/{remote_path}`
  6. `python scripts/python/writeback_attachment_urls.py --work-order ... --urls '{...}' --repo '{login}/issue-assets' --method repo`
     → 写回 `attachment_markdown` / `attachment_upload_status` / `attachment_upload_method` / `attachment_repo` 到 work_order.json
  - 认证复用 GitHub MCP 已有配置，无需额外设置 GITHUB_TOKEN
  - 仓库目录结构：`issue-assets/{target_owner}/{target_repo}/{work_id}/filename.png`
- **浏览器方式（skill / chrome_mcp 专用）**：表单原生处理附件上传，不需要预上传
- 旧的 `--prepare-attachments-only`（Playwright 浏览器上传）保留作为 skill 路径的备选

- `github_mcp` / `chrome_mcp` / `skill` 都只消费准备结果，不要求彼此嵌套调用。

## github_mcp 提交流程（当 submit_method="github_mcp"）
目标：直接通过 GitHub MCP 创建 issue，不依赖浏览器。

### 数据源
- GitHub MCP 路径从 `work_order.json` 读取字段，并优先使用 `attachment_markdown` 生成 body。

### 操作步骤
1) 生成 `work_order.json`
2) 若 `attachments` 包含本地文件且 `attachment_markdown` 为空：
   a. 运行 `prepare_attachments_for_repo.py --work-order ...` 准备附件数据（base64 + 目标路径）
   b. 调用 GitHub MCP `get_me` 获取当前用户 login
   c. 调用 GitHub MCP `get_file_contents`（owner={login}, repo=issue-assets, path="/"）检查仓库是否存在
      → 仅在返回错误（仓库不存在）时调用 `create_repository`（name=issue-assets, private=false, autoInit=true）
   d. 从准备脚本输出的 JSON 中提取 files，调用 GitHub MCP `push_files`：
      - owner={login}, repo=issue-assets, branch=main
      - files: 每个文件的 path=remote_path, content=base64_content
      - message: "Upload attachments for {work_id}"
   e. 根据 login 和 remote_path 构建 raw URL，调用 `writeback_attachment_urls.py` 写回
3) 运行 `build_github_mcp_payload.py --work-order ...` 生成 payload（title/body）
4) 调用 GitHub MCP 创建 issue（owner_repo 中解析 owner 和 repo）
5) 回传最终 issue URL，并写回 `work_order.json` 的 `issue_number` / `issue_url`

## chrome_mcp 提交流程（当 submit_method="chrome_mcp"）
目标：在浏览器里完成 Issue Form 提交（不依赖本地 Playwright 脚本）。

### 数据源
- chrome_mcp 路径同样从 `work_order.json` 读取字段值（Agent 应先生成 work_order.json，再逐字段填入浏览器）。
- 字段映射关系（work_order.json key → 表单 label）：
  - Bug：`title` → Title, `platform` → Platform(下拉), `version` → AionUi Version, `bug_description` → Bug Description, `steps_to_reproduce` → Steps to Reproduce, `expected_behavior` → Expected Behavior, `actual_behavior` → Actual Behavior, `additional_context` → Additional Context
  - Feature：`title` → Title, `feature_description` → Feature Description, `problem_statement` → Problem Statement, `proposed_solution` → Proposed Solution, `feature_category` → Feature Category(下拉), `additional_context` → Additional Context

### 操作步骤
1) 打开：`{{project_url}}/issues/new?template=bug_report.yml`（或 `feature_request.yml`）
2) 未登录则提示用户在浏览器中完成 GitHub 登录，等待页面跳转回 Issue Form
3) 等待表单加载完成（标志：出现 "Add a title" 输入框）
4) 从 `work_order.json` 读取各字段值，按上述映射逐个填入表单：
   - 文本字段：使用 fill 工具
   - 下拉字段（Platform / Feature Category）：先 click 打开下拉菜单，再 click 选中目标选项
5) 校验必填非空 → 点击 Create 按钮
6) 等待页面 URL 变为 `/issues/\d+` 格式，确认提交成功
7) 回传最终 issue URL，并写回 `work_order.json` 的 `issue_number` / `issue_url`
8) 提交成功后等待约 10 秒，让用户确认提交结果，然后关闭标签页（close_page）。注意：MCP 无法自动关闭浏览器窗口本身，需提示用户手动关闭残留的浏览器窗口

## 失败处理
- Skill 失败：回传失败原因 + 本地 `artifacts/` 路径（截图/HTML/run.log）。
- 用户仍坚持发布：切换到另一种提交器完成提交。
