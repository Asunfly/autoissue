from __future__ import annotations

import datetime
import importlib
import importlib.util
import json
import sys
import tempfile
import unittest
from itertools import product
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts" / "python"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

submit_mod = importlib.import_module("skill_submit_aionui_issue")
bootstrap_mod = importlib.import_module("skill_bootstrap")
github_payload_mod = importlib.import_module("github_mcp_build_payload")
chrome_bundle_mod = importlib.import_module("chrome_mcp_build_bundle")
upload_mod = importlib.import_module("github_mcp_upload_attachments")
support_mod = importlib.import_module("issue_payload_support")


class FakeControl:
    def __init__(self, name: str):
        self.name = name
        self.value = ""

    def click(self):
        return None

    def fill(self, value: str):
        self.value = value

    def input_value(self):
        return self.value

    def text_content(self):
        return self.value


class FakeButton:
    def __init__(self, page):
        self.page = page

    def click(self):
        self.page.handle_submit_click()


class FakeLocator:
    def __init__(self, target=None, exists: bool = True):
        self.target = target
        self.exists = exists
        self.first = self

    def fill(self, value: str):
        if not self.exists or self.target is None:
            raise AssertionError("Locator not found")
        self.target.fill(value)

    def click(self):
        if not self.exists or self.target is None:
            raise AssertionError("Locator not found")
        self.target.click()

    def input_value(self):
        if not self.exists or self.target is None:
            return ""
        return self.target.input_value()

    def text_content(self):
        if not self.exists or self.target is None:
            return ""
        return self.target.text_content()

    def count(self):
        return 1 if self.exists else 0


class FakePage:
    def __init__(
        self,
        final_issue_url: str | None = None,
        *,
        redirect_after_url_reads: int = 0,
        title_after_submit: str = "",
        heading_after_submit: str = "",
        canonical_after_submit: str = "",
        og_url_after_submit: str = "",
        body_issue_hint: str = "",
        keep_form_after_submit: bool = False,
    ):
        self._url = "https://github.com/iOfficeAI/AionUi/issues/new?template=bug_report.yml"
        self.final_issue_url = final_issue_url
        self.redirect_after_url_reads = max(0, redirect_after_url_reads)
        self.title_after_submit = title_after_submit
        self.heading_after_submit = heading_after_submit
        self.canonical_after_submit = canonical_after_submit
        self.og_url_after_submit = og_url_after_submit
        self.body_issue_hint = body_issue_hint
        self.keep_form_after_submit = keep_form_after_submit
        self.submitted = False
        self.url_reads_since_submit = 0
        self.title_control = FakeControl("title")
        self.create_button = FakeButton(self)

    @property
    def url(self):
        if self.submitted and self.final_issue_url and self._url != self.final_issue_url:
            if self.url_reads_since_submit >= self.redirect_after_url_reads:
                self._url = self.final_issue_url
            else:
                self.url_reads_since_submit += 1
        return self._url

    @url.setter
    def url(self, value):
        self._url = value

    def goto(self, *_args, **_kwargs):
        return None

    def handle_submit_click(self):
        self.submitted = True
        self.url_reads_since_submit = 0
        if self.final_issue_url and self.redirect_after_url_reads == 0:
            self._url = self.final_issue_url

    def form_visible(self) -> bool:
        return (not self.submitted) or self.keep_form_after_submit

    def locator(self, selector: str):
        if selector == "input[aria-label='Add a title']":
            return FakeLocator(self.title_control, exists=self.form_visible())
        if selector == "button[data-testid='create-issue-button']":
            return FakeLocator(self.create_button, exists=self.form_visible())
        raise AssertionError(f"Unexpected selector: {selector}")

    def screenshot(self, *_args, **_kwargs):
        return None

    def content(self):
        return "<html></html>"

    def title(self):
        if self.submitted and self.title_after_submit:
            return self.title_after_submit
        return "New issue · GitHub"

    def evaluate(self, _function: str):
        if not self.submitted:
            return {
                "canonical_url": "",
                "og_url": "",
                "heading_text": "",
                "body_issue_hint": "",
            }
        return {
            "canonical_url": self.canonical_after_submit,
            "og_url": self.og_url_after_submit,
            "heading_text": self.heading_after_submit,
            "body_issue_hint": self.body_issue_hint,
        }


class FakeContext:
    def __init__(self, page: FakePage):
        self.pages = [page]

    def set_default_timeout(self, _timeout_ms: int):
        return None

    def new_page(self):
        return self.pages[0]

    def close(self):
        return None


class FakeChromium:
    def __init__(self, page: FakePage):
        self.page = page

    def launch_persistent_context(self, *_args, **_kwargs):
        return FakeContext(self.page)


class FakePlaywright:
    def __init__(self, page: FakePage):
        self.chromium = FakeChromium(page)


class FakePlaywrightCM:
    def __init__(self, page: FakePage):
        self.page = page

    def __enter__(self):
        return FakePlaywright(self.page)

    def __exit__(self, exc_type, exc, tb):
        return False


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class WorkflowRegressionTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.session_id = "chat-20260306-01"

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def png_bytes() -> bytes:
        return (
            b"\x89PNG\r\n\x1a\n"
            b"\x00\x00\x00\rIHDR"
            b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
            b"\x1f\x15\xc4\x89"
            b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfeA\x0d\x89\x1b"
            b"\x00\x00\x00\x00IEND\xaeB`\x82"
        )

    def make_work_order(
        self,
        issue_type: str,
        work_id: str,
        with_attachment: bool = False,
        attachment_name: str = "screen.png",
        attachment_names: list[str] | None = None,
        attachment_bytes: bytes | None = None,
        attachment_outside_workspace: bool = False,
    ) -> Path:
        workspace = self.root / "issue_runs" / self.session_id / work_id
        workspace.mkdir(parents=True, exist_ok=True)
        artifacts_dir = workspace / "artifacts"
        attachment_dir = (self.root / "shared_attachments") if attachment_outside_workspace else workspace
        attachment_dir.mkdir(parents=True, exist_ok=True)
        attachment_paths: list[Path] = []
        names = attachment_names or [attachment_name]
        if with_attachment:
            for name in names:
                attachment_path = attachment_dir / name
                attachment_path.write_bytes(attachment_bytes or b"fake-png")
                attachment_paths.append(attachment_path)

        if issue_type == "bug":
            data = {
                "schema_version": "v23",
                "session_id": self.session_id,
                "work_id": work_id,
                "owner_repo": "iOfficeAI/AionUi",
                "project_url": "https://github.com/iOfficeAI/AionUi",
                "issue_type": "bug",
                "title": "【Bug】发送按钮点击后卡死 / [Bug] Freeze after Send",
                "platform": "auto",
                "version": "latest",
                "bug_description": "点击发送后界面卡死。",
                "steps_to_reproduce": "1. 打开\n2. 点击发送",
                "expected_behavior": "应出现 loading 并可继续操作。",
                "actual_behavior": "界面卡死。",
                "additional_context": "复现频率高",
                "attachments": [str(path) for path in attachment_paths] if with_attachment else [],
            }
        else:
            data = {
                "schema_version": "v23",
                "session_id": self.session_id,
                "work_id": work_id,
                "owner_repo": "iOfficeAI/AionUi",
                "project_url": "https://github.com/iOfficeAI/AionUi",
                "issue_type": "feature",
                "title": "【需求】发送时增加 loading / [Feature] Loading while sending",
                "feature_description": "发送消息时增加 loading 态。",
                "problem_statement": "当前点击发送后没有反馈。",
                "proposed_solution": "发送期间禁用按钮并显示 loading。",
                "feature_category": "UI/UX Improvement",
                "additional_context": "用于减少误触。",
                "attachments": [str(path) for path in attachment_paths] if with_attachment else [],
            }

        data.update(
            {
                "attachment_markdown": "",
                "attachment_upload_status": "none",
                "issue_number": "",
                "issue_url": "",
                "runtime": {
                    "workspace_dir": str(workspace),
                    "artifacts_dir": str(artifacts_dir),
                    "status": "draft",
                    "last_submitter": "",
                    "last_error": "",
                    "last_error_at": "",
                    "last_run_log": "",
                    "last_payload_path": "",
                    "attempt_count": 0,
                    "prepare_count": 0,
                    "submission_count": 0,
                    "updated_at": "",
                },
                "events": [],
            }
        )
        path = workspace / "work_order.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def build_controls(self, issue_type: str) -> dict[str, FakeControl]:
        if issue_type == "bug":
            labels = [
                "Platform",
                "AionUi Version",
                "Bug Description",
                "Steps to Reproduce",
                "Expected Behavior",
                "Actual Behavior",
                "Additional Context",
            ]
        else:
            labels = [
                "Feature Description",
                "Problem Statement",
                "Proposed Solution",
                "Feature Category",
                "Additional Context",
            ]
        return {label: FakeControl(label) for label in labels}

    def workspace_dir_for(self, work_order: Path) -> Path:
        return work_order.parent

    def run_submit(
        self,
        work_order: Path,
        *,
        args: list[str],
        final_issue_url: str | None = None,
        upload_markdown: str | None = None,
        should_timeout: bool = False,
        recent_issue_result=None,
        page_kwargs: dict | None = None,
    ):
        work_data = load_json(work_order)
        issue_type = work_data["issue_type"]
        controls = self.build_controls(issue_type)
        page = FakePage(final_issue_url=final_issue_url, **(page_kwargs or {}))

        def fake_find_control_by_label(_page, label):
            return None, controls[label]

        def fake_select_dropdown_option(_page, control, option_text):
            control.value = option_text
            return True

        def fake_upload_attachments(_page, control, attachment_paths, timeout_sec):
            markdown = upload_markdown or "![screen](https://github.com/user-attachments/assets/mock)"
            control.value = (control.value + "\n" + markdown).strip()
            return control.value, markdown

        wait_patch = mock.patch.object(
            submit_mod,
            "wait_until_issue_form_ready",
            side_effect=submit_mod.PlaywrightTimeoutError("timed out") if should_timeout else (lambda *_a, **_k: None),
        )

        with mock.patch.object(submit_mod, "sync_playwright", return_value=FakePlaywrightCM(page)), \
            mock.patch.object(submit_mod, "find_control_by_label", side_effect=fake_find_control_by_label), \
            mock.patch.object(submit_mod, "select_dropdown_option", side_effect=fake_select_dropdown_option), \
            mock.patch.object(submit_mod, "upload_attachments_to_control", side_effect=fake_upload_attachments), \
            mock.patch.object(submit_mod, "find_recent_issue_by_title", return_value=recent_issue_result), \
            mock.patch.object(submit_mod, "save_debug", return_value=None), \
            mock.patch.object(submit_mod.time, "sleep", return_value=None), \
            wait_patch, \
            mock.patch.object(sys, "argv", ["skill_submit_aionui_issue.py", "--work-order", str(work_order), *args]):
            if should_timeout:
                with self.assertRaises(SystemExit):
                    submit_mod.main()
            else:
                rc = submit_mod.main()
                self.assertEqual(rc, 0)

        return load_json(work_order), controls

    def run_chrome_bundle(self, work_order: Path) -> dict:
        output = work_order.parent / "chrome_bundle.json"
        with mock.patch.object(
            sys,
            "argv",
            ["chrome_mcp_build_bundle.py", "--work-order", str(work_order), "--output", str(output)],
        ):
            rc = chrome_bundle_mod.main()
            self.assertEqual(rc, 0)
        return load_json(output)

    def run_github_payload(self, work_order: Path) -> dict:
        output = work_order.parent / "github_payload.json"
        with mock.patch.object(
            sys,
            "argv",
            ["github_mcp_build_payload.py", "--work-order", str(work_order), "--output", str(output)],
        ):
            rc = github_payload_mod.main()
            self.assertEqual(rc, 0)
        return load_json(output)

    def test_skill_prepare_attachments_updates_runtime_and_history(self):
        work_order = self.make_work_order("bug", "wo-prepare-001", with_attachment=True)
        updated, controls = self.run_submit(work_order, args=["--prepare-attachments-only"])

        self.assertEqual(updated["attachment_upload_status"], "uploaded")
        self.assertIn("user-attachments", updated["attachment_markdown"])
        self.assertEqual(updated["runtime"]["status"], "attachments_prepared")
        self.assertEqual(updated["runtime"]["prepare_count"], 1)
        self.assertEqual(updated["events"][-1]["stage"], "prepare_attachments")
        self.assertEqual(updated["events"][-1]["status"], "succeeded")
        self.assertIn("user-attachments", controls["Additional Context"].value)

    def test_unsupported_attachment_is_filtered_not_blocked(self):
        work_order = self.make_work_order(
            "bug",
            "wo-filter-001",
            with_attachment=True,
            attachment_name="notes.txt",
            attachment_bytes=b"hello",
            attachment_outside_workspace=True,
        )
        updated, controls = self.run_submit(work_order, args=["--prepare-attachments-only"])

        self.assertEqual(updated["attachment_upload_status"], "listed_local")
        self.assertEqual(updated["runtime"]["status"], "attachments_prepared")
        self.assertIn("unsupported_extension:.txt", controls["Additional Context"].value)
        self.assertEqual(updated["events"][-1]["status"], "succeeded")
        self.assertEqual(
            updated["events"][-1]["extra"]["skipped_attachments"][0]["reason"],
            "unsupported_extension:.txt",
        )

    def test_skill_no_submit_records_state_without_issue_url(self):
        work_order = self.make_work_order("feature", "wo-nosubmit-001")
        updated, _controls = self.run_submit(work_order, args=["--no-submit"])

        self.assertEqual(updated["runtime"]["status"], "filled_no_submit")
        self.assertEqual(updated["issue_url"], "")
        self.assertEqual(updated["runtime"]["submission_count"], 1)
        self.assertEqual(updated["events"][-1]["status"], "filled_no_submit")

    def test_skill_submit_success_records_issue_url_and_history(self):
        work_order = self.make_work_order("bug", "wo-submit-001")
        updated, _controls = self.run_submit(
            work_order,
            args=[],
            final_issue_url="https://github.com/iOfficeAI/AionUi/issues/626",
        )

        self.assertEqual(updated["issue_number"], "626")
        self.assertEqual(updated["issue_url"], "https://github.com/iOfficeAI/AionUi/issues/626")
        self.assertEqual(updated["runtime"]["status"], "submitted")
        self.assertEqual(updated["events"][-1]["status"], "succeeded")

    def test_skill_submit_recovers_success_from_issue_title_before_url_redirect(self):
        work_order = self.make_work_order("bug", "wo-submit-title-001")
        updated, _controls = self.run_submit(
            work_order,
            args=[],
            final_issue_url="https://github.com/iOfficeAI/AionUi/issues/1605",
            page_kwargs={
                "redirect_after_url_reads": 999,
                "title_after_submit": "Issue #1605 · iOfficeAI/AionUi",
            },
        )

        self.assertEqual(updated["issue_number"], "1605")
        self.assertEqual(updated["issue_url"], "https://github.com/iOfficeAI/AionUi/issues/1605")
        self.assertEqual(updated["runtime"]["status"], "submitted")
        self.assertEqual(updated["events"][-1]["extra"]["detection_method"], "page_title")

    def test_skill_submit_uses_recent_issue_probe_before_retry(self):
        work_order = self.make_work_order("bug", "wo-submit-probe-001")
        recovered_issue = submit_mod.SubmissionSuccessInfo(
            issue_url="https://github.com/iOfficeAI/AionUi/issues/1606",
            issue_number="1606",
            detection_method="github_api_recent_exact_title",
            evidence="title match within recent issue window",
        )
        updated, _controls = self.run_submit(
            work_order,
            args=[],
            recent_issue_result=recovered_issue,
        )

        self.assertEqual(updated["issue_number"], "1606")
        self.assertEqual(updated["issue_url"], "https://github.com/iOfficeAI/AionUi/issues/1606")
        self.assertEqual(updated["events"][-1]["extra"]["detection_method"], "github_api_recent_exact_title")

    def test_extract_uploaded_attachment_markdown_keeps_all_completed_lines(self):
        before = "原始说明"
        after = "\n".join(
            [
                "原始说明",
                "![a](https://github.com/user-attachments/assets/a)",
                "<!-- Uploading \"b.png\" -->",
                "![b](https://github.com/user-attachments/assets/b)",
                "![c](https://github.com/user-attachments/assets/c)",
            ]
        )

        markdown = submit_mod._extract_uploaded_attachment_markdown(before, after)

        self.assertEqual(
            markdown,
            "\n".join(
                [
                    "![a](https://github.com/user-attachments/assets/a)",
                    "![b](https://github.com/user-attachments/assets/b)",
                    "![c](https://github.com/user-attachments/assets/c)",
                ]
            ),
        )

    def test_skill_prepare_attachments_detects_partial_multi_upload_and_falls_back(self):
        work_order = self.make_work_order(
            "bug",
            "wo-partial-upload-001",
            with_attachment=True,
            attachment_names=["1.png", "2.png", "3.png", "4.png"],
        )
        updated, controls = self.run_submit(
            work_order,
            args=["--no-submit"],
            upload_markdown="![1](https://github.com/user-attachments/assets/only-one)",
        )

        self.assertEqual(updated["attachment_upload_status"], "upload_failed")
        self.assertEqual(updated["attachment_markdown"], "")
        self.assertIn("user-attachments/assets/only-one", controls["Additional Context"].value)
        self.assertIn("`1.png`", controls["Additional Context"].value)
        self.assertIn("`4.png`", controls["Additional Context"].value)

    def test_ensure_work_order_attachments_discovers_workspace_images_only_from_allowed_dirs(self):
        work_order = self.make_work_order("bug", "wo-discover-001")
        workspace = self.workspace_dir_for(work_order)
        (workspace / "root.png").write_bytes(self.png_bytes())
        nested = workspace / "nested"
        nested.mkdir()
        (nested / "two.jpg").write_bytes(self.png_bytes())
        ignored = workspace / "artifacts"
        ignored.mkdir(exist_ok=True)
        (ignored / "debug.png").write_bytes(self.png_bytes())

        updated = support_mod.ensure_work_order_attachments(work_order)

        self.assertEqual(updated["attachments"], ["root.png", "nested/two.jpg"])

    def test_github_payload_builder_augments_work_order_attachments_before_payload(self):
        work_order = self.make_work_order("bug", "wo-discover-gh-001")
        workspace = self.workspace_dir_for(work_order)
        (workspace / "1.png").write_bytes(self.png_bytes())
        (workspace / "2.jpeg").write_bytes(self.png_bytes())
        screenshots = workspace / "screens"
        screenshots.mkdir()
        (screenshots / "3.webp").write_bytes(self.png_bytes())

        payload = self.run_github_payload(work_order)
        updated = load_json(work_order)

        self.assertIn("1.png", updated["attachments"])
        self.assertIn("2.jpeg", updated["attachments"])
        self.assertIn("screens/3.webp", updated["attachments"])
        self.assertIn("1.png", payload["body"])
        self.assertIn("screens/3.webp", payload["body"])

    def test_recent_issue_lookup_matches_exact_title_and_recency(self):
        payload = [
            {
                "number": 1400,
                "title": "别的标题",
                "html_url": "https://github.com/iOfficeAI/AionUi/issues/1400",
                "created_at": "2026-03-20T17:14:30Z",
            },
            {
                "number": 1605,
                "title": "【Bug】发送按钮点击后卡死 / [Bug] Freeze after Send",
                "html_url": "https://github.com/iOfficeAI/AionUi/issues/1605",
                "created_at": "2026-03-20T17:14:12Z",
            },
        ]
        response = mock.MagicMock()
        response.read.return_value = json.dumps(payload).encode("utf-8")
        response.__enter__.return_value = response
        response.__exit__.return_value = False

        with mock.patch.object(submit_mod.urllib.request, "urlopen", return_value=response):
            result = submit_mod.find_recent_issue_by_title(
                "iOfficeAI/AionUi",
                "【Bug】发送按钮点击后卡死 / [Bug] Freeze after Send",
                project_url="https://github.com/iOfficeAI/AionUi",
                not_before=datetime.datetime(2026, 3, 20, 17, 13, 30, tzinfo=datetime.timezone.utc),
                timeout_sec=10,
            )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.issue_number, "1605")
        self.assertEqual(result.detection_method, "github_api_recent_exact_title")

    def test_skill_failure_records_structured_error(self):
        work_order = self.make_work_order("bug", "wo-timeout-001")
        self.run_submit(work_order, args=[], should_timeout=True)
        updated = load_json(work_order)

        self.assertEqual(updated["runtime"]["status"], "failed")
        self.assertIn("Timeout", updated["runtime"]["last_error"])
        self.assertEqual(updated["events"][-1]["stage"], "playwright")
        self.assertEqual(updated["events"][-1]["status"], "failed")

    def test_duplicate_skip_records_skipped_duplicate(self):
        work_order = self.make_work_order("bug", "wo-dup-001")
        data = load_json(work_order)
        data["issue_url"] = "https://github.com/iOfficeAI/AionUi/issues/700"
        work_order.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        with mock.patch.object(sys, "argv", ["skill_submit_aionui_issue.py", "--work-order", str(work_order)]):
            rc = submit_mod.main()
            self.assertEqual(rc, 0)
        updated = load_json(work_order)
        self.assertEqual(updated["runtime"]["status"], "skipped_duplicate")
        self.assertEqual(updated["events"][-1]["status"], "skipped_duplicate")

    def test_github_payload_builder_records_payload_ready(self):
        work_order = self.make_work_order("bug", "wo-gh-001", with_attachment=True)
        payload = self.run_github_payload(work_order)
        updated = load_json(work_order)

        self.assertEqual(payload["issue_type"], "bug")
        self.assertIn("Additional Context", payload["body"])
        self.assertEqual(updated["runtime"]["status"], "payload_ready")
        self.assertEqual(updated["runtime"]["last_submitter"], "github_mcp")
        self.assertEqual(updated["events"][-1]["stage"], "payload_build")

    def test_chrome_bundle_derives_listed_local_status_for_local_only_attachments(self):
        work_order = self.make_work_order(
            "bug",
            "wo-bundle-local-001",
            with_attachment=True,
            attachment_name="notes.txt",
            attachment_bytes=b"hello",
        )

        github_payload = self.run_github_payload(work_order)
        chrome_bundle = self.run_chrome_bundle(work_order)

        self.assertEqual(github_payload["attachment_upload_status"], "listed_local")
        self.assertEqual(chrome_bundle["attachment_upload_status"], "listed_local")
        self.assertIn("unsupported_extension:.txt", github_payload["body"])

    def test_github_mcp_git_upload_writes_repo_status_and_project_scoped_paths(self):
        work_order = self.make_work_order(
            "bug",
            "wo-gh-upload-001",
            with_attachment=True,
            attachment_bytes=self.png_bytes(),
        )
        captured: dict[str, object] = {}

        def fake_upload(login, repo_name, owner_repo, work_id, file_pairs, branch="main"):
            captured["login"] = login
            captured["repo_name"] = repo_name
            captured["owner_repo"] = owner_repo
            captured["work_id"] = work_id
            captured["file_pairs"] = file_pairs
            captured["branch"] = branch
            return [
                {
                    "filename": item["filename"],
                    "remote_path": item["remote_path"],
                    "raw_url": f"https://raw.githubusercontent.com/{login}/{repo_name}/{branch}/{item['remote_path']}",
                }
                for item in file_pairs
            ]

        with mock.patch.object(upload_mod, "upload_via_git", side_effect=fake_upload), \
            mock.patch.object(
                sys,
                "argv",
                [
                    "github_mcp_upload_attachments.py",
                    "--work-order",
                    str(work_order),
                    "--login",
                    "Asunfly",
                ],
            ):
            rc = upload_mod.main()
            self.assertEqual(rc, 0)

        updated = load_json(work_order)
        self.assertEqual(captured["owner_repo"], "iOfficeAI/AionUi")
        self.assertEqual(captured["work_id"], "wo-gh-upload-001")
        self.assertEqual(captured["branch"], "main")
        self.assertEqual(
            captured["file_pairs"][0]["remote_path"],
            "iOfficeAI/AionUi/wo-gh-upload-001/screen.png",
        )
        self.assertEqual(updated["attachment_upload_method"], "repo")
        self.assertEqual(updated["attachment_upload_status"], "uploaded")
        self.assertEqual(updated["runtime"]["last_submitter"], "github_mcp")
        self.assertEqual(updated["runtime"]["status"], "attachments_uploaded")
        self.assertIn("raw.githubusercontent.com/Asunfly/issue-assets/main/iOfficeAI/AionUi/wo-gh-upload-001/screen.png", updated["attachment_markdown"])

    def test_github_mcp_git_upload_rejects_base64_text_images(self):
        work_order = self.make_work_order(
            "bug",
            "wo-gh-upload-text-001",
            with_attachment=True,
            attachment_bytes=b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB",
        )

        with mock.patch.object(
            sys,
            "argv",
            [
                "github_mcp_upload_attachments.py",
                "--work-order",
                str(work_order),
                "--login",
                "Asunfly",
            ],
        ):
            rc = upload_mod.main()
            self.assertEqual(rc, 1)

        updated = load_json(work_order)
        self.assertEqual(updated["runtime"]["status"], "failed")
        self.assertIn("valid binary image", updated["runtime"]["last_error"])
        self.assertEqual(updated["events"][-1]["status"], "failed")

    def test_independent_submitter_artifacts_for_two_issue_scenarios(self):
        issue_paths = [
            self.make_work_order("bug", "wo-bundle-bug-001", with_attachment=True),
            self.make_work_order("feature", "wo-bundle-feature-001"),
        ]

        for work_order in issue_paths:
            with self.subTest(work_order=work_order.name, submitter="chrome_mcp"):
                bundle = self.run_chrome_bundle(work_order)
                updated = load_json(work_order)
                self.assertEqual(bundle["submitter"], "chrome_mcp")
                self.assertEqual(bundle["work_id"], updated["work_id"])
                self.assertEqual(updated["runtime"]["last_submitter"], "chrome_mcp")
                self.assertEqual(updated["runtime"]["status"], "chrome_bundle_ready")

            with self.subTest(work_order=work_order.name, submitter="github_mcp"):
                payload = self.run_github_payload(work_order)
                updated = load_json(work_order)
                self.assertEqual(payload["issue_type"], updated["issue_type"])
                self.assertEqual(updated["runtime"]["last_submitter"], "github_mcp")
                self.assertEqual(updated["runtime"]["status"], "payload_ready")

    def test_switch_matrix_same_issue_and_cross_issue_keeps_isolation(self):
        methods = ["skill", "chrome_mcp", "github_mcp"]

        for first, second in product(methods, repeat=2):
            with self.subTest(scope="same_issue", first=first, second=second):
                work_order = self.make_work_order("bug", f"wo-switch-same-{first}-{second}", with_attachment=True)
                self._simulate_nonfinal_method(work_order, first)
                self._simulate_nonfinal_method(work_order, second)
                updated = load_json(work_order)
                self.assertEqual(updated["work_id"], f"wo-switch-same-{first}-{second}")
                self.assertEqual(updated["session_id"], self.session_id)
                self.assertGreaterEqual(len(updated["events"]), 2)

            with self.subTest(scope="cross_issue", first=first, second=second):
                issue_a = self.make_work_order("bug", f"wo-switch-a-{first}-{second}", with_attachment=True)
                issue_b = self.make_work_order("feature", f"wo-switch-b-{first}-{second}")
                self._simulate_nonfinal_method(issue_a, first)
                self._simulate_nonfinal_method(issue_b, second)
                updated_a = load_json(issue_a)
                updated_b = load_json(issue_b)
                self.assertNotEqual(updated_a["work_id"], updated_b["work_id"])
                self.assertEqual(updated_a["session_id"], updated_b["session_id"])
                self.assertNotEqual(updated_a["runtime"]["workspace_dir"], updated_b["runtime"]["workspace_dir"])

    def test_bootstrap_records_process_structure(self):
        work_order = self.make_work_order("bug", "wo-bootstrap-001")
        with mock.patch.object(bootstrap_mod, "_in_venv", return_value=True), \
            mock.patch.object(bootstrap_mod, "_install_requirements", return_value=None), \
            mock.patch.object(bootstrap_mod, "_install_playwright_browser", return_value=True), \
            mock.patch.object(bootstrap_mod.subprocess, "call", return_value=0), \
            mock.patch.object(sys, "argv", ["skill_bootstrap.py", str(work_order)]):
            rc = bootstrap_mod.main()
            self.assertEqual(rc, 0)

        updated = load_json(work_order)
        self.assertEqual(updated["runtime"]["status"], "bootstrap_succeeded")
        stages = [event["stage"] for event in updated["events"]]
        self.assertIn("bootstrap", stages)

    def test_bootstrap_respects_equals_form_pause_and_user_data_overrides(self):
        work_order = self.make_work_order("bug", "wo-bootstrap-overrides-001")
        captured = {}

        def fake_call(cmd, *args, **kwargs):
            captured["cmd"] = cmd
            return 0

        with mock.patch.object(bootstrap_mod, "_in_venv", return_value=True), \
            mock.patch.object(bootstrap_mod, "_install_requirements", return_value=None), \
            mock.patch.object(bootstrap_mod, "_install_playwright_browser", return_value=True), \
            mock.patch.object(bootstrap_mod.subprocess, "call", side_effect=fake_call), \
            mock.patch.object(
                sys,
                "argv",
                [
                    "skill_bootstrap.py",
                    str(work_order),
                    "--user-data-dir=/tmp/custom-user-data",
                    "--pause-before-submit-sec=5",
                ],
            ):
            rc = bootstrap_mod.main()
            self.assertEqual(rc, 0)

        cmd = captured["cmd"]
        self.assertEqual(sum(1 for arg in cmd if arg.startswith("--user-data-dir")), 1)
        self.assertEqual(sum(1 for arg in cmd if arg.startswith("--pause-before-submit-sec")), 1)
        self.assertIn("--user-data-dir=/tmp/custom-user-data", cmd)
        self.assertIn("--pause-before-submit-sec=5", cmd)

    def test_bootstrap_module_cold_import_does_not_require_issue_payload_support(self):
        bootstrap_path = SCRIPTS_DIR / "skill_bootstrap.py"
        module_name = "bootstrap_cold_import_test"
        spec = importlib.util.spec_from_file_location(module_name, bootstrap_path)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        original_module = sys.modules.pop("issue_payload_support", None)
        trimmed_sys_path = [p for p in sys.path if p != str(SCRIPTS_DIR)]
        try:
            with mock.patch.object(sys, "path", trimmed_sys_path):
                assert spec.loader is not None
                spec.loader.exec_module(module)
        finally:
            sys.modules.pop(module_name, None)
            if original_module is not None:
                sys.modules["issue_payload_support"] = original_module
        self.assertTrue(callable(module.main))

    def _simulate_nonfinal_method(self, work_order: Path, submitter: str):
        if submitter == "skill":
            self.run_submit(work_order, args=["--no-submit"])
        elif submitter == "chrome_mcp":
            self.run_chrome_bundle(work_order)
        else:
            self.run_github_payload(work_order)


if __name__ == "__main__":
    unittest.main()
