# Platform Dropdown

AionUi 的 Issue Form 里 `Platform` 是必填下拉（ActionList menuitemradio）。

可选值固定 4 个：
- macOS (Apple Silicon)
- macOS (Intel)
- Windows
- Linux

脚本会从 `work_order.json` 的 `platform` 字段读取并选择对应选项；若未提供则按本机 OS 自动选择。
由于屏幕/滚动原因选项可能在上方或下方，脚本会 `scrollIntoView` 后点击。
