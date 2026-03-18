#!/usr/bin/env python3
"""Prepare local attachments for upload to a GitHub assets repo.

This script reads work_order.json, resolves and filters attachments,
base64-encodes each uploadable file, and outputs a JSON payload to stdout.
It does NOT call any GitHub API — the actual upload is done by the agent
via GitHub MCP tools.

Usage:
    python prepare_attachments_for_repo.py --work-order /path/to/work_order.json
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from collections import Counter
from pathlib import Path

from issue_payload_support import (
    DEFAULT_ASSETS_REPO_NAME,
    append_work_order_event,
    ensure_work_order_runtime,
    filter_uploadable_attachments,
    normalize_work_order_dict,
    resolve_attachment_paths,
)


def _deduplicate_filename(name: str, seen: Counter) -> str:
    """Return a unique filename by appending -N suffix if already seen."""
    stem = Path(name).stem
    suffix = Path(name).suffix
    count = seen[name]
    seen[name] += 1
    if count == 0:
        return name
    return f"{stem}-{count + 1}{suffix}"


def _build_remote_path(owner_repo: str, work_id: str, filename: str) -> str:
    """Build remote path: {owner}/{repo}/{work_id}/{filename}.

    owner_repo like 'iOfficeAI/AionUi' becomes directory levels naturally.
    """
    return f"{owner_repo}/{work_id}/{filename}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare attachments for repo-based upload."
    )
    parser.add_argument("--work-order", required=True, help="Path to work_order.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    work_order_path = Path(args.work_order).expanduser().resolve()

    if not work_order_path.is_file():
        print(json.dumps({"error": f"work_order.json not found: {work_order_path}"}))
        return 1

    ensure_work_order_runtime(work_order_path)
    raw = json.loads(work_order_path.read_text(encoding="utf-8"))
    norm = normalize_work_order_dict(raw)

    # Already has attachment_markdown — skip preparation
    existing_markdown = norm.get("attachment_markdown", "").strip()
    if existing_markdown:
        print(json.dumps({
            "status": "already_prepared",
            "attachment_markdown": existing_markdown,
            "files": [],
            "skipped": [],
            "missing": [],
        }, ensure_ascii=False))
        return 0

    owner_repo = norm.get("owner_repo") or raw.get("owner_repo") or ""
    work_id = norm.get("work_id") or raw.get("work_id") or ""
    attachments = norm.get("attachments", [])

    if not attachments:
        print(json.dumps({
            "status": "no_attachments",
            "files": [],
            "skipped": [],
            "missing": [],
        }, ensure_ascii=False))
        return 0

    # Resolve paths
    existing_paths, missing_paths = resolve_attachment_paths(
        attachments, work_order_path.parent
    )

    # Filter uploadable
    uploadable, skipped = filter_uploadable_attachments(existing_paths)

    if not uploadable:
        result = {
            "status": "nothing_uploadable",
            "owner_repo": owner_repo,
            "work_id": work_id,
            "files": [],
            "skipped": [{"path": s["path"], "reason": s["reason"]} for s in skipped],
            "missing": missing_paths,
        }
        print(json.dumps(result, ensure_ascii=False))
        return 0

    # Build file entries with base64 content
    files = []
    seen_names: Counter = Counter()
    for local_path in uploadable:
        filename = _deduplicate_filename(local_path.name, seen_names)
        remote_path = _build_remote_path(owner_repo, work_id, filename)
        content_bytes = local_path.read_bytes()
        b64 = base64.b64encode(content_bytes).decode("ascii")
        files.append({
            "local_path": str(local_path),
            "remote_path": remote_path,
            "filename": filename,
            "base64_content": b64,
        })

    result = {
        "status": "ready",
        "owner_repo": owner_repo,
        "work_id": work_id,
        "assets_repo_name": DEFAULT_ASSETS_REPO_NAME,
        "files": files,
        "skipped": [{"path": s["path"], "reason": s["reason"]} for s in skipped],
        "missing": missing_paths,
    }

    # Log event
    append_work_order_event(
        work_order_path,
        stage="prepare_attachments",
        status="started",
        submitter="github_mcp",
        message=f"Prepared {len(files)} file(s) for repo upload.",
        extra={
            "method": "repo",
            "file_count": len(files),
            "skipped_count": len(skipped),
            "missing_count": len(missing_paths),
        },
    )

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
