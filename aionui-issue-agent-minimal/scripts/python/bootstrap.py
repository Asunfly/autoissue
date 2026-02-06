#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


def _find_work_order_and_args(argv: List[str]) -> Tuple[Path, List[str]]:
    if argv and not argv[0].startswith("-"):
        candidate = Path(argv[0]).expanduser()
        if candidate.is_file():
            return candidate, argv[1:]
    default_path = Path.cwd() / "work_order.json"
    return default_path, argv


def _default_user_data_dir() -> Path:
    home = Path.home()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or (home / ".aionui"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config")))
    return base / "AionUi" / "chromium_user_data"


def _ensure_venv(root: Path) -> Path:
    venv_dir = root / ".venv"
    if os.name == "nt":
        py = venv_dir / "Scripts" / "python.exe"
    else:
        py = venv_dir / "bin" / "python"
    if py.exists():
        return py
    subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])
    return py


def _in_venv() -> bool:
    return getattr(sys, "base_prefix", sys.prefix) != sys.prefix


def _install_requirements(py: Path, root: Path) -> None:
    req = root / "scripts" / "python" / "requirements.txt"
    subprocess.check_call([str(py), "-m", "pip", "install", "--upgrade", "pip"])
    subprocess.check_call([str(py), "-m", "pip", "install", "-r", str(req)])


def _install_playwright_browser(py: Path) -> None:
    if os.environ.get("SKIP_PLAYWRIGHT_INSTALL") == "1":
        print("[INFO] SKIP_PLAYWRIGHT_INSTALL=1, skip Playwright browser install.")
        return
    subprocess.check_call([str(py), "-m", "playwright", "install", "chromium"])


def _write_status(artifacts: Path, work_order: Path, code: int) -> None:
    status_name = "cmd_status.txt" if os.name == "nt" else "sh_status.txt"
    artifacts.mkdir(parents=True, exist_ok=True)
    status_path = artifacts / status_name
    status_path.write_text(
        f"exit_code={code}\nwork_order=\"{work_order}\"\nartifacts=\"{artifacts}\"\n",
        encoding="utf-8",
    )


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    work_order, extra_args = _find_work_order_and_args(sys.argv[1:])
    if not work_order.is_file():
        print(f"[ERROR] work_order.json not found: {work_order}")
        print("[HINT] Put work_order.json in your working directory, or pass its full path as the first argument.")
        return 2

    work_dir = work_order.parent
    artifacts = work_dir / "artifacts"
    user_data_dir = _default_user_data_dir()
    pause_sec = os.environ.get("PAUSE_BEFORE_SUBMIT_SEC", "10")

    if not _in_venv():
        venv_py = _ensure_venv(root)
        env = dict(os.environ)
        return subprocess.call([str(venv_py), str(Path(__file__).resolve())] + sys.argv[1:], env=env)

    venv_py = Path(sys.executable)
    _install_requirements(venv_py, root)
    _install_playwright_browser(venv_py)

    submit_script = root / "scripts" / "python" / "submit_aionui_issue.py"
    cmd = [
        str(venv_py),
        str(submit_script),
        "--work-order",
        str(work_order),
        "--artifacts-dir",
        str(artifacts),
        "--user-data-dir",
        str(user_data_dir),
    ]
    if "--pause-before-submit-sec" not in extra_args:
        cmd += ["--pause-before-submit-sec", str(pause_sec)]
    cmd += extra_args
    code = subprocess.call(cmd)
    _write_status(artifacts, work_order, code)
    if code == 0:
        print("[SUCCESS] Submission finished.")
        print("[INFO] Check work_order.json for issue_url/issue_number.")
    else:
        print(f"[FAILED] Submission failed (exit code {code}).")
        print(f"[INFO] Open \"{artifacts / 'run.log'}\" for details.")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
