#!/usr/bin/env python3
"""Write back uploaded attachment URLs to work_order.json.

Called by the agent after uploading files to the assets repo via GitHub MCP.

Usage:
    python writeback_attachment_urls.py \
        --work-order /path/to/work_order.json \
        --urls '{"screenshot.png":"https://raw.githubusercontent.com/.../screenshot.png"}' \
        --repo "Asunfly/issue-assets" \
        --method "repo"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from issue_payload_support import (
    append_work_order_event,
    build_repo_attachment_markdown,
    ensure_work_order_runtime,
    update_work_order_runtime,
    write_work_order_updates,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write back uploaded attachment URLs to work_order.json."
    )
    parser.add_argument("--work-order", required=True, help="Path to work_order.json")
    parser.add_argument(
        "--urls",
        required=True,
        help='JSON object: {"filename": "raw_url", ...}',
    )
    parser.add_argument("--repo", required=True, help="Assets repo, e.g. Asunfly/issue-assets")
    parser.add_argument("--method", default="repo", help="Upload method (default: repo)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    work_order_path = Path(args.work_order).expanduser().resolve()

    if not work_order_path.is_file():
        print(f"Error: work_order.json not found: {work_order_path}", file=sys.stderr)
        return 1

    ensure_work_order_runtime(work_order_path)

    # Parse URL mapping
    try:
        url_map: dict = json.loads(args.urls)
    except json.JSONDecodeError as exc:
        print(f"Error: invalid --urls JSON: {exc}", file=sys.stderr)
        return 1

    if not url_map:
        print("Warning: empty URL map, nothing to write back.", file=sys.stderr)
        return 0

    # Build attachment markdown
    uploaded_files = [
        {"filename": filename, "raw_url": raw_url}
        for filename, raw_url in url_map.items()
    ]
    attachment_markdown = build_repo_attachment_markdown(uploaded_files)

    # Write back to work_order.json
    write_work_order_updates(work_order_path, {
        "attachment_markdown": attachment_markdown,
        "attachment_upload_status": "uploaded",
        "attachment_upload_method": args.method,
        "attachment_repo": args.repo,
    })

    update_work_order_runtime(work_order_path, {
        "status": "attachments_prepared",
        "last_submitter": "github_mcp",
        "last_error": "",
        "last_error_at": "",
    })

    append_work_order_event(
        work_order_path,
        stage="prepare_attachments",
        status="succeeded",
        submitter="github_mcp",
        message=f"Uploaded {len(url_map)} attachment(s) to {args.repo} via {args.method}.",
        extra={
            "method": args.method,
            "attachment_repo": args.repo,
            "uploaded_count": len(url_map),
            "filenames": list(url_map.keys()),
        },
    )

    print(json.dumps({
        "status": "ok",
        "attachment_markdown": attachment_markdown,
        "uploaded_count": len(url_map),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
