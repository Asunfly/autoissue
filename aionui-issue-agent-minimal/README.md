# aionui-issue-agent-minimal (v22)

最简分支：固定只提交到 GitHub 项目 `iOfficeAI/AionUi`（Bug / Feature）。

---

## 快速开始

### Windows
- 仅运行：`run_windows.cmd`
  - 传额外参数给 Python（调试推荐）：`run_windows.cmd "D:\\my-issues\\work_order.json" --no-submit`
  - 强制再次提交（忽略 issue_number/issue_url 去重保护）：`run_windows.cmd "D:\\my-issues\\work_order.json" --force`

### macOS / Linux
- 运行：`bash run_macos_linux.sh`
  - 传额外参数给 Python（调试推荐）：`bash run_macos_linux.sh /path/to/work_order.json --no-submit`
  - 强制再次提交（忽略 issue_number/issue_url 去重保护）：`bash run_macos_linux.sh /path/to/work_order.json --force`

> 入口脚本已简化为薄包装，实际初始化由 `scripts/python/bootstrap.py` 完成（创建 venv、安装依赖、安装浏览器）。默认是有头模式，首次运行需你手动登录 GitHub 一次；后续会复用 `chromium_user_data` 登录态（若会话过期仍需重新登录）。

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
>
> 小技巧：Bug 的 `platform` 可写 `"auto"`（或留空）让脚本在运行时按当前系统推断，并写回为模板可选值。

### 运行相关环境变量（可选）
- `SKIP_PLAYWRIGHT_INSTALL=1`：跳过 Playwright 浏览器下载（已预置浏览器缓存时使用）
- `PAUSE_BEFORE_SUBMIT_SEC=10`：填表后暂停秒数（默认 10）
- `PYTHON_BIN=python3`：仅 macOS/Linux 下可指定 Python 解释器
- `PLAYWRIGHT_INSTALL_RETRIES=3`：浏览器下载失败重试次数（默认 3）
- `PLAYWRIGHT_INSTALL_RETRY_DELAY_SEC=2`：重试基础等待秒数（指数退避）
- `PLAYWRIGHT_INSTALL_TIMEOUT_SEC=240`：单次浏览器下载超时秒数（默认 240）
- `BOOTSTRAP_UPGRADE_PIP=1`：需要时才升级 pip（默认不升级，弱网更稳）
- `PLAYWRIGHT_HOST_PLATFORM_OVERRIDE`：手动覆盖 Playwright 平台（一般不需要；macOS arm64 入口脚本会自动设置）

> 若 Playwright 浏览器下载多次失败，bootstrap 会自动尝试回退到系统已安装的 Chrome/Chromium（无需额外参数）。

### 2) 运行过程中生成的产物（用户可见，建议保留用于排查）
- **artifacts/**（默认与 work_order.json 同目录）
  - 默认路径：`<work_order.json 所在目录>/artifacts/`
  - 内容示例：
    - `work_order_validation_report.json`：执行前必填校验报告（缺字段会生成）
    - `cmd_status.txt`：Windows 入口脚本写入的退出码与路径（用于 runner 不回显时确认是否执行）
    - `sh_status.txt`：macOS/Linux 入口脚本写入的退出码与路径（同上）
    - `missing_required_*.png/.html`：表单必填缺失时的截图/页面
    - `browser_error_*.png/.html`：浏览器启动/运行异常时的截图/页面
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

### 4) 浏览器用户数据（用于复用登录态，不影响你日常浏览器）
为避免每次都要求重新登录 GitHub，脚本默认使用“自动化专用”的 Chromium Profile（与日常浏览器 Profile 分离）。

- Windows（默认）：`%LOCALAPPDATA%\AionUi\chromium_user_data\`
- macOS/Linux（默认）：`$XDG_CONFIG_HOME/AionUi/chromium_user_data/`（一般是 `~/.config/AionUi/chromium_user_data/`）

**可清理吗？**
- 可以。删除后会丢失 GitHub 登录态（下次需要重新登录）。
- 如果遇到 profile “被占用/损坏”，清理它通常能解决。

---

## 哪些文件适合分享（可共享文件 / 不可共享文件）

### 可共享（建议打包时保留）
- `AGENT_PROMPT.md`（Agent 提示词）
- `SKILL.md`（Skill 说明）
- `assets/templates/*.yml`（Issue Forms 模板）
- `assets/examples/*.json`（work_order 示例）
- `scripts/python/*.py`（脚本代码）
- `run_windows.cmd` / `run_macos_linux.sh`（运行入口）
- `references/*`（字段/结构说明）

### 不建议共享（个人/环境相关）
- `.venv/`（依赖环境，平台相关，体积大）
- `chromium_user_data/`（可能包含你的登录态）
- `work_order.json`（包含你要提交的问题细节）
- `artifacts/`（可能包含截图、日志、页面内容）

---

## 常见问题（FAQ）

### Q1：为什么不会影响我平时用的浏览器？
因为脚本启动 Chromium 时指定了独立的 `--user-data-dir`，它使用的是一个“自动化专用 profile”，不会读取/修改你日常浏览器的默认 profile。

### Q2：我想换一个 GitHub 账号怎么办？
清理 `chromium_user_data/`（或改用新的 `--user-data-dir`），然后重新运行登录即可。
