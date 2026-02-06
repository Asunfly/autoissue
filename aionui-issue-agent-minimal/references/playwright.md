# Playwright Notes (Windows/macOS/Linux)

本 skill 默认策略：
1) 使用 Playwright 自带的 Chromium（通过 `python -m playwright install chromium` 安装/更新）
2) 若需要使用系统已安装的浏览器，可用 `--browser-binary` 指定可执行路径
3) 若已准备好浏览器缓存，可设置 `SKIP_PLAYWRIGHT_INSTALL=1` 跳过下载

## 为什么推荐 Playwright
- 无需手动维护 driver 版本，跨平台一致性更好
- Playwright 内置浏览器管理，减少依赖碎片
