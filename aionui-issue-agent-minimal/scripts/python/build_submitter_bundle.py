#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from issue_payload_support import (
    AIONUI_REPO,
    AIONUI_URL,
    all_fields_from_template,
    apply_template_defaults,
    append_work_order_event,
    build_issue_body_markdown,
    build_local_attachment_markdown,
    ensure_work_order_runtime,
    field_label,
    field_type,
    filter_uploadable_attachments,
    load_issue_template,
    normalize_work_order_dict,
    resolve_attachment_paths,
    template_for_issue_type,
    update_work_order_runtime,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build submitter-specific bundle from work_order.json.")
    parser.add_argument("--work-order", required=True, help="Path to work_order.json")
    parser.add_argument(
        "--submitter",
        required=True,
        choices=["skill", "chrome_mcp", "github_mcp"],
        help="Target submitter to build for",
    )
    parser.add_argument("--output", help="Optional output JSON file path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    work_order_path = Path(args.work_order).expanduser().resolve()
    ensure_work_order_runtime(work_order_path)

    raw = json.loads(work_order_path.read_text(encoding="utf-8"))
    norm = normalize_work_order_dict(raw)
    assets_templates_dir = Path(__file__).resolve().parents[2] / "assets" / "templates"
    template_filename, template_path = template_for_issue_type(norm.get("issue_type", "bug"), assets_templates_dir)
    tpl = load_issue_template(template_path)
    norm, _ = apply_template_defaults(tpl, norm)

    attachment_paths, missing_paths = resolve_attachment_paths(norm.get("attachments", []), work_order_path.parent)
    _, skipped = filter_uploadable_attachments(attachment_paths)
    attachment_markdown = str(norm.get("attachment_markdown") or "").strip()
    local_attachment_markdown = build_local_attachment_markdown(attachment_paths, missing_paths, skipped)
    attachment_block = attachment_markdown or local_attachment_markdown

    base = {
        "schema_version": raw.get("schema_version") or "",
        "session_id": raw.get("session_id") or "",
        "work_id": raw.get("work_id") or "",
        "owner_repo": raw.get("owner_repo") or AIONUI_REPO,
        "project_url": raw.get("project_url") or AIONUI_URL,
        "issue_type": norm.get("issue_type", "bug"),
        "title": norm.get("title", ""),
        "template_url": f"{raw.get('project_url') or AIONUI_URL}/issues/new?template={template_filename}",
        "attachment_upload_status": raw.get("attachment_upload_status") or ("uploaded" if attachment_markdown else "none"),
    }

    if args.submitter == "github_mcp":
        bundle = {
            **base,
            "submitter": "github_mcp",
            "body": build_issue_body_markdown(norm, tpl, attachment_markdown=attachment_block),
        }
    elif args.submitter == "chrome_mcp":
        fields = []
        for field in all_fields_from_template(tpl):
            field_id = str(field.get("id") or "")
            value = str(norm.get(field_id) or "")
            if field_id == "additional_context":
                value = build_issue_body_markdown({"additional_context": value}, {"body": [field]}, attachment_markdown=attachment_block)
                value = value.replace("## " + field_label(field) + "\n", "", 1).strip()
            fields.append(
                {
                    "id": field_id,
                    "label": field_label(field),
                    "type": field_type(field),
                    "value": value,
                }
            )
        bundle = {
            **base,
            "submitter": "chrome_mcp",
            "fields": fields,
        }
    else:
        bundle = {
            **base,
            "submitter": "skill",
            "command": [
                "bash",
                "run_macos_linux.sh",
                str(work_order_path),
            ],
            "artifacts_dir": str((work_order_path.parent / "artifacts").resolve()),
        }

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        payload_path = str(output_path)
    else:
        print(json.dumps(bundle, ensure_ascii=False, indent=2))
        payload_path = ""

    update_work_order_runtime(
        work_order_path,
        {
            "status": "bundle_ready",
            "last_submitter": args.submitter,
            "last_payload_path": payload_path,
            "last_error": "",
            "last_error_at": "",
        },
    )
    append_work_order_event(
        work_order_path,
        stage="bundle_build",
        status="succeeded",
        submitter=args.submitter,
        message=f"Built submitter bundle for {args.submitter}.",
        artifacts_dir=str((work_order_path.parent / "artifacts").resolve()),
        extra={"output_path": payload_path},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
