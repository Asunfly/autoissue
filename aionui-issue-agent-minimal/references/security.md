# Security Notes

- 不要把 GitHub 密码写入脚本或 work_order.json。
- 若使用持久登录态，建议通过 `--user-data-dir` 指向一个本地目录（仅本机可访问）。
- 任何 token（若未来扩展 API）应通过环境变量传入，不要写到仓库里。
- 分享日志/截图前，请先检查 `artifacts/*.html`、`artifacts/*.png` 是否包含敏感信息（用户名、仓库信息、路径、表单内容等）。
