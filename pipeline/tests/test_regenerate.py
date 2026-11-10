"""Tests for pipeline/regenerate.py (the single generation order) and for the workflows that must use it.

    python -m unittest discover -s pipeline/tests -v
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import regenerate as R  # noqa: E402

ROOT = R.ROOT
WORKFLOWS = ROOT / ".github" / "workflows"
ENGLISH_GENERATORS = ("build_services.py", "build_chrome.py", "build_catalog_grid.py", "build_home.py", "build_blog.py",
                      "build_plugin_pages.py", "build_feed.py")
# Node 20 pins replaced on 2026-11-09 (actions/checkout v4, actions/setup-python v5).
NODE20_PINS = ("11d5960a326750d5838078e36cf38b85af677262", "a26af69be951a213d495a4c3e4e4022e16d87065")


def order():
    return [script for script, _, _ in R.STEPS]


def workflow(name):
    return (WORKFLOWS / name).read_text(encoding="utf-8")


class OrderTest(unittest.TestCase):
    def test_every_step_exists_once(self):
        names = order()
        self.assertEqual(len(names), len(set(names)))
        for script in names:
            self.assertTrue((R.PIPELINE / script).is_file(), script)

    def test_spanish_pages_come_after_every_english_generator(self):
        i18n = order().index("build_i18n.py")
        for script in ENGLISH_GENERATORS:
            with self.subTest(script=script):
                self.assertLess(order().index(script), i18n)

    def test_blog_feed_link_is_fixed_after_the_spanish_copy(self):
        # The case of #30: build_i18n copies the English <head> into the Spanish Blog index; only
        # build_writing_feed puts the Spanish feed back.
        self.assertGreater(order().index("build_writing_feed.py"), order().index("build_i18n.py"))

    def test_search_index_reads_the_built_pages(self):
        s = order().index("build_search_index.py")
        for script in ENGLISH_GENERATORS + ("build_i18n.py", "build_writing_feed.py"):
            self.assertLess(order().index(script), s, script)

    def test_asset_hashes_go_last(self):
        self.assertEqual(order()[-1], "version_assets.py")

    def test_every_generator_is_in_the_order_or_excluded_with_a_reason(self):
        found = {p.name for p in R.PIPELINE.glob("build_*.py")} | {"version_assets.py"}
        listed, excluded = set(order()), set(R.EXCLUDED)
        self.assertEqual(listed & excluded, set())
        self.assertEqual(sorted(found - listed - excluded), [], "add it to regenerate.STEPS or EXCLUDED")
        for name, reason in R.EXCLUDED.items():
            self.assertTrue((R.PIPELINE / name).is_file(), name)
            self.assertGreater(len(reason), 20, name)


class WorkflowWiringTest(unittest.TestCase):
    def test_the_catalog_workflow_rebuilds_through_regenerate_only(self):
        text = workflow("update-catalog.yml")
        runs = re.findall(r"run:\s*python3? (pipeline/\S+)", text)
        self.assertEqual(runs.count("pipeline/regenerate.py"), 1, runs)
        self.assertEqual([r for r in runs if Path(r).name in order()], [], "a generator is run by hand again")
        self.assertLess(runs.index("pipeline/auto_update_catalog.py"), runs.index("pipeline/regenerate.py"))
        self.assertLess(runs.index("pipeline/auto_update_vscode_catalog.py"), runs.index("pipeline/regenerate.py"))

    def test_the_vscode_update_cannot_block_or_hide(self):
        text = workflow("update-catalog.yml")
        step = re.search(r"- name: Run VS Code auto-update\n(.*?)\n\n", text, re.S)
        self.assertIsNotNone(step)
        self.assertIn("id: vscode", step.group(1))
        self.assertIn("continue-on-error: true", step.group(1))
        self.assertRegex(text, r"if: always\(\) && steps\.vscode\.outcome == 'failure'")
        self.assertIn("data/vscode-catalog-data.json", re.search(r"TRACKED=\((.*?)\)", text, re.S).group(1))

    def test_a_single_workflow_writes_generated_files(self):
        self.assertFalse((WORKFLOWS / "update-vscode-catalog.yml").exists(),
                         "two writers of the same generated files cannot be reconciled by a rebase")
        writers = [p.name for p in WORKFLOWS.glob("*.yml") if "contents: write" in p.read_text(encoding="utf-8")]
        self.assertEqual(writers, ["update-catalog.yml"])

    def test_pull_requests_check_the_generated_files(self):
        text = workflow("site-checks.yml")
        self.assertIn("python3 pipeline/regenerate.py --strict --check", text)
        self.assertIn("python3 -m unittest discover -s pipeline/tests", text)
        self.assertIn("python3 _review/verify_tailwind.py", text)
        self.assertIn("npm ci --prefix pipeline --ignore-scripts", text)
        self.assertIn("pull_request:", text)
        # 2026-11-09: the browser checks run in CI too (they had gone stale when they ran only by hand)
        self.assertIn("node _review/site-behavior.test.js", text)
        self.assertIn("python3 _review/verify_site.py", text)
        # 2026-11-10: ubuntu-latest moved to an image Playwright 1.60 cannot install Chromium on; the job pins its image
        browser_job = re.search(r"\n  browser:\n(.*?)(?=\n  [a-z-]+:\n|\Z)", text, re.S)
        self.assertIsNotNone(browser_job, "site-checks.yml has no browser job")
        self.assertRegex(browser_job.group(1), r"runs-on: ubuntu-\d\d\.\d\d\b")
        # npm ci needs the lockfile in the repository, not only on disk (the first run of this check failed on that)
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "pipeline/package-lock.json"], cwd=ROOT,
                                 capture_output=True, text=True)
        self.assertEqual(tracked.returncode, 0, "pipeline/package-lock.json must be committed for npm ci")

    def test_tailwind_ignores_python_slices_and_translation_keys(self):
        # The case of 2026-11-09: text[line_start:at] and "[ctx:gh-nav-link]" in the generators became CSS rules.
        config = (R.PIPELINE / "tailwind.config.js").read_text(encoding="utf-8")
        self.assertRegex(config, r"transform:\s*\{\s*py:")
        self.assertNotIn(r"\[ctx", (ROOT / "css" / "tw.css").read_text(encoding="utf-8"))
        self.assertNotIn(r"\[line_start", (ROOT / "css" / "tw.css").read_text(encoding="utf-8"))

    def test_actions_are_pinned_to_a_full_sha_and_not_to_node20(self):
        for wf in sorted(WORKFLOWS.glob("*.yml")):
            for uses in re.findall(r"uses:\s*(\S+)", wf.read_text(encoding="utf-8")):
                with self.subTest(workflow=wf.name, uses=uses):
                    self.assertRegex(uses, r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")
                    self.assertNotIn(uses.split("@")[1], NODE20_PINS)


if __name__ == "__main__":
    unittest.main()
