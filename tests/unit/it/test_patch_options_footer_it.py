"""Regression guard for languages/it/patches/options_footer.py.

Mirrors tests/unit/de/test_patch_options_footer_de.py: the page-2 button
legend at 0x1F4E244 starts with a raw control byte (0xF8), so it never
reached the injection JSON and needs this dedicated in-place patch.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from src.text.charmap_data import CHAR_TO_BYTE  # noqa: E402
from languages.it.patches import options_footer as mod  # noqa: E402

EN_ORIGINAL = mod.EN_ORIGINAL
OFFSET = mod.OFFSET
SLOT_SIZE = mod.SLOT_SIZE
apply_patch = mod.apply_patch


def _seed_rom(payload: bytes | None = None) -> bytearray:
    size = OFFSET + SLOT_SIZE + 64
    rom = bytearray(b"\x00" * size)
    data = payload if payload is not None else EN_ORIGINAL
    rom[OFFSET : OFFSET + len(data)] = data
    rom[OFFSET + len(data)] = 0xFF
    sentinel = bytes(CHAR_TO_BYTE[c] for c in "WARNING") + b"\xff"
    rom[OFFSET + SLOT_SIZE : OFFSET + SLOT_SIZE + len(sentinel)] = sentinel
    return rom


def _apply_on(rom: bytearray, dry_run: bool = False) -> tuple[int, bytearray]:
    with TemporaryDirectory() as d:
        p = Path(d) / "rom.gba"
        p.write_bytes(rom)
        n = apply_patch(p, dry_run=dry_run)
        return n, bytearray(p.read_bytes())


class TestPatchOptionsFooterIt(unittest.TestCase):
    def test_applies_from_english_and_is_idempotent(self):
        n, patched = _apply_on(_seed_rom())
        self.assertEqual(n, 1)
        end = patched.index(0xFF, OFFSET)
        self.assertNotEqual(bytes(patched[OFFSET:end]), EN_ORIGINAL[: end - OFFSET])

        n2, patched2 = _apply_on(patched)
        self.assertEqual(n2, 0)
        self.assertEqual(patched, patched2)

    def test_does_not_overflow_into_next_string(self):
        _n, patched = _apply_on(_seed_rom())
        sentinel_offset = OFFSET + SLOT_SIZE
        end = patched.index(0xFF, sentinel_offset)
        decoded = bytes(patched[sentinel_offset:end])
        expected = bytes(CHAR_TO_BYTE[c] for c in "WARNING")
        self.assertEqual(decoded, expected, "next packed string was clobbered")

    def test_control_codes_are_copied_byte_for_byte(self):
        _n, patched = _apply_on(_seed_rom())
        self.assertEqual(patched[OFFSET : OFFSET + 2], b"\xf8\x0a")
        end = patched.index(0xFF, OFFSET)
        tail = bytes(patched[OFFSET:end])
        for seq in (b"\xf8\x0a", b"\xf8\x0b", b"\xf8\x00\xf8\x01", b"\xfc\x01\x05\xfc\x03\x04", b"\xf8\x02\xf8\x03"):
            self.assertIn(seq, tail)

    def test_skips_unexpected_current_value(self):
        rom = _seed_rom(b"\x00" * len(EN_ORIGINAL))  # neither EN nor IT
        n, patched = _apply_on(rom)
        self.assertEqual(n, 0)

    def test_every_it_word_encodes(self):
        for word in mod.IT_WORDS:
            for ch in word:
                self.assertIn(ch, CHAR_TO_BYTE, f"{ch!r} in {word!r} has no charmap byte")

    def test_fits_slot_budget(self):
        it_bytes = mod._build_it_bytes()
        self.assertLessEqual(len(it_bytes) + 1, SLOT_SIZE)


if __name__ == "__main__":
    unittest.main()
