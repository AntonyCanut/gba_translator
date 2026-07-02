"""Regression guard for B-133: Dresco/Mystherbe dialogue budget (no-pointer in-place slots).

These 5 offsets live in ROM cells with zero slack (pointer_offsets absent from the
injection JSON => no relocation possible, budget = EN byte length including the
0xFF terminator). A FR translation longer than the EN original is silently dropped
in favour of English at build time. Guards against a future combined_fr.txt edit
re-introducing the wordier "Feuilles de Mystherbe" phrasing that overflowed.
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

# EN byte budget (encoded length including the 0xFF terminator), measured directly
# from input/roms/englishrom.gba at each offset.
BUDGETS = {
    0x746471: 87,
    0x74C623: 31,
    0x753107: 131,
    0x1EE0B70: 452,
    0x1EE0FCF: 158,
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


class TestDrescoMystherbeBudget:
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
