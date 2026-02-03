#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import datetime
import json
import os
import platform as py_platform
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from browser_use import Agent, BrowserSession, llm


AIONUI_REPO = "iOfficeAI/AionUi"
AIONUI_URL = "https://github.com/iOfficeAI/AionUi"

ROOT_DIR = Path(__file__).resolve().parents[2]
AGENT_PROMPT_PATH = ROOT_DIR / "AGENT_PROMPT.md"
COMMON_SKILL_PATH = ROOT_DIR / "COMMON_SKILL.md"


# ---------------------------
# Template helpers (YAML-driven fill)
# ---------------------------

def load_issue_template(template_path: Path) -> dict:
    with template_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def template_for_issue_type(issue_type: str, assets_templates_dir: Path) -> Tuple[str, Path]:
    issue_type = (issue_type or "").lower()
    name = "feature_request.yml" if issue_type.startswith("feat") else "bug_report.yml"
    return name, assets_templates_dir / name


def all_fields_from_template(tpl: dict) -> List[dict]:
    body = tpl.get("body", []) if isinstance(tpl, dict) else []
    return [i for i in body if isinstance(i, dict) and i.get("id")]


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
    for o in options:
        if o.lower() == value.lower():
            return o
    return options[0]


# ---------------------------
# Work order
# ---------------------------

@dataclass
class WorkOrder:
    owner_repo: str = AIONUI_REPO
    project_url: str = AIONUI_URL
    issue_type: str = "bug"  # "bug" | "feature"
    title: str = ""

    # Bug ids
    platform: str = ""
    version: str = "latest"
    bug_description: str = ""
    steps_to_reproduce: str = ""
    expected_behavior: str = ""
    actual_behavior: str = ""
    additional_context: str = ""

    # Feature ids
    feature_description: str = ""
    problem_statement: str = ""
    proposed_solution: str = ""
    feature_category: str = ""

    # Common
    attachments: List[str] = None
    raw: Dict[str, Any] = None



def _infer_platform_default() -> str:
    sysname = py_platform.system().lower()
    if "windows" in sysname:
        return "Windows"
    if "linux" in sysname:
        return "Linux"
    if "darwin" in sysname or "mac" in sysname:
        return "macOS (Intel)"
    return "Windows"


def normalize_work_order_dict(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize payload into template-id-aligned keys.
    Accepts:
      - recommended keys (platform/version/bug_description/...)
      - legacy keys (description/steps/expected/template/problem/solution/category)
    """
    out = dict(raw or {})

    # issue_type inference
    it = (out.get("issue_type") or "").lower()
    tpl = (out.get("template") or "").lower()
    if not it:
        if "feature" in tpl:
            it = "feature"
        elif "bug" in tpl:
            it = "bug"
    out["issue_type"] = it or "bug"

    # steps
    steps = out.get("steps_to_reproduce") or out.get("steps") or ""
    if isinstance(steps, list):
        out["steps_to_reproduce"] = "\n".join(str(s) for s in steps)
    else:
        out["steps_to_reproduce"] = str(steps or "")

    # bug mappings
    out["bug_description"] = str(out.get("bug_description") or out.get("description") or "")
    out["expected_behavior"] = str(out.get("expected_behavior") or out.get("expected") or "")
    out["actual_behavior"] = str(out.get("actual_behavior") or out["bug_description"] or "")
    out["version"] = str(out.get("version") or "latest")
    out["platform"] = str(out.get("platform") or _infer_platform_default())
    out["additional_context"] = str(out.get("additional_context") or "")

    # feature mappings
    out["feature_description"] = str(out.get("feature_description") or out.get("description") or "")
    out["problem_statement"] = str(out.get("problem_statement") or out.get("problem") or "")
    out["proposed_solution"] = str(
        out.get("proposed_solution") or out.get("solution") or out.get("expected_behavior") or ""
    )
    out["feature_category"] = str(out.get("feature_category") or out.get("category") or "")
    # additional_context already set

    # attachments
    atts = out.get("attachments") or []
    if not isinstance(atts, list):
        atts = []
    out["attachments"] = [str(a) for a in atts]

    out["title"] = str(out.get("title") or "").strip()

    return out


def load_work_order(path: Path) -> WorkOrder:
    raw = json.loads(path.read_text(encoding="utf-8"))
    norm = normalize_work_order_dict(raw)

    owner_repo = norm.get("owner_repo") or AIONUI_REPO
    if owner_repo != AIONUI_REPO:
        raise SystemExit(f"Minimal branch only supports {AIONUI_REPO}, got: {owner_repo}")
    project_url = norm.get("project_url") or AIONUI_URL

    return WorkOrder(
        owner_repo=owner_repo,
        project_url=project_url,
        issue_type=norm.get("issue_type", "bug"),
        title=norm.get("title", ""),
        platform=norm.get("platform", _infer_platform_default()),
        version=norm.get("version", "latest"),
        bug_description=norm.get("bug_description", ""),
        steps_to_reproduce=norm.get("steps_to_reproduce", ""),
        expected_behavior=norm.get("expected_behavior", ""),
        actual_behavior=norm.get("actual_behavior", "") or norm.get("bug_description", ""),
        additional_context=norm.get("additional_context", ""),
        feature_description=norm.get("feature_description", ""),
        problem_statement=norm.get("problem_statement", ""),
        proposed_solution=norm.get("proposed_solution", ""),
        feature_category=norm.get("feature_category", ""),
        attachments=[str(Path(a)) for a in (norm.get("attachments") or [])],
        raw=raw,
    )


# ---------------------------
# Browser-use helpers
# ---------------------------

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def read_text_file(path: Path, fallback: str) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return fallback


def build_field_payload(tpl: dict, norm: Dict[str, Any], wo: WorkOrder) -> List[Dict[str, Any]]:
    fields_payload = []
    for field in all_fields_from_template(tpl):
        fid = field.get("id")
        ftype = field_type(field)
        flabel = field_label(field)
        required = bool((field.get("validations", {}) or {}).get("required", False))
        options_list = field_options(field)
        value = norm.get(fid, "")

        if fid == "platform":
            value = pick_valid_option(str(value or wo.platform or _infer_platform_default()), options_list)
        if fid == "feature_category":
            value = pick_valid_option(str(value), options_list)
        if fid == "actual_behavior" and not str(value).strip():
            value = norm.get("bug_description", "")
        if fid == "version" and not str(value).strip():
            value = "latest"

        fields_payload.append(
            {
                "id": fid,
                "label": flabel,
                "type": ftype,
                "required": required,
                "options": options_list,
                "value": value,
            }
        )
    return fields_payload


def build_agent_task(
    work_order: WorkOrder,
    template_url: str,
    fields_payload: List[Dict[str, Any]],
    attachments: List[str],
    login_wait_sec: int,
    pause_before_submit_sec: int,
    no_submit: bool,
) -> str:
    field_lines = []
    for field in fields_payload:
        value = str(field["value"]).strip()
        if not value and not field["required"]:
            value = "<留空/跳过>"
        options = ", ".join(field["options"]) if field["options"] else ""
        option_hint = f" | 可选项: {options}" if options else ""
        field_lines.append(
            f"- {field['label']} (id={field['id']}, type={field['type']}, required={field['required']}) -> {value}{option_hint}"
        )

    attachment_lines = attachments or []
    attachment_block = "\n".join(f"- {p}" for p in attachment_lines) if attachment_lines else "- <无>"

    submit_hint = "不要点击 Create" if no_submit else "点击 Create 提交"

    return "\n".join(
        [
            "你是自动化浏览器助手，目标是提交 GitHub Issue。",
            f"仓库固定为: {work_order.owner_repo}",
            f"请从这个模板页面开始: {template_url}",
            f"如果出现登录页，等待用户手动完成登录后再继续（最长等待 {login_wait_sec} 秒）。",
            "填写时不要改写/补写字段内容，严格按给定值填写。",
            f"Issue 标题: {work_order.title}",
            "表单字段如下:",
            *field_lines,
            "附件列表如下（如有需要上传到合适的描述区域/附件区域）:",
            attachment_block,
            f"填写完成后等待 {pause_before_submit_sec} 秒供人工确认，再执行: {submit_hint}",
            "提交成功后，请停留在结果页面，并保持浏览器打开以便读取最终 URL。",
        ]
    )


def is_issue_created_url(url: str) -> bool:
    return bool(re.search(r"/issues/\d+(?:$|[/?#])", url or ""))


def _extract_issue_number_from_url(url: str) -> str:
    m = re.search(r"/issues/(\d+)(?:$|[/?#])", url or "")
    return m.group(1) if m else ""


def _update_work_order_file(path: Path, issue_url: str) -> None:
    """
    Write-back to work_order.json to prevent repeated submission loops:
    - issue_number
    - issue_url
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    data["issue_url"] = issue_url
    num = _extract_issue_number_from_url(issue_url)
    if num:
        data["issue_number"] = num
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def preflight_validate_required(tpl: dict, norm: Dict[str, Any], out_dir: Path, issue_type: str) -> None:
    """
    Validate required fields against Issue Forms YAML BEFORE launching browser.
    - If missing, write a report under out_dir and raise SystemExit.
    """
    missing = []
    for field in all_fields_from_template(tpl):
        fid = field.get("id")
        ftype = field_type(field)
        flabel = field_label(field)
        required = bool((field.get("validations", {}) or {}).get("required", False))
        if not required:
            continue
        val = norm.get(fid, "")
        if fid == "platform" and not str(val).strip():
            val = _infer_platform_default()
        if fid == "version" and not str(val).strip():
            val = "latest"
        if fid == "actual_behavior" and not str(val).strip():
            val = norm.get("bug_description", "")
        if not str(val).strip():
            missing.append({"id": fid, "label": flabel, "type": ftype})

    if missing:
        report = {
            "ok": False,
            "issue_type": issue_type,
            "missing_required": missing,
            "hint": "Fill these fields in work_order.json (align keys to YAML 'id'), then re-run.",
        }
        ensure_dir(out_dir)
        (out_dir / "work_order_validation_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            "ERROR: work_order.json missing required fields (see artifacts/work_order_validation_report.json next to work_order.json)."
        )
        for m in missing:
            print(f" - {m['label']} (id={m['id']}, type={m['type']})")
        raise SystemExit(2)


class _Tee:
    """Write to multiple text streams (used to tee stdout/stderr into artifacts/run.log)."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            try:
                s.write(data)
            except Exception:
                pass

    def flush(self):
        for s in self.streams:
            try:
                s.flush()
            except Exception:
                pass


def _enable_run_logging(artifacts_dir: Path) -> None:
    """
    Tee stdout/stderr to artifacts/run.log so users can debug even if runner doesn't capture console output.
    """
    ensure_dir(artifacts_dir)
    log_path = artifacts_dir / "run.log"
    f = open(log_path, "a", encoding="utf-8", errors="ignore")
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    f.write("\n" + "=" * 80 + "\n")
    f.write(f"[{ts}] run started\n")
    f.flush()
    sys.stdout = _Tee(sys.__stdout__, f)
    sys.stderr = _Tee(sys.__stderr__, f)


def _run_async(coro):
    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_running():
        alt_loop = asyncio.new_event_loop()
        try:
            return alt_loop.run_until_complete(coro)
        finally:
            alt_loop.close()
    return loop.run_until_complete(coro)


def resolve_llm(model_name: Optional[str]):
    if model_name:
        if not hasattr(llm, model_name):
            raise SystemExit(f"Unknown model '{model_name}'. Check browser_use.llm.models for available names.")
        return getattr(llm, model_name)

    if os.getenv("OPENAI_API_KEY"):
        return llm.openai_gpt_4o_mini
    if os.getenv("BROWSER_USE_API_KEY"):
        return llm.bu_latest
    if os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_ENDPOINT"):
        return llm.azure_gpt_4o_mini

    raise SystemExit(
        "Missing LLM credentials. Set OPENAI_API_KEY, BROWSER_USE_API_KEY, or Azure OpenAI variables, "
        "or pass --llm-model to choose a configured model."
    )


def write_agent_context(
    artifacts: Path,
    agent_prompt: str,
    common_skill: str,
    task_prompt: str,
    template_url: str,
    fields_payload: List[Dict[str, Any]],
) -> None:
    ensure_dir(artifacts)
    payload = {
        "template_url": template_url,
        "agent_prompt": agent_prompt,
        "common_skill": common_skill,
        "task_prompt": task_prompt,
        "fields": fields_payload,
    }
    (artifacts / "agent_context.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------
# CLI
# ---------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Auto-submit GitHub issue to iOfficeAI/AionUi via Browser-use.")
    p.add_argument("--work-order", required=False, help="Path to work_order.json")
    p.add_argument("--work-order-file", required=False, help="Alias of --work-order")
    p.add_argument("--headless", action="store_true", help="Run browser headless")
    p.add_argument("--timeout-sec", type=int, default=180, help="Step timeout seconds for each agent action")
    p.add_argument("--login-wait-sec", type=int, default=600, help="Max seconds to wait for manual login")
    p.add_argument("--browser-binary", default=None, help="Path to Chrome/Chromium binary if needed")
    p.add_argument("--user-data-dir", default=None, help="Chrome user data dir to reuse login state")
    p.add_argument("--artifacts-dir", default="artifacts", help="Where to write debug artifacts")
    p.add_argument("--no-submit", action="store_true", help="Fill form but DO NOT click Create")
    p.add_argument("--pause-before-submit-sec", type=int, default=10, help="Pause after filling, before clicking Create")
    p.add_argument("--llm-model", default=None, help="browser_use.llm model name (e.g. openai_gpt_4o_mini)")
    p.add_argument("--max-steps", type=int, default=80, help="Max agent steps")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if not args.work_order and args.work_order_file:
        args.work_order = args.work_order_file
    if not args.work_order:
        raise SystemExit("Missing: --work-order (or --work-order-file)")

    work_order_path = Path(args.work_order)
    # Resolve artifacts directory next to work_order.json (not inside skill folder)
    artifacts = Path(args.artifacts_dir)
    if not artifacts.is_absolute():
        artifacts = work_order_path.parent / artifacts
    _enable_run_logging(artifacts)

    # Prevent resubmission loop: if issue_number already present, exit.
    try:
        _pre = json.loads(work_order_path.read_text(encoding="utf-8"))
        if str(_pre.get("issue_number") or "").strip():
            print(f"work_order.json already has issue_number={_pre.get('issue_number')}, skip submission.")
            if _pre.get("issue_url"):
                print(f"Existing issue_url: {_pre.get('issue_url')}")
            return 0
    except Exception:
        pass

    wo = load_work_order(work_order_path)

    # Default user-data-dir under user config to reduce repeated login.
    if not args.user_data_dir:
        home = Path.home()
        if py_platform.system().lower().startswith("windows"):
            lad = os.environ.get("LOCALAPPDATA")
            base_dir = Path(lad) if lad else (home / ".aionui")
        else:
            base_dir = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config")))
        args.user_data_dir = str(base_dir / "AionUi" / "chrome_user_data")
    ensure_dir(Path(args.user_data_dir))

    assets_templates_dir = ROOT_DIR / "assets" / "templates"
    template_filename, template_path = template_for_issue_type(wo.issue_type, assets_templates_dir)
    template_url = f"{wo.project_url}/issues/new?template={template_filename}"

    raw_payload = json.loads(work_order_path.read_text(encoding="utf-8"))
    norm = normalize_work_order_dict(raw_payload)
    tpl = load_issue_template(template_path)
    preflight_validate_required(tpl, norm, artifacts, wo.issue_type)

    fields_payload = build_field_payload(tpl, norm, wo)

    agent_prompt = read_text_file(
        AGENT_PROMPT_PATH,
        "你是浏览器自动化助手，负责在 GitHub Issue 表单中准确填写并提交，不要改写用户内容。",
    )
    common_skill = read_text_file(
        COMMON_SKILL_PATH,
        "通用技能：识别表单字段、按标签填写、必要时等待登录、完成后回到结果页面。",
    )

    task_prompt = build_agent_task(
        work_order=wo,
        template_url=template_url,
        fields_payload=fields_payload,
        attachments=wo.attachments or [],
        login_wait_sec=max(30, int(args.login_wait_sec)),
        pause_before_submit_sec=max(0, int(args.pause_before_submit_sec)),
        no_submit=args.no_submit,
    )

    write_agent_context(artifacts, agent_prompt, common_skill, task_prompt, template_url, fields_payload)

    model = resolve_llm(args.llm_model)

    browser_session = BrowserSession(
        headless=args.headless,
        user_data_dir=args.user_data_dir,
        executable_path=args.browser_binary,
    )

    agent = Agent(
        task=task_prompt,
        llm=model,
        browser_session=browser_session,
        override_system_message=agent_prompt,
        extend_system_message=common_skill,
        available_file_paths=wo.attachments or None,
        save_conversation_path=artifacts / "agent_conversation.json",
        step_timeout=max(30, int(args.timeout_sec)),
    )

    history = None
    try:
        history = agent.run(max_steps=max(10, int(args.max_steps)))
        if history:
            with contextlib.suppress(Exception):
                history.save_to_file(artifacts / "agent_history.json")

        if args.no_submit:
            print("NO-SUBMIT: filled the form but did not click Create.")
            return 0

        current_url = _run_async(browser_session.get_current_page_url())
        if current_url and is_issue_created_url(current_url):
            print(f"SUCCESS: {current_url}")
            _update_work_order_file(work_order_path, current_url)
            # Post-submit wait to improve UX / allow final validation
            if not args.headless:
                time.sleep(10)
            return 0

        print("WARNING: Could not confirm issue URL. Please check the browser or agent_history.json.")
        return 1

    except Exception as e:
        print(f"ERROR: {e}")
        return 1
    finally:
        with contextlib.suppress(Exception):
            _run_async(browser_session.stop())


if __name__ == "__main__":
    raise SystemExit(main())
