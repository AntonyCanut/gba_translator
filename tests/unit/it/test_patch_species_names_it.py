"""Regression guard for languages/it/combined_it.txt's species names.

The Italian build patches gSpeciesNames from combined_it.txt at the fixed
0x166A997 offset scheme. This guard makes sure the authored data remains at
that offset scheme and that the patch writes Italian-sourced cells in place.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from languages.fr.patches.species_names import (  # noqa: E402
    SPECIES_COUNT,
    SPECIES_STRIDE,
    TABLE_OFFSET,
    _decode_cell,
    _encode,
    apply_to_rom,
)

COMBINED_IT = ROOT / "languages" / "it" / "combined_it.txt"
_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")


def _it_entries() -> dict[int, str]:
    entries = {}
    for line in COMBINED_IT.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _LINE_RE.match(line)
        if m:
            entries[int(m.group(1), 16)] = m.group(2)
    return entries


class TestCombinedItSpeciesNames(unittest.TestCase):
    def test_combined_it_carries_expected_species_name_coverage(self):
        entries = _it_entries()
        species_entries = {
            offset: name
            for offset, name in entries.items()
            if TABLE_OFFSET <= offset < TABLE_OFFSET + SPECIES_COUNT * SPECIES_STRIDE
            and (offset - TABLE_OFFSET) % SPECIES_STRIDE == 0
        }
        self.assertGreaterEqual(len(species_entries), 1270)
        self.assertIn(TABLE_OFFSET, species_entries)
        self.assertIn(TABLE_OFFSET + 1292 * SPECIES_STRIDE, species_entries)

    def test_known_canonical_mappings(self):
        entries = _it_entries()
        self.assertEqual(entries.get(TABLE_OFFSET), "Bulbasaur")
        self.assertEqual(entries.get(TABLE_OFFSET + 1 * SPECIES_STRIDE), "Ivysaur")
        self.assertEqual(entries.get(TABLE_OFFSET + 3 * SPECIES_STRIDE), "Charmander")
        self.assertEqual(entries.get(TABLE_OFFSET + 1288 * SPECIES_STRIDE), "Alcremie")

    def test_patch_replaces_english_first_cells(self):
        data = bytearray(TABLE_OFFSET + 3 * SPECIES_STRIDE)
        data[TABLE_OFFSET: TABLE_OFFSET + len(_encode("SOMEOLD")) + 1] = _encode("SOMEOLD") + b"\xff"
        bulba = TABLE_OFFSET + SPECIES_STRIDE
        data[bulba: bulba + len(_encode("OLDNAME")) + 1] = _encode("OLDNAME") + b"\xff"
        ivysaur = TABLE_OFFSET + 2 * SPECIES_STRIDE
        data[ivysaur: ivysaur + len(_encode("OLDTWO")) + 1] = _encode("OLDTWO") + b"\xff"

        patched, warnings = apply_to_rom(
            data,
            {
                TABLE_OFFSET: "Bulbasaur",
                bulba: "Bulbasaur",
                ivysaur: "Ivysaur",
            },
            count=3,
        )

        self.assertEqual(patched, 3)
        self.assertEqual(warnings, [])
        self.assertEqual(_decode_cell(data, TABLE_OFFSET), "Bulbasaur")
        self.assertEqual(_decode_cell(data, bulba), "Bulbasaur")
        self.assertEqual(_decode_cell(data, ivysaur), "Ivysaur")


if __name__ == "__main__":
    unittest.main()
