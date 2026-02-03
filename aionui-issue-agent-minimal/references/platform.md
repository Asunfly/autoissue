# Platform Dropdown

AionUi 的 Issue Form 里 `Platform` 是必填下拉（ActionList menuitemradio）。

可选值固定 4 个：
- macOS (Apple Silicon)
- macOS (Intel)
- Windows
- Linux

脚本会从 `work_order.json` 的 `platform` 字段读取并选择对应选项（仅 Bug 模板）。
若 `platform` 缺省/空字符串，或显式写为 `"auto"`/`"detect"`，则按本机 OS/CPU 自动选择并写回 `work_order.json`。
由于屏幕/滚动原因选项可能在上方或下方，脚本会 `scrollIntoView` 后点击。
