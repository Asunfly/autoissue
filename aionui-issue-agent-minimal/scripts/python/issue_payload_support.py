#!/usr/bin/env python3
from __future__ import annotations

import datetime
import json
import platform as py_platform
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


AIONUI_REPO = "iOfficeAI/AionUi"
AIONUI_URL = "https://github.com/iOfficeAI/AionUi"
WORK_ORDER_SCHEMA_VERSION = "v23"
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".gif", ".jpg", ".jpeg"}
MAX_GITHUB_IMAGE_BYTES = 10 * 1024 * 1024


def iso_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def new_work_id(prefix: str = "wo") -> str:
    ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    return f"{prefix}-{ts}-{uuid.uuid4().hex[:6]}"


def load_issue_template(template_path: Path) -> dict:
    with template_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def template_for_issue_type(issue_type: str, assets_templates_dir: Path) -> Tuple[str, Path]:
    issue_type = (issue_type or "").lower()
    name = "feature_request.yml" if issue_type.startswith("feat") else "bug_report.yml"
    return name, assets_templates_dir / name


def all_fields_from_template(tpl: dict) -> List[dict]:
    body = tpl.get("body", []) if isinstance(tpl, dict) else []
    return [item for item in body if isinstance(item, dict) and item.get("id")]


def field_label(item: dict) -> str:
    attrs = item.get("attributes", {}) or {}
    return str(attrs.get("label", "")).strip()


def field_type(item: dict) -> str:
    return str(item.get("type", "")).strip().lower()


def field_options(item: dict) -> List[str]:
    attrs = item.get("attributes", {}) or {}
    opts = attrs.get("options", []) or []
    return [str(o) for o in opts]


def pick_valid_option(value: str, options: List[str]) -> str:
    if not options:
        return value
    if not value:
        return options[0]
    for option in options:
        if option.lower() == value.lower():
            return option
    return options[0]


def option_matches(value: str, options: List[str]) -> bool:
    v = (value or "").strip().lower()
    if not v or not options:
        return False
    return any(v == str(option).strip().lower() for option in options)


def infer_platform_default() -> str:
    sysname = py_platform.system().lower()
    if "windows" in sysname:
        return "Windows"
    if "linux" in sysname:
        return "Linux"
    if "darwin" in sysname or "mac" in sysname:
        machine = (py_platform.machine() or "").lower()
        if machine in ("arm64", "aarch64"):
            return "macOS (Apple Silicon)"
        return "macOS (Intel)"
    return "Windows"


def normalize_work_order_dict(raw: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(raw or {})

    issue_type = (out.get("issue_type") or "").lower()
    tpl = (out.get("template") or "").lower()
    if not issue_type:
        if "feature" in tpl:
            issue_type = "feature"
        elif "bug" in tpl:
            issue_type = "bug"
    out["issue_type"] = issue_type or "bug"

    steps = out.get("steps_to_reproduce") or out.get("steps") or ""
    if isinstance(steps, list):
        out["steps_to_reproduce"] = "\n".join(str(s) for s in steps)
    else:
        out["steps_to_reproduce"] = str(steps or "")

    out["bug_description"] = str(out.get("bug_description") or out.get("description") or "")
    out["expected_behavior"] = str(out.get("expected_behavior") or out.get("expected") or "")
    out["actual_behavior"] = str(out.get("actual_behavior") or out["bug_description"] or "")
    out["additional_context"] = str(out.get("additional_context") or "")

    if out["issue_type"] == "bug":
        out["version"] = str(out.get("version") or "").strip()
        raw_platform = str(out.get("platform") or "").strip()
        if raw_platform.lower() in ("auto", "detect"):
            raw_platform = ""
        out["platform"] = raw_platform or infer_platform_default()

    out["feature_description"] = str(out.get("feature_description") or out.get("description") or "")
    out["problem_statement"] = str(out.get("problem_statement") or out.get("problem") or "")
    out["proposed_solution"] = str(
        out.get("proposed_solution") or out.get("solution") or out.get("expected_behavior") or ""
    )
    out["feature_category"] = str(out.get("feature_category") or out.get("category") or "")

    attachments = out.get("attachments") or []
    if not isinstance(attachments, list):
        attachments = []
    out["attachments"] = [str(item) for item in attachments]
    out["attachment_markdown"] = str(out.get("attachment_markdown") or "").strip()
    out["attachment_upload_status"] = str(out.get("attachment_upload_status") or "").strip()
    out["title"] = str(out.get("title") or "").strip()
    return out


def apply_template_defaults(tpl: dict, norm: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    out = dict(norm or {})
    updates: Dict[str, Any] = {}

    for field in all_fields_from_template(tpl):
        field_id = field.get("id")
        options_list = field_options(field)
        value = out.get(field_id, "")

        if field_id == "platform" and field_type(field) == "dropdown":
            if not str(value).strip():
                inferred = infer_platform_default()
                chosen = inferred if option_matches(inferred, options_list) else pick_valid_option("", options_list)
                out["platform"] = chosen
                updates["platform"] = chosen
            elif options_list and not option_matches(str(value), options_list):
                inferred = infer_platform_default()
                chosen = inferred if option_matches(inferred, options_list) else pick_valid_option("", options_list)
                out["platform"] = chosen
                updates["platform"] = chosen

        if field_id == "actual_behavior" and not str(value).strip():
            fallback = str(out.get("bug_description") or "")
            if fallback.strip():
                out["actual_behavior"] = fallback
                updates["actual_behavior"] = fallback

        if field_id == "feature_category" and field_type(field) == "dropdown":
            if options_list and not option_matches(str(value), options_list):
                chosen = pick_valid_option(str(value), options_list)
                out["feature_category"] = chosen
                updates["feature_category"] = chosen

    return out, updates


def resolve_attachment_paths(attachments: List[str], base_dir: Path) -> Tuple[List[Path], List[str]]:
    existing: List[Path] = []
    missing: List[str] = []
    for raw in attachments or []:
        if not str(raw).strip():
            continue
        candidate = Path(str(raw)).expanduser()
        if not candidate.is_absolute():
            candidate = (base_dir / candidate).resolve()
        else:
            candidate = candidate.resolve()
        if candidate.is_file():
            existing.append(candidate)
        else:
            missing.append(str(candidate))
    return existing, missing


def filter_uploadable_attachments(paths: List[Path]) -> Tuple[List[Path], List[Dict[str, str]]]:
    uploadable: List[Path] = []
    skipped: List[Dict[str, str]] = []
    for path in paths:
        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_IMAGE_EXTENSIONS:
            skipped.append({"path": str(path), "reason": f"unsupported_extension:{suffix or 'none'}"})
            continue
        try:
            size = path.stat().st_size
        except Exception:
            skipped.append({"path": str(path), "reason": "stat_failed"})
            continue
        if size > MAX_GITHUB_IMAGE_BYTES:
            skipped.append({"path": str(path), "reason": f"file_too_large:{size}"})
            continue
        uploadable.append(path)
    return uploadable, skipped


def build_local_attachment_markdown(
    existing: List[Path],
    missing: List[str],
    skipped: List[Dict[str, str]] | None = None,
) -> str:
    sections: List[str] = []
    if existing:
        lines = [f"- `{path.name}`: `{path}`" for path in existing]
        sections.append("附件（本地路径，尚未上传）:\n" + "\n".join(lines))
    if missing:
        lines = [f"- `{path}`" for path in missing]
        sections.append("附件路径无效或文件不存在:\n" + "\n".join(lines))
    if skipped:
        lines = [f"- `{item['path']}`: `{item['reason']}`" for item in skipped]
        sections.append("附件已跳过上传（仍保留本地路径）:\n" + "\n".join(lines))
    return "\n\n".join(sections).strip()


def merge_markdown_blocks(*blocks: str) -> str:
    return "\n\n".join(block.strip() for block in blocks if block and block.strip())


def build_issue_body_markdown(norm: Dict[str, Any], tpl: dict, attachment_markdown: str = "") -> str:
    sections: List[str] = []

    for field in all_fields_from_template(tpl):
        field_id = str(field.get("id") or "")
        label = field_label(field) or field_id
        value = str(norm.get(field_id) or "")
        if field_id == "additional_context":
            value = merge_markdown_blocks(value, attachment_markdown)
        if field_id == "actual_behavior" and not value.strip():
            value = str(norm.get("bug_description") or "")
        if not value.strip():
            continue
        sections.append(f"## {label}\n{value.strip()}")

    return "\n\n".join(sections).strip()


def write_work_order_updates(path: Path, updates: Dict[str, Any]) -> None:
    if not updates:
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for key, value in updates.items():
        if data.get(key) != value:
            data[key] = value
            changed = True
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_work_order_runtime(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False

    if data.get("schema_version") != WORK_ORDER_SCHEMA_VERSION:
        data["schema_version"] = WORK_ORDER_SCHEMA_VERSION
        changed = True

    if not str(data.get("work_id") or "").strip():
        data["work_id"] = new_work_id()
        changed = True

    runtime = data.get("runtime")
    if not isinstance(runtime, dict):
        runtime = {}
        data["runtime"] = runtime
        changed = True

    defaults = {
        "workspace_dir": str(path.parent.resolve()),
        "artifacts_dir": str((path.parent / "artifacts").resolve()),
        "status": "draft",
        "last_submitter": "",
        "last_error": "",
        "last_error_at": "",
        "last_run_log": "",
        "last_payload_path": "",
        "attempt_count": 0,
        "prepare_count": 0,
        "submission_count": 0,
        "updated_at": iso_now(),
    }
    for key, value in defaults.items():
        if runtime.get(key) in (None, ""):
            runtime[key] = value
            changed = True

    events = data.get("events")
    if not isinstance(events, list):
        data["events"] = []
        changed = True

    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def update_work_order_runtime(path: Path, runtime_updates: Dict[str, Any], top_level_updates: Dict[str, Any] | None = None) -> Dict[str, Any]:
    data = ensure_work_order_runtime(path)
    changed = False

    runtime = data["runtime"]
    for key, value in (runtime_updates or {}).items():
        if runtime.get(key) != value:
            runtime[key] = value
            changed = True
    runtime["updated_at"] = iso_now()

    for key, value in (top_level_updates or {}).items():
        if data.get(key) != value:
            data[key] = value
            changed = True

    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def append_work_order_event(
    path: Path,
    *,
    stage: str,
    status: str,
    submitter: str = "",
    message: str = "",
    error: str = "",
    issue_url: str = "",
    issue_number: str = "",
    artifacts_dir: str = "",
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    data = ensure_work_order_runtime(path)
    event = {
        "timestamp": iso_now(),
        "stage": stage,
        "status": status,
        "submitter": submitter,
        "message": message,
        "error": error,
        "issue_url": issue_url,
        "issue_number": issue_number,
        "artifacts_dir": artifacts_dir,
    }
    if extra:
        event["extra"] = extra
    data["events"].append(event)
    data["runtime"]["updated_at"] = event["timestamp"]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data
