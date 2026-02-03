# ChromeDriver Notes (Windows/macOS/Linux)

本 skill 默认策略：
1) 若指定 `--driver-path`，则使用该 chromedriver
2) 否则交给 Selenium Manager 自动选择/获取 driver（可能会下载，需要网络）

## 为什么需要匹配版本
ChromeDriver 的主版本通常需要与 Chrome 主版本一致，否则会出现 `SessionNotCreatedException`。
