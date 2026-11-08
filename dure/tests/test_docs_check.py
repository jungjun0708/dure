from __future__ import annotations

import importlib.util
import datetime as dt
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPOSITORY_ROOT / "scripts" / "check_docs.py"
SPEC = importlib.util.spec_from_file_location("dure_docs_check", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
DOCS_CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DOCS_CHECK)


class DocumentationLinkCheckTests(unittest.TestCase):
    def _run_cli(self, root: Path, today: str, *args: str):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(root), "--today", today, *args],
            capture_output=True,
            encoding="utf-8",
            check=False,
        )

    def test_accepts_existing_relative_markdown_and_image_links(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "docs" / "assets").mkdir(parents=True)
            (root / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
            (root / "docs" / "assets" / "diagram.png").write_bytes(b"png")
            (root / "README.md").write_text(
                "[guide](docs/guide.md)\n![diagram](docs/assets/diagram.png)\n",
                encoding="utf-8",
            )

            self.assertEqual(DOCS_CHECK.check_relative_links(root), [])

    def test_reports_a_missing_relative_link(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "docs").mkdir()
            (root / "README.md").write_text(
                "[missing](docs/missing.md)\n", encoding="utf-8"
            )

            errors = DOCS_CHECK.check_relative_links(root)

        self.assertEqual(len(errors), 1)
        self.assertIn("README.md:1", errors[0])
        self.assertIn("docs/missing.md", errors[0])

    def test_checks_root_policy_and_nested_dure_documentation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "dure" / "docs").mkdir(parents=True)
            (root / "README.md").write_text("# Root\n", encoding="utf-8")
            (root / "GOVERNANCE.md").write_text(
                "[missing](missing.md)\n", encoding="utf-8"
            )
            (root / "dure" / "README.md").write_text(
                "[guide](docs/guide.md)\n", encoding="utf-8"
            )
            (root / "dure" / "docs" / "guide.md").write_text(
                "# Guide\n", encoding="utf-8"
            )

            errors = DOCS_CHECK.check_relative_links(root)

        self.assertEqual(len(errors), 1)
        self.assertIn("GOVERNANCE.md:1", errors[0])
        self.assertIn("missing.md", errors[0])

    def test_reports_missing_anchor_and_duplicate_heading(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "docs").mkdir()
            (root / "README.md").write_text(
                "[missing](docs/guide.md#nope)\n", encoding="utf-8"
            )
            (root / "docs" / "guide.md").write_text(
                "# Same\n\n## Same\n", encoding="utf-8"
            )

            errors = DOCS_CHECK.check_relative_links(root) + DOCS_CHECK.check_duplicate_headings(root)

        self.assertEqual(len(errors), 2)
        self.assertIn("missing anchor nope", errors[0])
        self.assertIn("duplicate heading anchor same", errors[1])

    def test_reports_stale_explicit_document_date(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "README.md").write_text(
                "# Guide\n\n기준일: 2026-01-01\n", encoding="utf-8"
            )

            warnings = DOCS_CHECK.check_document_freshness(
                root, today=dt.date(2026, 7, 22), max_age_days=90
            )

        self.assertEqual(len(warnings), 1)
        self.assertIn("older than 90 days", warnings[0])

    def test_cli_document_age_only_produces_warnings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "README.md").write_text(
                "# Guide\n\n작성일: 2026-01-01\n", encoding="utf-8"
            )
            cases = (
                ("2026-04-01", (), False),  # Exactly 90 days old.
                ("2026-04-02", (), True),
                ("2026-01-03", ("--max-document-age-days", "1"), True),
            )
            for today, args, should_warn in cases:
                with self.subTest(today=today, args=args):
                    result = self._run_cli(root, today, *args)

                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("documentation links: OK", result.stdout)
                    if should_warn:
                        self.assertIn("warning: README.md:3: document date", result.stderr)
                    else:
                        self.assertEqual(result.stderr, "")

    def test_cli_link_errors_still_fail_alongside_age_warnings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "guide.md").write_text("# Guide\n", encoding="utf-8")
            cases = (
                ("missing.md", "missing relative link missing.md"),
                ("guide.md#missing", "missing anchor missing"),
            )
            for target, expected_error in cases:
                with self.subTest(target=target):
                    (root / "README.md").write_text(
                        f"# Home\n\n기준일: 2026-01-01\n\n[guide]({target})\n",
                        encoding="utf-8",
                    )
                    result = self._run_cli(root, "2026-04-02")

                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertIn("warning: README.md:3: document date", result.stderr)
                    self.assertIn(expected_error, result.stderr)
                    self.assertNotIn("documentation links: OK", result.stdout)

    def test_requires_current_package_evidence_and_release_references(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dure = root / "dure"
            (dure / "docs" / "release-evidence").mkdir(parents=True)
            (dure / "pyproject.toml").write_text(
                '[project]\nversion = "1.2.3"\n', encoding="utf-8"
            )
            (dure / "CHANGELOG.md").write_text(
                "## 1.2.3 — 소스 기준선\n", encoding="utf-8"
            )
            (dure / "docs" / "roadmap.md").write_text(
                "현재 릴리스 메타데이터: `1.2.3`\n", encoding="utf-8"
            )
            (dure / "docs" / "release-evidence" / "README.md").write_text(
                "현재 source metadata `1.2.3`\n", encoding="utf-8"
            )
            (dure / "docs" / "release-evidence" / "v1.2.3.md").write_text(
                "# v1.2.3 수용 증적\n\n`NOT_RUN`\n", encoding="utf-8"
            )

            errors = DOCS_CHECK.check_release_documentation_contract(root)

        self.assertEqual(errors, [])

    def test_reports_release_or_bootstrap_documentation_contract_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dure = root / "dure"
            (dure / "docs").mkdir(parents=True)
            (dure / "pyproject.toml").write_text(
                '[project]\nversion = "1.2.3"\n', encoding="utf-8"
            )
            (dure / "src" / "dure").mkdir(parents=True)
            (dure / "src" / "dure" / "cli.py").write_text(
                "Compatibility flag; --apply already includes the required Docker restart\n",
                encoding="utf-8",
            )
            (dure / "docs" / "cli-reference.md").write_text("old docs\n", encoding="utf-8")

            release_errors = DOCS_CHECK.check_release_documentation_contract(root)
            cli_errors = DOCS_CHECK.check_bootstrap_cli_contract(root)

        self.assertTrue(any("missing current release evidence" in error for error in release_errors))
        self.assertEqual(len(cli_errors), 1)
        self.assertIn("does not match", cli_errors[0])
