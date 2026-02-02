# work_order.json schema (v19)

v19 uses YAML-driven fill based on GitHub Issue Forms templates under `assets/templates/`.

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
- issue_number: string (default empty). If non-empty, script skips submission.
- issue_url: string (set after success).
