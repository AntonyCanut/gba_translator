import importlib.util
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "clean_quote_inner_spaces_fr", REPO / "scripts" / "clean_quote_inner_spaces_fr.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
strip = mod.strip_inner_quote_spaces


class StripInnerQuoteSpacesTests(unittest.TestCase):
    def test_guillemet_inner_spaces_removed(self):
        self.assertEqual(strip("« Rejoindre Groupe »."), "«Rejoindre Groupe».")

    def test_space_before_closing_after_punct(self):
        self.assertEqual(strip("pas ! »"), "pas !»")

    def test_curly_quotes_tightened(self):
        self.assertEqual(strip("“ bonjour ”"), "“bonjour”")

    def test_straight_quote_pair_tightened(self):
        # 1st " opens, 2nd " closes; only inner spaces go.
        self.assertEqual(strip('un " OK " !'), 'un "OK" !')

    def test_straight_quote_with_placeholder(self):
        self.assertEqual(strip('Boîte "{DYNAMIC} "'), 'Boîte "{DYNAMIC}"')

    def test_already_tight_unchanged(self):
        self.assertEqual(strip('préfère "passionné".'), 'préfère "passionné".')

    def test_structural_break_preserved(self):
        # A backslash-n break right after the quote stays; only the space goes.
        self.assertEqual(strip("choisir\\n« Rejoindre"), "choisir\\n«Rejoindre")

    def test_non_quote_spaces_untouched(self):
        self.assertEqual(strip("le chat noir"), "le chat noir")

    def test_only_shortens(self):
        for s in ("« a »", 'x "y" z', "pas ! »", "“ z ”"):
            self.assertLessEqual(len(strip(s)), len(s))

    def test_no_quote_adjacent_space_remains(self):
        # After the transform, no opener is followed by a space and no
        # closer is preceded by a space.
        for s in ("« a » et « b »", 'dit " OK " puis « fin »'):
            out = strip(s)
            for op in mod.OPENERS:
                self.assertNotIn(op + " ", out)
            for cl in mod.CLOSERS:
                self.assertNotIn(" " + cl, out)


if __name__ == "__main__":
    unittest.main()
