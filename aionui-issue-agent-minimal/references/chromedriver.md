# ChromeDriver Notes (Windows/macOS/Linux)

本 skill 默认优先：
1) 使用 `--driver-path` 指定的 chromedriver
2) 否则尝试在 PATH 里查找 `chromedriver`
3) 若检测到 Chrome/ChromeDriver 主版本不匹配，会给出警告，并尝试改用 Selenium Manager（如果环境允许下载）
4) 若用户显式指定了 `--driver-path` 且版本不匹配，会直接报错提示更新 driver

## 为什么需要匹配版本
ChromeDriver 的主版本通常需要与 Chrome 主版本一致，否则会出现 `SessionNotCreatedException`。
