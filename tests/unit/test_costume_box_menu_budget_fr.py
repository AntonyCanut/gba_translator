"""Regression guard for the Costume Box (Garde-robe) menu strings.

0x1EED1B3 (title) and 0x1EED1C0 (D-pad/action/B-button labels) are fixed-width
no-pointer in-place cells (no relocation possible), budget = EN byte length
including the 0xFF terminator, measured directly from englishrom.gba.

A FR translation exceeding the budget is silently dropped in favour of English
at build time — that's what happened with the previous
"{DPAD_LEFTRIGHT}Choisir {SE_SHOP}Essayer {B_BUTTON}Fermer" button row (20+
chars against a 15-char budget for the three words). The title also needs its
leading-space byte (present in both EN " Costume Box" and the ES reference
" Atuendos   "): the window chrome overlaps the first tile, so a translation
missing that leading space renders with its first letter clipped ("Garde-robe"
displays as "arde-robe").
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core.text_codec import TextEncoder  # noqa: E402

COMBINED_FR = ROOT / "languages/fr/combined_fr.txt"

# EN byte budget (encoded length including the 0xFF terminator), measured
# directly from input/roms/englishrom.gba at each offset.
BUDGETS = {
    0x1EED1B3: 13,
    0x1EED1C0: 24,
}

_LINE_RE = re.compile(r"^(0x[0-9a-fA-F]+): (.*)$")


def _load_last_wins(path: Path) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _LINE_RE.match(line)
        if not m:
            continue
        mapping[int(m.group(1), 16)] = m.group(2)
    return mapping


class TestCostumeBoxMenuBudget:
    def test_combined_fr_present(self):
        assert COMBINED_FR.exists()

    @pytest.mark.parametrize("offset", sorted(BUDGETS))
    def test_offset_present_in_combined_fr(self, offset: int):
        mapping = _load_last_wins(COMBINED_FR)
        assert offset in mapping, f"0x{offset:06X} missing from combined_fr.txt"

    @pytest.mark.parametrize("offset", sorted(BUDGETS))
    def test_translation_fits_budget(self, offset: int):
        mapping = _load_last_wins(COMBINED_FR)
        text = mapping[offset]
        encoded = TextEncoder().encode_pokemon(text)
        length = len(encoded) if encoded and encoded[-1] == 0xFF else len(encoded) + 1
        budget = BUDGETS[offset]
        assert length <= budget, (
            f"0x{offset:06X}: encoded length {length} exceeds EN budget {budget} "
            f"({text!r}) — will be dropped to English at build time"
        )

    def test_title_has_leading_space(self):
        """The window chrome clips the first tile; the title needs a leading
        space byte to avoid its first letter being visually obscured."""
        mapping = _load_last_wins(COMBINED_FR)
        text = mapping[0x1EED1B3]
        assert text.startswith("<0x00>"), (
            f"0x1EED1B3 title {text!r} is missing its leading-space byte "
            "(<0x00>) — the first letter will render clipped by the window chrome"
        )
