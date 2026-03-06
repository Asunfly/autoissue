# work_order.json schema (v23)

v23 uses YAML-driven fill based on GitHub Issue Forms templates under `assets/templates/`.

## Core rule for multi-issue sessions
- `work_order.json` is now defined as **one issue = one work order**.
- In the same chat/session, every new issue must use a new `work_id` and a new workspace directory.
- Never overwrite a previously submitted issue's `work_order.json` when the user is actually creating a new issue.
- Only reuse an existing `work_order.json` when the user is clearly updating/retrying the same issue.

## Recommended workspace layout
- `issue_runs/<session_id>/<work_id>/work_order.json`
- `issue_runs/<session_id>/<work_id>/artifacts/`

Example:
- `issue_runs/chat-20260306-01/wo-20260306T111530-a1b2c3/work_order.json`

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

## Attachment preparation
- attachments: string[] (local file paths; may be absolute or relative to work_order.json)
- Only the current work order's `attachments` are consumed during prepare/submit; other `work_id` histories must be ignored.
- attachment_markdown: string (optional; content generated after uploading attachments to GitHub, may be Markdown or GitHub-returned HTML `<img ...>` snippet)
- attachment_upload_status: string (optional; `uploaded` / `listed_local` / `missing_files` / `upload_failed` / `none`)
- Upload filter: `.png` / `.gif` / `.jpg` / `.jpeg`, max `10MB` per file
- Unsupported or oversized files are skipped before upload and should be recorded in `events[].extra.skipped_attachments`

## Multi-issue identity fields
- schema_version: string (`v23`)
- session_id: string (same chat/session can share this)
- work_id: string (unique per issue work item)

## Runtime state
- runtime.workspace_dir: string
- runtime.artifacts_dir: string
- runtime.status: string
- runtime.last_submitter: string (`skill` / `chrome_mcp` / `github_mcp`)
- runtime.last_error: string
- runtime.last_error_at: string (ISO8601)
- runtime.last_run_log: string
- runtime.last_payload_path: string
- runtime.attempt_count: integer
- runtime.prepare_count: integer
- runtime.submission_count: integer
- runtime.updated_at: string (ISO8601)

## Event history
- events: array
- Each event is append-only and should include:
  - timestamp
  - stage (`bootstrap` / `prepare_attachments` / `payload_build` / `submit` / `validation` / ...)
  - status (`started` / `succeeded` / `failed` / `retry` / `skipped_duplicate` / ...)
  - submitter
  - message
  - error
  - issue_url
  - issue_number
  - artifacts_dir
  - extra (optional object)

## Bug platform auto-detect (optional)
- Bug 的 `platform` 字段可设置为 `"auto"` / `"detect"` 或留空，脚本会按当前运行系统推断并写回为模板可选值（例如 `macOS (Apple Silicon)`）。
