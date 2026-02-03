# work_order.json schema (v20)

v20 uses YAML-driven fill based on GitHub Issue Forms templates under `assets/templates/`.

## Bug (bug_report.yml) ids
- platform (required)
- version (required)
- bug_description (required)
- steps_to_reproduce (required)
- expected_behavior (required)
- actual_behavior (required)
- additional_context (optional)

## Feature (feature_request.yml) ids
- feature_description (required)
- problem_statement (required)
- proposed_solution (required)
- feature_category (required; must match options)
- additional_context (optional)


## Loop guard
- issue_number: string (default empty). If non-empty, script skips submission (unless `--force`).
- issue_url: string (set after success). If issue_number is empty but issue_url exists, script parses issue number and skips (unless `--force`).

## Bug platform auto-detect (optional)
- Bug 的 `platform` 字段可设置为 `"auto"` / `"detect"` 或留空，脚本会按当前运行系统推断并写回为模板可选值（例如 `macOS (Apple Silicon)`）。
