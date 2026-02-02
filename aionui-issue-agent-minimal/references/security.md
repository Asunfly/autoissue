# Security Notes

- 不要把 GitHub 密码写入脚本或 work_order.json。
- 若使用持久登录态，建议通过 `--user-data-dir` 指向一个本地目录（仅本机可访问）。
- 任何 token（若未来扩展 API）应通过环境变量传入，不要写到仓库里。
