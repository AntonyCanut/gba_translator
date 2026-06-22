"""Regression guard for the arrow-at-line-start rule across ALL game dialogue.

Pokemon Unbound world-map / route sign panels point at a destination with a
directional arrow glyph (0x79 ↑, 0x7A ↓, 0x7B ←, 0x7C →). In the English source
every sign arrow sits at the START of a line — first byte, or right after a
line-break code (\\n 0xFE, \\l 0xFA, \\p 0xFB). Machine translation sometimes
buried the arrow mid-line or swapped it with the line break, so the rendered
sign lost its arrow / line breaks (parent ticket P-68).

B-74 fixed the worldmap cluster and most road panels; this suite makes the rule
hold for *every* dialogue, not just the panels B-74 happened to touch. The check
is English-grounded: only offsets whose English original is itself a panel are
required to keep their French arrows at line start, which automatically excludes
inline colored arrow icons in prose, control-code headers and non-text data
(their English arrows are mid-line too).

Pure-logic tests run everywhere; the corpus test needs the bundled English ROM
and skips cleanly when it is absent.
"""

import unittest
from pathlib import Path

from scripts import audit_arrow_line_start_fr as audit

REPO_ROOT = Path(__file__).resolve().parent.parent
COMBINED = REPO_ROOT / "combined_fr.txt"
ENGLISH_ROM = REPO_ROOT / "input/roms/englishrom.gba"

# Panels B-74 missed and this ticket fixed — must now be arrow-clean.
FIXED_OFFSETS = [0x741AF1, 0x7B8908, 0x7E6B88, 0x1F721EC, 0x1F72353]


class ArrowLineStartLogicTests(unittest.TestCase):
    """Pure tokeniser checks — no ROM required."""

    def test_first_byte_arrow_is_line_start(self):
        self.assertEqual(audit.find_misplaced_arrows(r"<0x7C> Antisis"), [])

    def test_arrow_after_break_is_line_start(self):
        for brk in (r"\n", r"\l", r"\p"):
            self.assertEqual(
                audit.find_misplaced_arrows(f"Route 9{brk}<0x79> Mont Givre"), [],
                f"arrow after {brk} should be a line start",
            )

    def test_arrow_after_text_is_misplaced(self):
        bad = audit.find_misplaced_arrows(r"Route 16 <0x7C>\nVille Portuaire")
        self.assertEqual([b for b, _ in bad], [0x7C])

    def test_arrow_before_break_is_misplaced(self):
        # arrow sitting at the END of a line (just before the break) is wrong
        bad = audit.find_misplaced_arrows(r"Ville de Tehl <0x79>\nVoie Auburn")
        self.assertEqual([b for b, _ in bad], [0x79])

    def test_inline_icon_between_color_codes_is_flagged_by_source_only(self):
        # Source-only the inline icon looks misplaced; English grounding is what
        # exonerates it (see ArrowLineStartCorpusTests).
        bad = audit.find_misplaced_arrows(r"Une {COLOR}É<0x79>{COLOR}Á verte")
        self.assertEqual([b for b, _ in bad], [0x79])

    def test_multiple_arrows_all_line_start(self):
        text = r"Route 13\p<0x79> Route 4\l<0x7A> Route 14\l<0x7C> Dehara"
        self.assertEqual(audit.find_misplaced_arrows(text), [])


class ArrowLineStartLiveEntryTests(unittest.TestCase):
    """The live combined_fr.txt entry for each fixed offset is arrow-clean."""

    @classmethod
    def setUpClass(cls):
        cls.live = audit.load_live_entries(COMBINED)

    def test_fixed_offsets_now_clean(self):
        for off in FIXED_OFFSETS:
            self.assertIn(off, self.live, f"0x{off:X} missing from combined_fr.txt")
            text, _ = self.live[off]
            self.assertEqual(
                audit.find_misplaced_arrows(text), [],
                f"0x{off:X} still has a misplaced arrow: {text!r}",
            )


class ArrowLineStartCorpusTests(unittest.TestCase):
    """Whole-corpus, English-grounded: no panel may have a mid-line arrow."""

    @classmethod
    def setUpClass(cls):
        if not ENGLISH_ROM.exists():
            raise unittest.SkipTest(f"English ROM not found: {ENGLISH_ROM}")
        cls.english = ENGLISH_ROM.read_bytes()

    def test_no_panel_has_misplaced_arrow(self):
        findings = audit.audit(COMBINED, self.english)
        detail = "\n".join(
            f"  0x{off:07X} (line {ln}): {text}" for off, ln, text, _ in findings
        )
        self.assertEqual(
            findings, [],
            f"{len(findings)} sign panel(s) with a mid-line arrow:\n{detail}",
        )

    def test_english_panel_detection(self):
        # A real worldmap panel (English arrows at line start) is a panel…
        self.assertTrue(audit.english_is_panel(self.english, 0x745518))
        # …while the inline-icon "Trainer Tips" string is not.
        self.assertFalse(audit.english_is_panel(self.english, 0x1F72F5A))


if __name__ == "__main__":
    unittest.main()
