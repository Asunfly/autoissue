#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import json
import os
import platform as py_platform
import re
import shutil
import subprocess
import sys
import datetime
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException, SessionNotCreatedException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


AIONUI_REPO = "iOfficeAI/AionUi"
AIONUI_URL = "https://github.com/iOfficeAI/AionUi"


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

def option_matches(value: str, options: List[str]) -> bool:
    v = (value or "").strip().lower()
    if not v or not options:
        return False
    return any(v == str(o).strip().lower() for o in options)


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
        machine = (py_platform.machine() or "").lower()
        if machine in ("arm64", "aarch64"):
            return "macOS (Apple Silicon)"
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

    # bug mappings (only meaningful for bug template)
    out["bug_description"] = str(out.get("bug_description") or out.get("description") or "")
    out["expected_behavior"] = str(out.get("expected_behavior") or out.get("expected") or "")
    out["actual_behavior"] = str(out.get("actual_behavior") or out["bug_description"] or "")
    out["additional_context"] = str(out.get("additional_context") or "")

    if out["issue_type"] == "bug":
        out["version"] = str(out.get("version") or "latest")
        raw_platform = str(out.get("platform") or "").strip()
        if raw_platform.lower() in ("auto", "detect"):
            raw_platform = ""
        out["platform"] = raw_platform or _infer_platform_default()

    # feature mappings
    out["feature_description"] = str(out.get("feature_description") or out.get("description") or "")
    out["problem_statement"] = str(out.get("problem_statement") or out.get("problem") or "")
    out["proposed_solution"] = str(out.get("proposed_solution") or out.get("solution") or out.get("expected_behavior") or "")
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
# Selenium helpers
# ---------------------------

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def save_debug(driver, artifacts: Path, prefix: str) -> None:
    ensure_dir(artifacts)
    ts = int(time.time())
    with contextlib.suppress(Exception):
        driver.save_screenshot(str(artifacts / f"{prefix}_{ts}.png"))
    with contextlib.suppress(Exception):
        (artifacts / f"{prefix}_{ts}.html").write_text(driver.page_source, encoding="utf-8")


def find_control_by_label(driver, label_text: str):
    """
    Stable mapping: label text -> label element -> aria-labelledby token match.
    Returns (label_el, control_el).
    """
    labs = driver.find_elements(By.XPATH, f"//label[normalize-space(.)={json.dumps(label_text)}]")
    if not labs:
        labs = driver.find_elements(By.XPATH, f"//label[contains(normalize-space(.), {json.dumps(label_text)})]")
    if not labs:
        return None, None

    lab = labs[0]
    lid = lab.get_attribute("id")
    if lid:
        # aria-labelledby often contains multiple IDs; token selector handles that
        controls = driver.find_elements(By.CSS_SELECTOR, f"[aria-labelledby~='{lid}']")
        if controls:
            return lab, controls[0]

    # fallback "for"
    tid = lab.get_attribute("for")
    if tid:
        els = driver.find_elements(By.ID, tid)
        if els:
            return lab, els[0]

    # last resort: next control
    for tag in ["textarea", "input", "button"]:
        cand = lab.find_elements(By.XPATH, f"following::{tag}[1]")
        if cand:
            return lab, cand[0]

    return lab, None


def set_text_control(el, value: str):
    with contextlib.suppress(Exception):
        el.click()
    with contextlib.suppress(Exception):
        el.clear()
    el.send_keys(value)


def dropdown_already_selected(control_btn, wanted: str) -> bool:
    try:
        txt = (control_btn.text or "").strip()
        return wanted.lower() in txt.lower()
    except Exception:
        return False


def select_dropdown_option(driver, wait: WebDriverWait, control_btn, option_text: str) -> bool:
    """
    Select an option from GitHub ActionList dropdown (Issue Forms).
    Strategy:
      - If already selected, return True
      - Click button to open
      - Find menu/listbox role items and click the one matching option_text
      - Wait until button text updates / menu closes
    """
    if dropdown_already_selected(control_btn, option_text):
        return True

    try:
        control_btn.click()
    except Exception:
        return False

    # wait menu
    with contextlib.suppress(Exception):
        wait.until(EC.presence_of_element_located((By.XPATH, "//ul[@role='menu' or @role='listbox']")))

    # prefer role=menuitemradio/option inside the opened menu/listbox
    items = driver.find_elements(By.XPATH, "//ul[@role='menu' or @role='listbox']//*[@role='menuitemradio' or @role='option']")
    target = None
    for it in items:
        t = ""
        with contextlib.suppress(Exception):
            t = (it.text or "").strip()
        if option_text.lower() in t.lower():
            target = it
            break

    if target is None:
        # fallback global
        items2 = driver.find_elements(By.XPATH, "//*[@role='menuitemradio' or @role='option']")
        for it in items2:
            t = ""
            with contextlib.suppress(Exception):
                t = (it.text or "").strip()
            if option_text.lower() in t.lower():
                target = it
                break

    if target is None:
        return False

    with contextlib.suppress(Exception):
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", target)

    try:
        target.click()
    except Exception:
        return False

    # wait button text updates OR menu closes
    end = time.time() + 5
    while time.time() < end:
        if dropdown_already_selected(control_btn, option_text):
            return True
        exp = (control_btn.get_attribute("aria-expanded") or "").lower()
        if exp == "false":
            # menu closed; accept
            return dropdown_already_selected(control_btn, option_text) or True
        time.sleep(0.1)
    return dropdown_already_selected(control_btn, option_text)


def is_issue_form_ready(driver) -> bool:
    return bool(driver.find_elements(By.CSS_SELECTOR, "input[aria-label='Add a title']"))


def is_login_page(driver) -> bool:
    url = (driver.current_url or "").lower()
    if "/login" in url or "/session" in url:
        return True
    if driver.find_elements(By.XPATH, "//input[@name='login']"):
        return True
    if driver.find_elements(By.XPATH, "//h1[contains(., 'Sign in')] | //h1[contains(., 'Sign in to GitHub')]"):
        return True
    return False


def wait_until_issue_form_ready(driver, template_url: str, login_wait_sec: int) -> None:
    """
    Business-stable flow:
      - open template_url
      - if redirected to login, wait for user
      - after login, ensure we end up back at template_url (navigate if needed)
      - return once title input is visible
    """
    deadline = time.time() + login_wait_sec
    printed_login_hint = False

    while time.time() < deadline:
        if is_issue_form_ready(driver):
            return

        if is_login_page(driver):
            if not printed_login_hint:
                print("Not logged in. Please complete GitHub login in the opened browser window...")
                printed_login_hint = True
            time.sleep(0.5)
            continue

        # neither ready nor login page — maybe redirected elsewhere after login; go back to template
        with contextlib.suppress(Exception):
            driver.get(template_url)
        time.sleep(0.8)

    raise TimeoutException("Timed out waiting for issue form (login + page load).")


def is_issue_created_url(url: str) -> bool:
    return bool(re.search(r"/issues/\d+(?:$|[/?#])", url or ""))



def _extract_issue_number_from_url(url: str) -> str:
    m = re.search(r"/issues/(\d+)(?:$|[/?#])", url or "")
    return m.group(1) if m else ""

def _write_back_defaults_if_needed(path: Path, updates: Dict[str, Any]) -> None:
    """
    Best-effort write-back to work_order.json for auto-defaulted fields.
    Helps when a work_order.json is moved across machines/OSes.
    """
    if not updates:
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    changed = False
    for k, v in updates.items():
        if data.get(k, None) != v:
            data[k] = v
            changed = True
    if not changed:
        return
    with contextlib.suppress(Exception):
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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
        # dropdowns: treat empty as missing (will be defaulted later by normalize rules, but enforce now)
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
            "hint": "Fill these fields in work_order.json (align keys to YAML 'id'), then re-run."
        }
        ensure_dir(out_dir)
        (out_dir / "work_order_validation_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("ERROR: work_order.json missing required fields (see artifacts/work_order_validation_report.json next to work_order.json).")
        for m in missing:
            print(f" - {m['label']} (id={m['id']}, type={m['type']})")
        raise SystemExit(2)

def apply_template_defaults(tpl: dict, norm: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Apply safe defaults/coercions so platform/version/actual_behavior don't block submission.
    Returns (updated_norm, write_back_updates).
    """
    out = dict(norm or {})
    updates: Dict[str, Any] = {}

    for field in all_fields_from_template(tpl):
        fid = field.get("id")
        ftype = field_type(field)
        options_list = field_options(field)
        value = out.get(fid, "")

        if fid == "platform" and ftype == "dropdown":
            if not str(value).strip():
                inferred = _infer_platform_default()
                chosen = inferred if option_matches(inferred, options_list) else pick_valid_option("", options_list)
                out["platform"] = chosen
                updates["platform"] = chosen
            else:
                # Keep user-provided platform even if it differs from inferred,
                # but if it's not in template options, coerce to inferred/first option.
                if options_list and not option_matches(str(value), options_list):
                    inferred = _infer_platform_default()
                    chosen = inferred if option_matches(inferred, options_list) else pick_valid_option("", options_list)
                    print(f"[WARN] work_order.platform={value!r} is not in template options; using {chosen!r} instead.")
                    out["platform"] = chosen
                    updates["platform"] = chosen

        if fid == "version":
            if not str(value).strip():
                out["version"] = "latest"
                updates["version"] = "latest"

        if fid == "actual_behavior":
            if not str(value).strip():
                fallback = str(out.get("bug_description", "") or "")
                if fallback.strip():
                    out["actual_behavior"] = fallback
                    updates["actual_behavior"] = fallback

        if fid == "feature_category" and ftype == "dropdown":
            if options_list and not option_matches(str(value), options_list):
                chosen = pick_valid_option(str(value), options_list)
                out["feature_category"] = chosen
                updates["feature_category"] = chosen

    return out, updates


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
    f.write("\n" + "="*80 + "\n")
    f.write(f"[{ts}] run started\n")
    f.flush()
    sys.stdout = _Tee(sys.__stdout__, f)
    sys.stderr = _Tee(sys.__stderr__, f)

# ---------------------------
# CLI
# ---------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Auto-submit GitHub issue to iOfficeAI/AionUi (YAML-driven Issue Forms).")
    p.add_argument("--work-order", required=False, help="Path to work_order.json")
    p.add_argument("--work-order-file", required=False, help="Alias of --work-order")
    p.add_argument("--headless", action="store_true", help="Run Chrome headless")
    p.add_argument("--timeout-sec", type=int, default=30, help="Element wait timeout seconds")
    p.add_argument("--login-wait-sec", type=int, default=600, help="Max seconds to wait for manual login")
    p.add_argument("--browser-binary", default=None, help="Path to Chrome/Chromium binary if needed")
    p.add_argument("--driver-path", default=None, help="Path to chromedriver; if omitted, Selenium Manager may auto-download (requires network).")
    p.add_argument("--user-data-dir", default=None, help="Chrome user data dir to reuse login state")
    p.add_argument("--profile-dir", default=None, help="Chrome profile dir name inside user-data-dir")
    p.add_argument("--artifacts-dir", default="artifacts", help="Where to write debug artifacts")
    p.add_argument("--no-submit", action="store_true", help="Fill form but DO NOT click Create")
    p.add_argument("--pause-before-submit-sec", type=int, default=10, help="Pause after filling, before clicking Create")
    p.add_argument("--force", action="store_true", help="Ignore existing issue_number/issue_url and submit anyway")
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
        _pre = json.loads(work_order_path.read_text(encoding='utf-8'))
        if not args.force:
            existing_issue_number = str(_pre.get('issue_number') or '').strip()
            existing_issue_url = str(_pre.get('issue_url') or '').strip()
            if not existing_issue_number and existing_issue_url:
                existing_issue_number = _extract_issue_number_from_url(existing_issue_url)
            if existing_issue_number or existing_issue_url:
                msg = f"work_order.json already has issue_number={existing_issue_number!r}" if existing_issue_number else "work_order.json already has issue_url"
                print(f"{msg}, skip submission.")
                if existing_issue_url:
                    print(f"Existing issue_url: {existing_issue_url}")
                print("To submit again, clear issue_number/issue_url in work_order.json or pass --force.")
                return 0
    except Exception:
        pass

    wo = load_work_order(work_order_path)
    # Warn only for bug template (feature template doesn't have platform field).
    try:
        if wo.issue_type == "bug":
            inferred_platform = _infer_platform_default()
            if (wo.platform or "").strip() and wo.platform.strip() != inferred_platform:
                sysname = py_platform.system()
                machine = py_platform.machine()
                print(
                    f"[WARN] work_order.platform={wo.platform!r} differs from inferred={inferred_platform!r} "
                    f"(system={sysname!r}, machine={machine!r}). If you moved this work_order.json across OS, update 'platform'."
                )
    except Exception:
        pass

    # Default user-data-dir under user config dir to reduce repeated login.
    if not args.user_data_dir:
        # Persistent profile outside skill folder to avoid re-login and keep work outputs clean
        home = Path.home()
        if py_platform.system().lower().startswith('windows'):
            lad = os.environ.get('LOCALAPPDATA')
            base_dir = Path(lad) if lad else (home / '.aionui')
        else:
            base_dir = Path(os.environ.get('XDG_CONFIG_HOME', str(home / '.config')))
        args.user_data_dir = str(base_dir / 'AionUi' / 'chrome_user_data')
    ensure_dir(Path(args.user_data_dir))

    options = webdriver.ChromeOptions()
    if args.headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,900")

    options.add_argument(f"--user-data-dir={args.user_data_dir}")
    if args.profile_dir:
        options.add_argument(f"--profile-directory={args.profile_dir}")

    if args.browser_binary:
        options.binary_location = args.browser_binary

    service = ChromeService(executable_path=args.driver_path) if args.driver_path else None

    driver = None
    try:
        # NOTE: If driver_path not provided, Selenium Manager may download a driver (requires network).
        driver = webdriver.Chrome(options=options, service=service)
        wait = WebDriverWait(driver, args.timeout_sec)

        assets_templates_dir = Path(__file__).resolve().parents[2] / "assets" / "templates"
        template_filename, template_path = template_for_issue_type(wo.issue_type, assets_templates_dir)

        template_url = f"{wo.project_url}/issues/new?template={template_filename}"

        # Preflight: validate work_order.json required fields against YAML template
        raw_payload = json.loads(work_order_path.read_text(encoding="utf-8"))
        norm = normalize_work_order_dict(raw_payload)
        tpl = load_issue_template(template_path)
        template_field_ids = {str(f.get("id")) for f in all_fields_from_template(tpl) if f.get("id")}
        wb: Dict[str, Any] = {}
        # If user didn't specify these (or used "auto"), write back the auto-defaults to work_order.json.
        raw_platform = str(raw_payload.get("platform") or "").strip()
        if "platform" in template_field_ids and (not raw_platform or raw_platform.lower() in ("auto", "detect")):
            wb["platform"] = norm.get("platform", _infer_platform_default())
        if "version" in template_field_ids and not str(raw_payload.get("version") or "").strip():
            wb["version"] = norm.get("version", "latest")
        if "actual_behavior" in template_field_ids and not str(raw_payload.get("actual_behavior") or "").strip():
            ab = str(norm.get("actual_behavior") or "")
            if ab.strip():
                wb["actual_behavior"] = ab

        norm, wb2 = apply_template_defaults(tpl, norm)
        wb.update(wb2)
        _write_back_defaults_if_needed(work_order_path, wb)
        preflight_validate_required(tpl, norm, artifacts, wo.issue_type)

        # 1) Open template url
        driver.get(template_url)

        # 2) Wait for login/form ready
        wait_until_issue_form_ready(driver, template_url, login_wait_sec=args.login_wait_sec)

        # 3) Title
        title_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[aria-label='Add a title']")))
        title_input.clear()
        title_input.send_keys(wo.title)

        # 4) YAML-driven fill

        missing_required: List[str] = []

        for field in all_fields_from_template(tpl):
            fid = field.get("id")
            ftype = field_type(field)
            flabel = field_label(field)
            required = bool((field.get("validations", {}) or {}).get("required", False))
            options_list = field_options(field)

            value = norm.get(fid, "")

            # Per-template fallbacks
            if fid == "platform":
                value = pick_valid_option(str(value or wo.platform or _infer_platform_default()), options_list)
            if fid == "feature_category":
                value = pick_valid_option(str(value), options_list)
            if fid == "actual_behavior" and not str(value).strip():
                value = norm.get("bug_description", "")
            if fid == "version" and not str(value).strip():
                value = "latest"

            lab, control = find_control_by_label(driver, flabel)
            if control is None:
                if required:
                    missing_required.append(f"{flabel} (id={fid}, type={ftype}) [control not found]")
                continue

            ok = False
            try:
                if ftype == "dropdown":
                    value = pick_valid_option(str(value), options_list)
                    ok = select_dropdown_option(driver, wait, control, value)
                elif ftype in ("input", "textarea"):
                    set_text_control(control, str(value))
                    ok = bool(str(value).strip())
                else:
                    # best-effort text
                    set_text_control(control, str(value))
                    ok = bool(str(value).strip())
            except Exception:
                ok = False

            if required and not ok:
                missing_required.append(f"{flabel} (id={fid}, type={ftype})")

        if missing_required:
            print("ERROR: Missing required fields or failed to fill:")
            for m in missing_required:
                print(" -", m)
            save_debug(driver, artifacts, "missing_required")
            raise SystemExit("Missing required fields; see artifacts for details.")

        # 5) Pause to let user confirm (requested)
        pause = max(0, int(args.pause_before_submit_sec))
        if pause > 0 and not args.headless:
            print(f"Filled all fields. Pausing {pause}s before submit for review...")
            time.sleep(pause)

        if args.no_submit:
            print("NO-SUBMIT: filled the form but will not click Create.")
            save_debug(driver, artifacts, "no_submit")
            return 0

        # 6) Submit with retries
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='create-issue-button']")))
                btn.click()
            except Exception as e:
                print(f"Attempt {attempt}: failed to click Create: {e}")
                save_debug(driver, artifacts, f"create_click_fail_{attempt}")
                continue

            # wait for navigation
            for _ in range(40):  # ~20s
                time.sleep(0.5)
                cur = driver.current_url or ""
                if is_issue_created_url(cur):
                    print(f"SUCCESS: {cur}")
                    _update_work_order_file(work_order_path, cur)
                    # Post-submit wait to improve UX / allow final validation
                    if not args.headless:
                        time.sleep(10)
                    return 0

            save_debug(driver, artifacts, f"submit_attempt_{attempt}")
            print(f"Attempt {attempt}: still on create page (validation may have failed). Retrying...")

        raise SystemExit("Failed to submit after 3 attempts. See artifacts/*.png and *.html for details.")

    except SessionNotCreatedException as e:
        save_debug(driver, artifacts, "session_not_created") if driver else None
        raise SystemExit(
            "ChromeDriver 无法创建会话（常见原因：Chrome 与 ChromeDriver 主版本不匹配）。"
            " 解决：安装匹配版本的 ChromeDriver 并用 --driver-path 指定；或更新 Chrome。"
        ) from e
    except TimeoutException as e:
        save_debug(driver, artifacts, "timeout") if driver else None
        raise SystemExit(f"Timeout waiting for element/state: {e}") from e
    except WebDriverException as e:
        save_debug(driver, artifacts, "webdriver_error") if driver else None
        raise SystemExit(
            "WebDriver 启动失败：可能未安装/未找到 ChromeDriver，或网络受限导致 Selenium Manager 无法下载 driver。"
            " 解决：提供 --driver-path（推荐），或确保网络可用以便自动下载。"
        ) from e
    finally:
        with contextlib.suppress(Exception):
            if driver:
                driver.quit()


if __name__ == "__main__":
    raise SystemExit(main())
