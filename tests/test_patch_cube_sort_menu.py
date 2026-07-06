"""Regression guard for languages/fr/patches/cube_sort_menu.py.

Issue #25: the Cube's item-pocket "Sort" popup ("Sort this pocket's items
how?" -> Type/Name/Amount -> "Sort items by X?" / "Items sorted by X!")
shipped in English. combined_fr.txt already has a French translation for
each offset, but none of these five strings has a live pointer in the built
ROM (unlike the neighboring Type/Nom/Plus/Moins cells in the same table),
so the reinjection pass can never relocate a longer French replacement here
and silently skips them. This dedicated in-place patch writes byte-exact FR
replacements that fit the original (tightly packed) slot sizes.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.text.charmap_data import CHAR_TO_BYTE
from languages.fr.patches.cube_sort_menu import _ENTRIES, apply_patch

_BASE = min(_ENTRIES)
_END = max(off + slot for off, (_en, _fr, slot) in _ENTRIES.items())


def _seed_rom() -> bytearray:
    rom = bytearray(_END + 64)
    for offset, (en_original, _fr_content, _slot) in _ENTRIES.items():
        rom[offset : offset + len(en_original)] = en_original
    # Sentinel string right after the last slot, matching the real ROM's
    # tightly packed layout — must survive untouched.
    sentinel = bytes(CHAR_TO_BYTE[c] for c in "WARNING") + b"\xff"
    rom[_END : _END + len(sentinel)] = sentinel
    return rom


def _apply_on(rom: bytearray, dry_run: bool = False) -> tuple[int, bytearray]:
    with TemporaryDirectory() as d:
        p = Path(d) / "rom.gba"
        p.write_bytes(rom)
        n = apply_patch(p, dry_run=dry_run)
        return n, bytearray(p.read_bytes())


class TestPatchCubeSortMenuFr(unittest.TestCase):
    def test_applies_all_five_and_is_idempotent(self):
        n, patched = _apply_on(_seed_rom())
        self.assertEqual(n, len(_ENTRIES))

        for offset, (en_original, _fr_content, _slot) in _ENTRIES.items():
            end = patched.index(0xFF, offset)
            self.assertNotEqual(
                bytes(patched[offset : end + 1]),
                en_original,
                f"0x{offset:X} still holds the English original",
            )

        n2, patched2 = _apply_on(patched)
        self.assertEqual(n2, 0)
        self.assertEqual(patched, patched2)

    def test_fr_bytes_fit_within_original_slot(self):
        for offset, (_en_original, fr_content, slot) in _ENTRIES.items():
            self.assertLessEqual(len(fr_content) + 1, slot, f"0x{offset:X} overflows its slot")

    def test_does_not_overflow_into_next_string(self):
        _n, patched = _apply_on(_seed_rom())
        end = patched.index(0xFF, _END)
        decoded = bytes(patched[_END:end])
        expected = bytes(CHAR_TO_BYTE[c] for c in "WARNING")
        self.assertEqual(decoded, expected, "the string following the last slot was clobbered")

    def test_skips_unexpected_current_value(self):
        rom = _seed_rom()
        first_offset = min(_ENTRIES)
        en_original, _fr, _slot = _ENTRIES[first_offset]
        rom[first_offset : first_offset + len(en_original)] = b"\x00" * len(en_original)
        n, _patched = _apply_on(rom)
        self.assertEqual(n, len(_ENTRIES) - 1)

    def test_every_fr_string_encodes_with_known_charmap_bytes(self):
        for _offset, (_en_original, fr_content, _slot) in _ENTRIES.items():
            for byte in fr_content:
                self.assertTrue(
                    byte in CHAR_TO_BYTE.values() or byte in (0xFE, 0xFD, 0x02),
                    f"byte 0x{byte:02X} is not a known charmap/control byte",
                )


if __name__ == "__main__":
    unittest.main()
