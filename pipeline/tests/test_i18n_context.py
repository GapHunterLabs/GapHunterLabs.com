"""Tests for contextual keys in pipeline/i18n/es.json ("[ctx:<class>] <text>"), as applied by build_i18n.

A contextual key translates a text only inside an element that has that class, and wins over the plain key there.
The header link "Sponsors" must read "Patrocinio" to fit the header, while the sponsor wall headings keep
"Patrocinadores".

    python -m unittest discover -s pipeline/tests -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_i18n as bi  # noqa: E402

TABLE = {
    "Sponsors": "Patrocinadores",
    "[ctx:gh-nav-link] Sponsors": "Patrocinio",
    "[ctx:gh-nav-link] Plugins": "Herramientas",
    "[ctx:gh-nav-link] {n} new": "{n} nuevos",
    "Methodology": "Metodología",
}


def run(html, table=TABLE):
    missing, used = {}, set()
    out = bi.translate(html, table, missing, "/test/", used)
    return out, missing, used


class ContextualLookupTest(unittest.TestCase):
    def test_contextual_key_applies_only_inside_the_class(self):
        out, missing, used = run('<nav><a class="gh-nav-link" href="/s/">Sponsors</a></nav><h2>Sponsors</h2>')
        self.assertIn('>Patrocinio</a>', out)
        self.assertIn('<h2>Patrocinadores</h2>', out)
        self.assertEqual(missing, {})
        self.assertEqual(used, {"[ctx:gh-nav-link] Sponsors"})

    def test_class_among_several_and_in_any_order(self):
        for cls in ("gh-nav-link is-active", "is-active gh-nav-link", "a gh-nav-link b"):
            with self.subTest(cls=cls):
                out, _, _ = run('<a class="%s" href="/s/">Sponsors</a>' % cls)
                self.assertIn('>Patrocinio</a>', out)

    def test_similar_class_names_do_not_match(self):
        for cls in ("gh-nav-linkx", "gh-nav", "nav-link", "GH-NAV-LINK"):
            with self.subTest(cls=cls):
                out, _, used = run('<a class="%s" href="/s/">Sponsors</a>' % cls)
                self.assertIn('>Patrocinadores</a>', out)
                self.assertEqual(used, set())

    def test_no_class_attribute_uses_the_plain_key(self):
        out, _, _ = run('<p>Sponsors</p>')
        self.assertIn('<p>Patrocinadores</p>', out)

    def test_contextual_only_text_is_missing_everywhere_else(self):
        # "Plugins" has no plain key on purpose: outside the header it must get its own translation.
        out, missing, _ = run('<a class="gh-nav-link" href="/c/">Plugins</a><h3>Plugins</h3>')
        self.assertIn('>Herramientas</a>', out)
        self.assertIn('<h3>Plugins</h3>', out)
        self.assertEqual(set(missing), {"Plugins"})

    def test_loose_text_in_a_mixed_block_gets_no_context(self):
        # The loose text belongs to no element of its own, so the div's class must not apply to it.
        out, _, used = run('<div class="gh-nav-link">Sponsors<p>Methodology</p></div>')
        self.assertIn('Patrocinadores<p>Metodología</p>', out)
        self.assertEqual(used, set())

    def test_numbers_are_normalized_before_the_contextual_lookup(self):
        out, missing, used = run('<span class="gh-nav-link">12 new</span>')
        self.assertIn('>12 nuevos</span>', out)
        self.assertEqual(missing, {})
        self.assertEqual(used, {"[ctx:gh-nav-link] {n} new"})

    def test_attributes_keep_plain_keys(self):
        # Contextual keys are for element text; an aria-label on the same element still uses the plain table.
        out, _, _ = run('<a class="gh-nav-link" aria-label="Sponsors" href="/s/">Sponsors</a>')
        self.assertIn('aria-label="Patrocinadores"', out)
        self.assertIn('>Patrocinio</a>', out)


class TableChecksTest(unittest.TestCase):
    def assertRejected(self, table, expected):
        with self.assertRaises(SystemExit) as caught:
            bi.check_table(table)
        self.assertIn(expected, str(caught.exception.code))

    def test_valid_tables_pass(self):
        bi.check_table(TABLE)
        bi.check_table({})
        # "::" is ordinary text (Class::method); it was the first separator choice and must stay a plain key.
        bi.check_table({"Memory leak via ProjectRootManagerImpl::rootsChanged": "Fuga de memoria"})

    def test_malformed_contextual_keys_are_named(self):
        for key in ("[ctx:] Plugins", "[ctx:GH-Nav] Plugins", "[ctx:gh-nav-link]Plugins", "[ctx:gh-nav-link] ",
                    "[ctx:gh nav] Plugins", "[ctx:gh-nav-link Plugins", "[ctx:-gh] Plugins"):
            with self.subTest(key=key):
                self.assertRejected({key: "Herramientas"}, repr(key[:60]))

    def test_contextual_key_without_translation(self):
        for value in ("", "   "):
            with self.subTest(value=repr(value)):
                self.assertRejected({"[ctx:gh-nav-link] Plugins": value}, "without a translation")

    def test_stale_contextual_keys(self):
        self.assertEqual(bi.stale_context_keys(TABLE, {"[ctx:gh-nav-link] Sponsors"}),
                         ["[ctx:gh-nav-link] Plugins", "[ctx:gh-nav-link] {n} new"])
        self.assertEqual(bi.stale_context_keys(TABLE, set(k for k in TABLE if k.startswith("[ctx:"))), [])
        self.assertEqual(bi.stale_context_keys({"Sponsors": "Patrocinadores"}, set()), [])


if __name__ == "__main__":
    unittest.main()
