# ChromeDriver Notes (已弃用)

本分支已迁移到 **Browser-use**，不再依赖 ChromeDriver。

## 新方案说明
- Browser-use 使用 Playwright/浏览器会话管理，不需要单独安装 chromedriver。
- 如需指定本地浏览器，请使用 `--browser-binary` 指向 Chrome/Chromium。
- 若网络受限导致 Playwright 安装失败，可设置 `SKIP_PLAYWRIGHT_INSTALL=1` 并提前准备可用的浏览器。
