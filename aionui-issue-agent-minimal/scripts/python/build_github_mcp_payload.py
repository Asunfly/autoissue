#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from issue_payload_support import (
    AIONUI_REPO,
    AIONUI_URL,
    apply_template_defaults,
    append_work_order_event,
    build_issue_body_markdown,
    build_local_attachment_markdown,
    ensure_work_order_runtime,
    filter_uploadable_attachments,
    load_issue_template,
    normalize_work_order_dict,
    resolve_attachment_paths,
    template_for_issue_type,
    update_work_order_runtime,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build payload JSON for github_mcp issue creation.")
    parser.add_argument("--work-order", required=True, help="Path to work_order.json")
    parser.add_argument("--output", help="Optional output JSON file path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    work_order_path = Path(args.work_order).expanduser().resolve()
    ensure_work_order_runtime(work_order_path)
    raw = json.loads(work_order_path.read_text(encoding="utf-8"))
    norm = normalize_work_order_dict(raw)

    assets_templates_dir = Path(__file__).resolve().parents[2] / "assets" / "templates"
    _, template_path = template_for_issue_type(norm.get("issue_type", "bug"), assets_templates_dir)
    tpl = load_issue_template(template_path)
    norm, _ = apply_template_defaults(tpl, norm)

    attachment_paths, missing_paths = resolve_attachment_paths(norm.get("attachments", []), work_order_path.parent)
    attachment_markdown = norm.get("attachment_markdown", "").strip()
    if not attachment_markdown:
        _, skipped = filter_uploadable_attachments(attachment_paths)
        attachment_markdown = build_local_attachment_markdown(attachment_paths, missing_paths, skipped)
    raw_status = str(raw.get("attachment_upload_status") or "").strip().lower()
    if raw_status in ("", "none"):
        if norm.get("attachment_markdown"):
            raw_status = "uploaded"
        elif missing_paths:
            raw_status = "missing_files"
        elif attachment_paths:
            raw_status = "listed_local"
        else:
            raw_status = "none"

    payload = {
        "owner_repo": raw.get("owner_repo") or AIONUI_REPO,
        "project_url": raw.get("project_url") or AIONUI_URL,
        "issue_type": norm.get("issue_type", "bug"),
        "title": norm.get("title", "").strip(),
        "body": build_issue_body_markdown(norm, tpl, attachment_markdown=attachment_markdown),
        "attachment_upload_status": raw_status,
    }

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    update_work_order_runtime(
        work_order_path,
        {
            "status": "payload_ready",
            "last_submitter": "github_mcp",
            "last_payload_path": str((Path(args.output).expanduser().resolve()) if args.output else ""),
            "last_error": "",
            "last_error_at": "",
        },
    )
    append_work_order_event(
        work_order_path,
        stage="payload_build",
        status="succeeded",
        submitter="github_mcp",
        message="Built github_mcp payload from work_order.json.",
        artifacts_dir=str((work_order_path.parent / "artifacts").resolve()),
        extra={"output_path": str((Path(args.output).expanduser().resolve()) if args.output else "")},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
