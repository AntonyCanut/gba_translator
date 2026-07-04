"""Regression tests for languages/de/patches/time_format.py.

Run the real patch logic against a fresh copy of englishrom.gba (the
patches are all verified-byte, offset/pointer-exact rewrites, so a pristine
English ROM is the correct baseline — no DE build required) and assert the
decoded result matches German conventions.
"""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from languages.de.patches import time_format as mod  # noqa: E402
from src.text.charmap_data import CHAR_TO_BYTE  # noqa: E402

BYTE_TO_CHAR = {v: k for k, v in CHAR_TO_BYTE.items()}
ENGLISH_ROM = ROOT / "input" / "roms" / "englishrom.gba"


def _decode(data: bytes) -> str:
    return "".join(BYTE_TO_CHAR.get(b, f"<{b:02x}>") for b in data)


def _read_cstr(data: bytes, offset: int) -> bytes:
    i = offset
    while data[i] != 0xFF:
        i += 1
    return data[offset:i]


@pytest.mark.skipif(not ENGLISH_ROM.exists(), reason="englishrom.gba not available")
class TestApplyPatches(unittest.TestCase):
    def setUp(self):
        self.data = bytearray(ENGLISH_ROM.read_bytes())

    def test_applies_cleanly_against_pristine_english_rom(self):
        applied = mod.apply_patches(self.data)
        self.assertEqual(applied, len(mod.PATCHES))

    def test_idempotent_second_run_applies_nothing(self):
        mod.apply_patches(self.data)
        applied_again = mod.apply_patches(self.data)
        self.assertEqual(applied_again, 0)

    def test_never_becomes_niemals_and_pointer_shifts(self):
        mod.apply_patches(self.data)
        region = _read_cstr(self.data, 0x1F11DAC + 6)
        self.assertEqual(_decode(region), "Niemals")
        ptr = struct.unpack("<I", self.data[0x1EB6260:0x1EB6264])[0]
        self.assertEqual(ptr, 0x09F11DBA)

    def test_save_template_is_day_dot_month_dot_year(self):
        mod.apply_patches(self.data)
        ptr_target = 0x1F11DBA  # per the shifted pointer above
        template = self.data[ptr_target : ptr_target + 22]
        # {COLOR}{SHADOW} FD 04 . FD 03 . FD 02 <space> FD 07 : FD 08 <FF>
        self.assertEqual(
            bytes(template[:20]),
            bytes((0xFC, 0x01, 0x02, 0xFC, 0x03, 0x03))
            + bytes((0xFD, 0x04)) + b"\xad" + bytes((0xFD, 0x03)) + b"\xad"
            + bytes((0xFD, 0x02)) + b"\x00" + bytes((0xFD, 0x07)) + b"\xf0"
            + bytes((0xFD, 0x08)),
        )
        self.assertEqual(template[20], 0xFF)

    def test_weekday_cells_are_german_three_letter_forms(self):
        mod.apply_patches(self.data)
        i = 0xA4E554
        days = []
        for _ in range(7):
            j = i
            while self.data[j] != 0xFF:
                j += 1
            days.append(_decode(bytes(self.data[i:j])))
            i = j + 1
        self.assertEqual(days, ["Son", "Mon", "Die", "Mit", "Don", "Fre", "Sam"])

    def test_am_pm_suffixes_emptied(self):
        mod.apply_patches(self.data)
        self.assertEqual(self.data[0x1F0687D], 0xFF)
        self.assertEqual(self.data[0x1F06881], 0xFF)

    def test_asm_conversion_branches_forced_unconditional(self):
        mod.apply_patches(self.data)
        self.assertEqual(bytes(self.data[0x1EB5F12:0x1EB5F14]), b"\x04\xe0")
        self.assertEqual(bytes(self.data[0xA0B534:0xA0B536]), b"\x00\xe0")
        self.assertEqual(bytes(self.data[0x1ECC16A:0x1ECC16C]), b"\x00\xe0")
        self.assertEqual(bytes(self.data[0x1ECC182:0x1ECC184]), b"\x00\xe0")


@pytest.mark.skipif(not ENGLISH_ROM.exists(), reason="englishrom.gba not available")
class TestPatchMonths(unittest.TestCase):
    def setUp(self):
        self.data = bytearray(ENGLISH_ROM.read_bytes())

    def _month(self, month: int) -> str:
        ptr_off = mod.MONTH_PTR_TABLE_FILE + 4 * (month - 1)
        ptr = struct.unpack("<I", self.data[ptr_off : ptr_off + 4])[0]
        off = ptr - 0x08000000
        return _decode(_read_cstr(self.data, off))

    def test_patched_months_render_german_abbreviations(self):
        mod.patch_months(self.data)
        # patch_months() alone leaves any trailing space in place — trimming
        # (when the Trainer Card builder needs it) is
        # patch_trainer_card_date_de.py's job, covered separately.
        for month, text in mod.MONTH_DE.items():
            self.assertEqual(self._month(month), text, f"month {month}")

    def test_idempotent_second_run_changes_nothing(self):
        mod.patch_months(self.data)
        changed_again = mod.patch_months(self.data)
        self.assertEqual(changed_again, 0)

    def test_untouched_months_keep_pipeline_provided_text(self):
        # Feb./Jun./Nov. are intentionally left alone (see module docstring):
        # against a pristine English ROM that means the original spelling
        # (English cells carry a trailing space in-slot).
        mod.patch_months(self.data)
        self.assertEqual(self._month(2), "Feb. ")
        self.assertEqual(self._month(6), "June ")
        self.assertEqual(self._month(11), "Nov. ")

    def test_raises_if_live_slot_too_small(self):
        # Simulate a relocated cell too tight for the German text: shrink
        # month 3's slot to 2 content bytes before patching.
        ptr_off = mod.MONTH_PTR_TABLE_FILE + 4 * (3 - 1)
        ptr = struct.unpack("<I", self.data[ptr_off : ptr_off + 4])[0]
        off = ptr - 0x08000000
        self.data[off : off + 3] = b"Hi" + b"\xff"
        with self.assertRaises(ValueError):
            mod.patch_months(self.data)

    def test_july_fits_a_four_byte_live_slot(self):
        # CI run #29 failed here after the generic DE pipeline relocated July
        # to a 4-byte live slot. The patch must stay within that budget.
        ptr_off = mod.MONTH_PTR_TABLE_FILE + 4 * (7 - 1)
        relocated = 0x1000
        self.data[ptr_off : ptr_off + 4] = struct.pack("<I", 0x08000000 + relocated)
        self.data[relocated : relocated + 5] = mod.encode("Jul.") + b"\xff"

        mod.patch_months(self.data)

        self.assertEqual(_decode(_read_cstr(self.data, relocated)), "Juli")


if __name__ == "__main__":
    unittest.main()
