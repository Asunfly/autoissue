#!/usr/bin/env python3
"""Upload attachments to GitHub assets repo via git clone + push.

This script replaces the broken MCP `push_files` flow which stores base64
text instead of binary images.  It works by:
  1. shallow-cloning the user's `{login}/issue-assets` repo
  2. writing the *decoded binary* files to the correct directory path
  3. git add + commit + push

Directory convention inside issue-assets:
    {owner}/{repo}/{work_id}/{filename}
    e.g.  iOfficeAI/AionUi/wo-20260318T154155-abc/screenshot.png

IMPORTANT: `owner_repo` (like "iOfficeAI/AionUi") contains a "/" that is
intentionally used to create two directory levels inside issue-assets.
Do NOT confuse it with the {login}/issue-assets repo coordinates.

Usage:
    python github_mcp_upload_attachments.py \\
        --work-order /path/to/work_order.json \\
        --login Asunfly
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from issue_payload_support import (
    ATTACHMENT_UPLOAD_METHOD_REPO,
    DEFAULT_ASSETS_REPO_NAME,
    SUBMITTER_GITHUB_MCP,
    append_work_order_event,
    build_assets_repo_attachment_path,
    build_github_raw_url,
    build_repo_attachment_markdown,
    derive_attachment_upload_status,
    ensure_work_order_attachments,
    ensure_work_order_runtime,
    filter_uploadable_attachments,
    normalize_work_order_dict,
    resolve_attachment_paths,
    update_work_order_runtime,
    write_work_order_updates,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Magic bytes for supported image formats
_IMAGE_MAGIC = {
    b"\x89PNG\r\n\x1a\n": "png",
    b"\xff\xd8\xff": "jpeg",
    b"GIF87a": "gif",
    b"GIF89a": "gif",
}


def _verify_binary_image(path: Path) -> Optional[str]:
    """Verify a file is a real binary image, not base64 text.

    Returns None if OK, or an error message if the file is broken.
    """
    try:
        data = path.read_bytes()
    except Exception as exc:
        return f"cannot read file: {exc}"

    if len(data) == 0:
        return "file is empty (0 bytes)"

    # Check 1: if the file is mostly ASCII printable + newlines, it's text
    if len(data) < 1_000_000:  # only check files under 1MB for speed
        printable = sum(1 for b in data[:4096] if 32 <= b <= 126 or b in (10, 13, 9))
        if len(data[:4096]) > 0 and printable / len(data[:4096]) > 0.95:
            return (
                f"file appears to be TEXT ({printable}/{len(data[:4096])} printable bytes). "
                "It was likely stored as base64 instead of binary."
            )

    # Check 2: magic bytes
    matched = False
    for magic in _IMAGE_MAGIC:
        if data[:len(magic)] == magic:
            matched = True
            break
    if not matched:
        hex_head = data[:16].hex(" ")
        return (
            f"file does not start with known image magic bytes "
            f"(first 16 bytes: {hex_head}). Expected PNG/JPEG/GIF header."
        )

    return None  # OK

def _deduplicate_filename(name: str, seen: dict) -> str:
    stem = Path(name).stem
    suffix = Path(name).suffix
    count = seen.get(name, 0)
    seen[name] = count + 1
    if count == 0:
        return name
    return f"{stem}-{count + 1}{suffix}"


def _build_remote_path(owner_repo: str, work_id: str, filename: str) -> str:
    """Build the in-repo path for an attachment."""
    return build_assets_repo_attachment_path(owner_repo, work_id, filename)


def _run(cmd: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    """Run a subprocess; raise on failure."""
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n"
            f"stderr: {result.stderr.strip()}\n"
            f"stdout: {result.stdout.strip()}"
        )
    return result


# ---------------------------------------------------------------------------
# Core upload logic
# ---------------------------------------------------------------------------

def upload_via_git(
    login: str,
    repo_name: str,
    owner_repo: str,
    work_id: str,
    file_pairs: list[dict],  # [{"local_path": ..., "remote_path": ..., "filename": ...}]
    branch: str = "main",
) -> list[dict]:
    """Clone, copy binary files, commit, push. Returns list of uploaded file info."""

    repo_url = f"https://github.com/{login}/{repo_name}.git"

    tmpdir = tempfile.mkdtemp(prefix="issue-assets-")
    clone_dir = os.path.join(tmpdir, repo_name)

    try:
        # Shallow clone (depth 1 is enough — we just need to push a new commit)
        _run(["git", "clone", "--depth", "1", repo_url, clone_dir])

        uploaded = []
        for fp in file_pairs:
            local = Path(fp["local_path"])
            remote = fp["remote_path"]         # e.g. "iOfficeAI/AionUi/wo-xxx/file.png"
            filename = fp["filename"]

            dest = Path(clone_dir) / remote
            dest.parent.mkdir(parents=True, exist_ok=True)

            # Copy BINARY file — no base64, no encoding, raw bytes
            shutil.copy2(str(local), str(dest))

            # Verify: destination must be a real binary image, not text
            verify_err = _verify_binary_image(dest)
            if verify_err:
                raise RuntimeError(
                    f"Post-copy verification FAILED for {filename}: {verify_err}\n"
                    f"Source: {local}\n"
                    f"Dest:   {dest}\n"
                    "This means the source file itself is corrupt or was "
                    "previously saved as base64 text instead of binary."
                )

            # Also verify size matches source
            src_size = local.stat().st_size
            dst_size = dest.stat().st_size
            if src_size != dst_size:
                raise RuntimeError(
                    f"Size mismatch for {filename}: "
                    f"source={src_size} bytes, dest={dst_size} bytes"
                )

            raw_url = build_github_raw_url(login=login, repo=repo_name, path=remote, branch=branch)
            uploaded.append({
                "filename": filename,
                "remote_path": remote,
                "raw_url": raw_url,
            })

        if not uploaded:
            return []

        # Stage, commit, push
        _run(["git", "add", "-A"], cwd=clone_dir)
        _run(
            ["git", "commit", "-m", f"Upload attachments for {work_id}"],
            cwd=clone_dir,
        )
        _run(["git", "push", "origin", branch], cwd=clone_dir)

        return uploaded

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload attachments via git clone + push (binary-safe)."
    )
    parser.add_argument("--work-order", required=True, help="Path to work_order.json")
    parser.add_argument("--login", required=True, help="GitHub username (e.g. Asunfly)")
    parser.add_argument(
        "--repo-name", default=DEFAULT_ASSETS_REPO_NAME,
        help=f"Assets repo name (default: {DEFAULT_ASSETS_REPO_NAME})",
    )
    parser.add_argument(
        "--branch",
        default="main",
        help="Assets repo branch to push to (default: main)",
    )
    parser.add_argument(
        "--no-writeback",
        action="store_false",
        dest="writeback",
        default=True,
        help="Do not write uploaded URLs back to work_order.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    work_order_path = Path(args.work_order).expanduser().resolve()

    if not work_order_path.is_file():
        print(json.dumps({"error": f"work_order.json not found: {work_order_path}"}))
        return 1

    runtime_data = ensure_work_order_runtime(work_order_path)
    ensure_work_order_attachments(work_order_path)
    raw = json.loads(work_order_path.read_text(encoding="utf-8"))
    norm = normalize_work_order_dict(raw)
    current_prepare_count = int(runtime_data["runtime"].get("prepare_count") or 0)

    # Skip if already uploaded
    existing_md = norm.get("attachment_markdown", "").strip()
    if existing_md:
        update_work_order_runtime(work_order_path, {
            "status": "attachments_prepared",
            "last_submitter": SUBMITTER_GITHUB_MCP,
            "prepare_count": current_prepare_count + 1,
            "last_error": "",
            "last_error_at": "",
        })
        append_work_order_event(
            work_order_path,
            stage="upload_attachments",
            status="skipped_existing",
            submitter=SUBMITTER_GITHUB_MCP,
            message="Skipped git upload because attachment_markdown already exists.",
            extra={"attachment_upload_status": "uploaded"},
        )
        print(json.dumps({
            "status": "already_uploaded",
            "attachment_markdown": existing_md,
        }, ensure_ascii=False))
        return 0

    owner_repo = norm.get("owner_repo") or raw.get("owner_repo") or ""
    work_id = norm.get("work_id") or raw.get("work_id") or ""
    attachments = norm.get("attachments", [])

    if not attachments:
        write_work_order_updates(work_order_path, {
            "attachment_upload_status": "none",
            "attachment_upload_method": "",
            "attachment_repo": "",
        })
        update_work_order_runtime(work_order_path, {
            "status": "attachments_prepared",
            "last_submitter": SUBMITTER_GITHUB_MCP,
            "prepare_count": current_prepare_count + 1,
            "last_error": "",
            "last_error_at": "",
        })
        append_work_order_event(
            work_order_path,
            stage="upload_attachments",
            status="skipped_no_attachments",
            submitter=SUBMITTER_GITHUB_MCP,
            message="Skipped git upload because no attachments were provided.",
            extra={"attachment_upload_status": "none"},
        )
        print(json.dumps({"status": "no_attachments"}))
        return 0

    if not owner_repo or not work_id:
        error_msg = "owner_repo or work_id missing in work_order.json"
        update_work_order_runtime(work_order_path, {
            "status": "failed",
            "last_submitter": SUBMITTER_GITHUB_MCP,
            "prepare_count": current_prepare_count + 1,
            "last_error": error_msg,
            "last_error_at": "",
        })
        append_work_order_event(
            work_order_path,
            stage="upload_attachments",
            status="failed",
            submitter=SUBMITTER_GITHUB_MCP,
            error=error_msg,
            message="Attachment upload aborted because work_order identity fields are missing.",
        )
        print(json.dumps({"error": error_msg}))
        return 1

    # Resolve and filter
    existing_paths, missing_paths = resolve_attachment_paths(
        attachments, work_order_path.parent,
    )
    uploadable, skipped = filter_uploadable_attachments(existing_paths)
    derived_status = derive_attachment_upload_status(
        raw.get("attachment_upload_status") or "",
        attachment_markdown="",
        existing_paths=existing_paths,
        missing_paths=missing_paths,
    )

    if not uploadable:
        write_work_order_updates(work_order_path, {
            "attachment_upload_status": derived_status,
            "attachment_upload_method": "",
            "attachment_repo": "",
        })
        update_work_order_runtime(work_order_path, {
            "status": "attachments_prepared",
            "last_submitter": SUBMITTER_GITHUB_MCP,
            "prepare_count": current_prepare_count + 1,
            "last_error": "",
            "last_error_at": "",
        })
        append_work_order_event(
            work_order_path,
            stage="upload_attachments",
            status="skipped_not_uploadable",
            submitter=SUBMITTER_GITHUB_MCP,
            message="Skipped git upload because there were no uploadable attachments.",
            extra={
                "attachment_upload_status": derived_status,
                "skipped_attachments": skipped,
                "missing_attachments": missing_paths,
            },
        )
        print(json.dumps({
            "status": "nothing_uploadable",
            "skipped": [s["reason"] for s in skipped],
            "missing": missing_paths,
        }, ensure_ascii=False))
        return 0

    # Build file pairs
    seen: dict = {}
    file_pairs = []
    for local_path in uploadable:
        filename = _deduplicate_filename(local_path.name, seen)
        remote_path = _build_remote_path(owner_repo, work_id, filename)
        file_pairs.append({
            "local_path": str(local_path),
            "remote_path": remote_path,
            "filename": filename,
        })

    # Pre-flight: verify ALL source files are real binary images
    for fp in file_pairs:
        src = Path(fp["local_path"])
        err = _verify_binary_image(src)
        if err:
            error_msg = (
                f"Source file is NOT a valid binary image: {src.name}\n"
                f"  Path: {src}\n"
                f"  Error: {err}\n"
                "Aborting upload — all source files must be valid binary images."
            )
            update_work_order_runtime(work_order_path, {
                "status": "failed",
                "last_submitter": SUBMITTER_GITHUB_MCP,
                "prepare_count": current_prepare_count + 1,
                "last_error": error_msg,
                "last_error_at": "",
            })
            append_work_order_event(
                work_order_path,
                stage="upload_attachments",
                status="failed",
                submitter=SUBMITTER_GITHUB_MCP,
                error=error_msg,
                message="Attachment validation failed before git upload.",
            )
            print(json.dumps({"error": error_msg}, ensure_ascii=False))
            return 1

    # Upload
    login = args.login
    repo_name = args.repo_name

    append_work_order_event(
        work_order_path,
        stage="upload_attachments",
        status="started",
        submitter=SUBMITTER_GITHUB_MCP,
        message=f"Uploading {len(file_pairs)} file(s) via git clone+push.",
    )

    try:
        uploaded = upload_via_git(
            login,
            repo_name,
            owner_repo,
            work_id,
            file_pairs,
            branch=args.branch,
        )
    except Exception as exc:
        error_msg = str(exc)
        write_work_order_updates(work_order_path, {
            "attachment_upload_status": "upload_failed",
            "attachment_upload_method": "",
        })
        update_work_order_runtime(work_order_path, {
            "status": "failed",
            "last_submitter": SUBMITTER_GITHUB_MCP,
            "prepare_count": current_prepare_count + 1,
            "last_error": error_msg,
            "last_error_at": "",
        })
        append_work_order_event(
            work_order_path,
            stage="upload_attachments",
            status="failed",
            submitter=SUBMITTER_GITHUB_MCP,
            error=error_msg,
            message="git clone+push upload failed.",
        )
        print(json.dumps({"error": error_msg}, ensure_ascii=False))
        return 1

    if not uploaded:
        update_work_order_runtime(work_order_path, {
            "status": "attachments_prepared",
            "last_submitter": SUBMITTER_GITHUB_MCP,
            "prepare_count": current_prepare_count + 1,
            "last_error": "",
            "last_error_at": "",
        })
        print(json.dumps({"status": "nothing_uploaded"}))
        return 0

    # Build markdown and write back
    attachment_markdown = build_repo_attachment_markdown(uploaded)
    url_map = {u["filename"]: u["raw_url"] for u in uploaded}
    assets_repo = f"{login}/{repo_name}"

    if args.writeback:
        write_work_order_updates(work_order_path, {
            "attachment_markdown": attachment_markdown,
            "attachment_upload_status": "uploaded",
            "attachment_upload_method": ATTACHMENT_UPLOAD_METHOD_REPO,
            "attachment_repo": assets_repo,
        })
    update_work_order_runtime(work_order_path, {
        "status": "attachments_uploaded",
        "last_submitter": SUBMITTER_GITHUB_MCP,
        "prepare_count": current_prepare_count + 1,
        "last_error": "",
        "last_error_at": "",
    })

    append_work_order_event(
        work_order_path,
        stage="upload_attachments",
        status="succeeded",
        submitter=SUBMITTER_GITHUB_MCP,
        message=f"Uploaded {len(uploaded)} file(s) to {assets_repo} via git push.",
        extra={
            "method": ATTACHMENT_UPLOAD_METHOD_REPO,
            "attachment_repo": assets_repo,
            "uploaded_count": len(uploaded),
            "filenames": list(url_map.keys()),
            "urls": url_map,
            "branch": args.branch,
        },
    )

    result = {
        "status": "uploaded",
        "method": ATTACHMENT_UPLOAD_METHOD_REPO,
        "attachment_markdown": attachment_markdown,
        "uploaded_count": len(uploaded),
        "uploaded_files": uploaded,
        "skipped": [{"path": s["path"], "reason": s["reason"]} for s in skipped],
        "missing": missing_paths,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
