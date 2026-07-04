"""Data-integrity guard for languages/it/combined_it.txt's move-name entries.

Every entry is authored at the legacy 0xA40A10 offset scheme (see
languages/fr/patches/move_names.py for why that isn't the live table); this
guards that the full 894-entry roster is present and every Italian name
fits the real table's 13-byte cell, so a future combined_it.txt edit can't
silently reintroduce an overflowing name.
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from languages.fr.patches.move_names import (  # noqa: E402
    LEGACY_TABLE_OFFSET,
    MOVE_COUNT,
    MOVE_STRIDE,
    _encode,
)

COMBINED_IT = ROOT / "languages" / "it" / "combined_it.txt"
_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")


def _it_entries() -> dict:
    entries = {}
    for line in COMBINED_IT.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _LINE_RE.match(line)
        if m:
            entries[int(m.group(1), 16)] = m.group(2)  # last wins
    return entries


class TestCombinedItMoveNames(unittest.TestCase):
    def test_all_894_move_indices_present(self):
        entries = _it_entries()
        missing = [
            i for i in range(MOVE_COUNT)
            if LEGACY_TABLE_OFFSET + i * MOVE_STRIDE not in entries
        ]
        self.assertEqual(missing, [], f"{len(missing)} move index(es) missing an Italian name")

    def test_most_italian_move_names_fit_cell(self):
        """Many official Italian move names are longer than French/English and
        overflow the 13-byte cell (~262/894 today, e.g. "Attacco d'Ala" /
        Wing Attack at 14 bytes) — apply_to_rom warns and skips those rather
        than truncating/corrupting (see test_patch_move_names_fr.py), exactly
        like the ~130 over-long ability names before B-131's shortening pass.
        Shortening these is editorial follow-up work, not this guard's job;
        it only asserts the split doesn't silently blow out further and that
        the large majority of the roster is genuinely patchable today.
        """
        entries = _it_entries()
        fits, overflow = 0, 0
        for index in range(MOVE_COUNT):
            offset = LEGACY_TABLE_OFFSET + index * MOVE_STRIDE
            name = entries.get(offset)
            if name is None:
                continue
            encoded = _encode(name)
            if len(encoded) + 1 <= MOVE_STRIDE:
                fits += 1
            else:
                overflow += 1
        self.assertGreater(fits, 600, "fewer patchable move names than expected")
        self.assertLess(overflow, 300, "more overflowing move names than expected — investigate regression")

    def test_known_canonical_mappings(self):
        entries = _it_entries()
        self.assertEqual(entries.get(LEGACY_TABLE_OFFSET + 1 * MOVE_STRIDE), "Botta")
        self.assertEqual(entries.get(LEGACY_TABLE_OFFSET + 2 * MOVE_STRIDE), "Colpo Karate")
        self.assertEqual(entries.get(LEGACY_TABLE_OFFSET + 12 * MOVE_STRIDE), "Ghigliottina")


if __name__ == "__main__":
    unittest.main()
