"""The site repository was renamed from GapHunterLabs/GapHunterLabs.github.io to GapHunterLabs/GapHunterLabs.com on
2026-11-09. GitHub redirects the old URL only while no repository takes the old name again, so nothing the site
serves may link to it (the contact form opened issues there).

    python -m unittest discover -s pipeline/tests -v
"""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD = "github.com/GapHunterLabs/GapHunterLabs.github.io"


class RepoNameTest(unittest.TestCase):
    def test_no_served_file_links_the_old_repository(self):
        out = subprocess.run(["git", "grep", "-l", "-I", "-i", "-F", OLD, "--", "*.html", "*.js", "*.json", "*.xml", "*.txt"],
                             cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertIn(out.returncode, (0, 1), out.stderr)       # 1 = no match
        self.assertEqual(out.stdout.split(), [], "link the renamed repository, GapHunterLabs/GapHunterLabs.com")

    def test_the_contact_form_opens_issues_in_the_current_repository(self):
        js = (ROOT / "js" / "contact.js").read_text(encoding="utf-8")
        self.assertIn("'https://github.com/GapHunterLabs/GapHunterLabs.com/issues/new'", js)


if __name__ == "__main__":
    unittest.main()
