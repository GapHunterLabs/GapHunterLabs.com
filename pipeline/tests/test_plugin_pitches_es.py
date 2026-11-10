"""Spanish plugin descriptions (pipeline/i18n/plugin-pitches.es.json) and how build_i18n uses them.

    python -m unittest discover -s pipeline/tests -v
"""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_i18n as I  # noqa: E402
from build_plugin_pages import pitch_prose, DESC_MAX  # noqa: E402

ROOT = I.ROOT
STORED = json.loads(I.PITCHES_FILE.read_text(encoding="utf-8"))


def data_keys():
    jb = json.loads((ROOT / "data" / "catalog-data.json").read_text(encoding="utf-8"))["plugins"]
    vs = json.loads((ROOT / "data" / "vscode-catalog-data.json").read_text(encoding="utf-8"))["extensions"]
    return ({"jetbrains:" + p["repo"]: p["pitch"] for p in jb} | {"vscode:" + e["name"]: e["pitch"] for e in vs})


class TranslationFileTest(unittest.TestCase):
    def test_every_plugin_has_a_current_translation(self):
        keys = data_keys()
        self.assertEqual(sorted(set(keys) - set(STORED)), [], "plugins without a Spanish description")
        stale = [k for k, p in keys.items() if k in STORED and STORED[k]["en"] != pitch_prose(p).strip()]
        self.assertEqual(stale, [], "English description changed: translate it again")
        self.assertEqual(I._pitch_tables()[2], [])

    def test_links_and_bold_survive_the_translation(self):
        for k, v in STORED.items():
            with self.subTest(plugin=k):
                self.assertEqual(re.findall(r"\]\((https?://[^)]+)\)", v["en"]), re.findall(r"\]\((https?://[^)]+)\)", v["es"]))
                self.assertEqual(v["en"].count("**"), v["es"].count("**"))
                self.assertTrue(v["es"].strip())
                self.assertNotEqual(v["es"].strip(), v["en"].strip())

    def test_meta_descriptions_fit(self):
        for path in I._pitch_tables()[0]:
            with self.subTest(page=path):
                d = I.pitch_description_es(path)
                self.assertLessEqual(len(d), DESC_MAX)
                self.assertGreater(len(d), 30)

    def test_unknown_page_has_no_description(self):
        self.assertIsNone(I.pitch_description_es("/catalog/no-such-plugin/"))


class TranslatePitchesTest(unittest.TestCase):
    def test_known_block_is_replaced(self):
        (cls, en_html), es_html = next(iter(I._pitch_tables()[1].items()))
        missing = {}
        out = I.translate_pitches('<p class="%s">%s</p>' % (cls, en_html), "/x/", missing)
        self.assertEqual(out, '<p class="%s">%s</p>' % (cls, es_html))
        self.assertEqual(missing, {})

    def test_unknown_block_is_reported_and_kept(self):
        missing = {}
        html = '<p class="card-pitch">An English text nobody translated.</p>'
        self.assertEqual(I.translate_pitches(html, "/es/x/", missing), html)
        self.assertEqual(len(missing), 1)

    def test_placeholder_and_other_classes_are_ignored(self):
        missing = {}
        html = '<p class="ph-lead">—</p><p class="card-pitch"></p><p class="lead">Plain English.</p>'
        self.assertEqual(I.translate_pitches(html, "/es/x/", missing), html)
        self.assertEqual(missing, {})


class SpanishPagesTest(unittest.TestCase):
    def test_no_spanish_page_keeps_an_english_description(self):
        # The case of 2026-11-09: lead and meta were Spanish, but the JSON-LD of 102 plugin pages kept the English text.
        english = [k[1][:50] for k in I._pitch_tables()[1] if k[0] == "jsonld" and len(k[1]) > 20]
        english += [d[:50] for d in I._jsonld_descriptions()]
        pages = sorted((ROOT / "es").rglob("index.html"))
        self.assertGreater(len(pages), 150)
        bad = [str(p.relative_to(ROOT)) for p in pages if any(e in p.read_text(encoding="utf-8") for e in english)]
        self.assertEqual(bad, [])

    def test_spanish_plugin_page_reads_in_spanish(self):
        page = (ROOT / "es" / "catalogo" / "ansible-companion" / "index.html").read_text(encoding="utf-8")
        es = STORED["jetbrains:ansible-companion"]["es"]
        self.assertIn("Cifra y descifra Ansible Vault", page)
        self.assertNotIn("Encrypt and decrypt Ansible Vault", page)
        self.assertIn('<meta name="description" content="Cifra y descifra', page)
        self.assertTrue(es.startswith("**Cifra"))


if __name__ == "__main__":
    unittest.main()
