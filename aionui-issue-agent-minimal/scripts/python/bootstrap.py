#!/usr/bin/env python3
from __future__ import annotations

import os
import platform as py_platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple


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
    if os.environ.get("BOOTSTRAP_UPGRADE_PIP") == "1":
        subprocess.check_call([str(py), "-m", "pip", "install", "--upgrade", "pip"])
    subprocess.check_call([str(py), "-m", "pip", "install", "-r", str(req)])


def _apply_playwright_platform_override_for_macos_arm64() -> None:
    """
    Work around Playwright host-platform detection issues on some macOS arm64 environments.
    In restricted/sandboxed environments, Node may report cpu.model without "Apple",
    causing Playwright to resolve to mac-x64 executable paths.
    """
    if sys.platform != "darwin":
        return
    if os.environ.get("PLAYWRIGHT_HOST_PLATFORM_OVERRIDE"):
        return
    machine = (py_platform.machine() or "").lower()
    if machine not in ("arm64", "aarch64"):
        return
    try:
        kernel_major = int((py_platform.release() or "").split(".")[0])
    except Exception:
        kernel_major = 24
    if kernel_major < 18:
        override = "mac10.13-arm64"
    elif kernel_major == 18:
        override = "mac10.14-arm64"
    elif kernel_major == 19:
        override = "mac10.15-arm64"
    else:
        # Keep aligned with Playwright's current LAST_STABLE_MACOS_MAJOR_VERSION=15 behavior.
        mac_major = min(max(kernel_major - 9, 11), 15)
        override = f"mac{mac_major}-arm64"
    os.environ["PLAYWRIGHT_HOST_PLATFORM_OVERRIDE"] = override
    print(f"[INFO] Set PLAYWRIGHT_HOST_PLATFORM_OVERRIDE={override} for macOS arm64.")


def _install_playwright_browser(py: Path) -> bool:
    if os.environ.get("SKIP_PLAYWRIGHT_INSTALL") == "1":
        print("[INFO] SKIP_PLAYWRIGHT_INSTALL=1, skip Playwright browser install.")
        return True

    try:
        retries = max(1, int(os.environ.get("PLAYWRIGHT_INSTALL_RETRIES", "3")))
    except ValueError:
        retries = 3
    try:
        base_delay = max(1.0, float(os.environ.get("PLAYWRIGHT_INSTALL_RETRY_DELAY_SEC", "2")))
    except ValueError:
        base_delay = 2.0
    try:
        timeout_sec = max(30, int(os.environ.get("PLAYWRIGHT_INSTALL_TIMEOUT_SEC", "240")))
    except ValueError:
        timeout_sec = 240
    cmd = [str(py), "-m", "playwright", "install", "chromium"]

    for attempt in range(1, retries + 1):
        try:
            subprocess.check_call(cmd, timeout=timeout_sec)
            return True
        except subprocess.TimeoutExpired:
            if attempt >= retries:
                print(
                    f"[WARN] Playwright browser install timed out after {timeout_sec}s "
                    f"(attempt {attempt}/{retries})."
                )
                return False
            wait_sec = int(base_delay * (2 ** (attempt - 1)))
            print(
                f"[WARN] Playwright browser install timed out after {timeout_sec}s "
                f"(attempt {attempt}/{retries}), retry in {wait_sec}s..."
            )
            time.sleep(wait_sec)
        except subprocess.CalledProcessError as e:
            if attempt >= retries:
                print(f"[WARN] Playwright browser install failed after {retries} attempts: {e}")
                return False
            wait_sec = int(base_delay * (2 ** (attempt - 1)))
            print(f"[WARN] Playwright browser install failed (attempt {attempt}/{retries}), retry in {wait_sec}s...")
            time.sleep(wait_sec)

    return False


def _detect_system_browser_binary() -> Optional[str]:
    if os.name == "nt":
        candidates = []
        for base in [os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")]:
            if not base:
                continue
            candidates.extend(
                [
                    Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe",
                    Path(base) / "Chromium" / "Application" / "chrome.exe",
                ]
            )
        for p in candidates:
            if p.is_file():
                return str(p)
        return None

    if sys.platform == "darwin":
        for p in [
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        ]:
            if p.is_file():
                return str(p)
        return None

    for name in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"]:
        p = shutil.which(name)
        if p:
            return p
    return None


def _write_status(artifacts: Path, work_order: Path, code: int) -> None:
    status_name = "cmd_status.txt" if os.name == "nt" else "sh_status.txt"
    artifacts.mkdir(parents=True, exist_ok=True)
    status_path = artifacts / status_name
    status_path.write_text(
        f"exit_code={code}\nwork_order=\"{work_order}\"\nartifacts=\"{artifacts}\"\n",
        encoding="utf-8",
    )


def _extract_cli_value(args: List[str], key: str) -> Optional[str]:
    for index, arg in enumerate(args):
        if arg == key and index + 1 < len(args):
            return args[index + 1]
        if arg.startswith(f"{key}="):
            return arg.split("=", 1)[1]
    return None


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
    _apply_playwright_platform_override_for_macos_arm64()
    _install_requirements(venv_py, root)
    browser_ready = _install_playwright_browser(venv_py)
    fallback_browser = None
    if not browser_ready:
        fallback_browser = _detect_system_browser_binary()
        if fallback_browser:
            print(f"[WARN] Fallback to system browser binary: {fallback_browser}")
        else:
            print("[ERROR] Playwright browser install failed and no system browser binary found.")
            print("[HINT] Retry with network, or set SKIP_PLAYWRIGHT_INSTALL=1 after preinstalling Playwright browsers.")
            return 1

    artifacts_override = _extract_cli_value(extra_args, "--artifacts-dir")
    final_artifacts = artifacts
    if artifacts_override:
        override_path = Path(artifacts_override)
        final_artifacts = override_path if override_path.is_absolute() else (work_dir / override_path)

    submit_script = root / "scripts" / "python" / "submit_aionui_issue.py"
    cmd = [
        str(venv_py),
        str(submit_script),
        "--work-order",
        str(work_order),
        "--user-data-dir",
        str(user_data_dir),
    ]
    has_artifacts_arg = any(a == "--artifacts-dir" or a.startswith("--artifacts-dir=") for a in extra_args)
    if not has_artifacts_arg:
        cmd += ["--artifacts-dir", str(artifacts)]
    has_browser_binary_arg = any(a == "--browser-binary" or a.startswith("--browser-binary=") for a in extra_args)
    if fallback_browser and not has_browser_binary_arg:
        cmd += ["--browser-binary", fallback_browser]
    if "--pause-before-submit-sec" not in extra_args:
        cmd += ["--pause-before-submit-sec", str(pause_sec)]
    cmd += extra_args
    code = subprocess.call(cmd)
    _write_status(final_artifacts, work_order, code)
    if code == 0:
        print("[SUCCESS] Submission finished.")
        print("[INFO] Check work_order.json for issue_url/issue_number.")
    else:
        print(f"[FAILED] Submission failed (exit code {code}).")
        print(f"[INFO] Open \"{final_artifacts / 'run.log'}\" for details.")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
