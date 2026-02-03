# aionui-issue-agent-minimal (v19)

最简分支：固定只提交到 GitHub 项目 `iOfficeAI/AionUi`（Bug / Feature）。底层使用 **Browser-use** 驱动浏览器。

---

## 快速开始

### Windows
- 仅运行：`run_windows.cmd`

### macOS / Linux
- 运行：`bash run_macos_linux.sh`

> 首次运行会自动创建虚拟环境并安装依赖，并拉起 Chrome（需你手动登录 GitHub 一次），随后自动回填并提交。
> 默认会自动安装 Playwright 浏览器（可通过环境变量 `SKIP_PLAYWRIGHT_INSTALL=1` 跳过）。

### 运行前准备（Browser-use / LLM）
- 需要配置可用的 LLM 访问凭据（以下任一即可）：
  - `OPENAI_API_KEY`
  - `BROWSER_USE_API_KEY`
  - Azure OpenAI 相关变量（`AZURE_OPENAI_API_KEY`/`AZURE_OPENAI_ENDPOINT`）
- 若你想指定模型，可在命令行传 `--llm-model`（例如 `openai_gpt_4o_mini`）。

---

## 运行产物与路径说明（非常重要）

下面路径以“默认行为”为准；如果你传了自定义参数（例如 `--work-order` 或 `--user-data-dir`），对应路径会变化。

### 1) 你需要准备的文件（用户可见）
- **work_order.json**（你自己放在“工作目录”里）
  - 推荐：在你准备提 issue 的任意工作目录中创建，例如：
    - `D:\my-issues\work_order.json`
  - 运行脚本时会读取这个文件，并在提交成功后回写：
    - `issue_number`（例如 `"626"`）
    - `issue_url`（例如 `"https://github.com/iOfficeAI/AionUi/issues/626"`）

> work_order.json 的字段名必须与 `assets/templates/*.yml` 中的 YAML `id` 对齐；可参考 `assets/examples/` 里的示例。

### 2) 运行过程中生成的产物（用户可见，建议保留用于排查）
- **artifacts/**（默认与 work_order.json 同目录）
  - 默认路径：`<work_order.json 所在目录>/artifacts/`
  - 内容示例：
    - `work_order_validation_report.json`：执行前必填校验报告（缺字段会生成）
    - `cmd_status.txt`：Windows 入口脚本写入的退出码与路径（用于 runner 不回显时确认是否执行）
    - `sh_status.txt`：macOS/Linux 入口脚本写入的退出码与路径（同上）
    - `missing_required_*.png/.html`：表单必填缺失时的截图/页面
    - `agent_history.json`：Browser-use Agent 行为历史（用于排查）
    - `agent_conversation.json`：Agent 对话记录
    - `agent_context.json`：最终提示词/技能与字段清单
    - `run.log`（如有）：脚本运行日志

**可清理吗？**
- 可以清理（不影响下次运行），但**遇到失败请先保留 artifacts**，方便你或别人排查。

### 3) 虚拟环境（可共享代码，但虚拟环境不建议共享）
- **.venv**（位于 skill 目录内，用于隔离依赖）
  - Windows：`<skill_dir>\.venv\`
  - macOS/Linux：`<skill_dir>/.venv/`

**可清理吗？**
- 可以。删除后下次运行会重新创建并安装依赖（会花点时间）。
- 不建议把 `.venv` 打包分享给别人（体积大且和平台/路径强相关）。

### 4) 浏览器用户数据（用于复用登录态，不影响你日常 Chrome）
为避免每次都要求重新登录 GitHub，脚本默认使用“自动化专用”的 Chrome Profile（与日常 Chrome Profile 分离）。

- Windows（默认）：`%LOCALAPPDATA%\AionUi\chrome_user_data\`
- macOS/Linux（默认）：`$XDG_CONFIG_HOME/AionUi/chrome_user_data/`（一般是 `~/.config/AionUi/chrome_user_data/`）

**可清理吗？**
- 可以。删除后会丢失 GitHub 登录态（下次需要重新登录）。
- 如果遇到 profile “被占用/损坏”，清理它通常能解决。

---

## 哪些文件适合分享（可共享文件 / 不可共享文件）

### 可共享（建议打包时保留）
- `AGENT_PROMPT.md`（Agent 提示词）
- `COMMON_SKILL.md`（通用 skill）
- `SKILL.md`（Skill 说明）
- `assets/templates/*.yml`（Issue Forms 模板）
- `assets/examples/*.json`（work_order 示例）
- `scripts/python/*.py`（脚本代码）
- `run_windows.cmd` / `run_macos_linux.sh`（运行入口）
- `references/*`（字段/结构说明）

### 不建议共享（个人/环境相关）
- `.venv/`（依赖环境，平台相关，体积大）
- `chrome_user_data/`（可能包含你的登录态）
- `work_order.json`（包含你要提交的问题细节）
- `artifacts/`（包含日志、Agent 历史、页面内容）

---

## AgentPrompt / Skill 使用方式（CLI）

本项目用于在 Codex/Claude Code 等 CLI 环境运行：  
- `AGENT_PROMPT.md` 作为 **输入提示词**（入口指令）。  
- `COMMON_SKILL.md` 作为 **通用 skill**（被提示词调用的操作能力）。  
- 运行脚本会把它们写入 `artifacts/agent_context.json` 方便回溯与审计。

## 常见问题（FAQ）

### Q1：为什么不会影响我平时用的 Chrome？
因为脚本启动浏览器时指定了独立的 `--user-data-dir`，它使用的是一个“自动化专用 profile”，不会读取/修改你日常 Chrome 的默认 profile。

### Q2：我想换一个 GitHub 账号怎么办？
清理 `chrome_user_data/`（或改用新的 `--user-data-dir`），然后重新运行登录即可。
