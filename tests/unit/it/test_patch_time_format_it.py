"""Regression tests for languages/it/patches/time_format.py.

Run the real patch logic against a fresh copy of englishrom.gba (the
patches are all verified-byte, offset/pointer-exact rewrites, so a pristine
English ROM is the correct baseline — no IT build required) and assert the
decoded result matches Italian conventions.

Unlike the DE port, the "Never" word and the date template are patched as
two independent, non-relocating edits — the IT generic build's own pipeline
can relocate a byte-identical copy of the template elsewhere and repoint the
0x1EB6260 literal pool at it *before this script ever runs* (a pre-existing
pipeline behaviour, reproduced even with no Italian translation touching
this area at all — see the module docstring). Against a pristine English
ROM the pointer is untouched, so patch_save_template() finds the template at
its original fixed address; the "wherever the pointer resolves to" logic is
covered by test_patch_save_template_follows_relocated_pointer below, which
simulates the pipeline having moved it.
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

from languages.it.patches import time_format as mod  # noqa: E402
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

    def test_never_becomes_mai(self):
        mod.apply_patches(self.data)
        region = _read_cstr(self.data, mod.NEVER_OFFSET + 6)
        self.assertEqual(_decode(region), "Mai")

    def test_weekday_cells_are_italian_three_letter_forms(self):
        mod.apply_patches(self.data)
        i = 0xA4E554
        days = []
        for _ in range(7):
            j = i
            while self.data[j] != 0xFF:
                j += 1
            days.append(_decode(bytes(self.data[i:j])))
            i = j + 1
        self.assertEqual(days, ["Dom", "Lun", "Mar", "Mer", "Gio", "Ven", "Sab"])

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
class TestPatchSaveTemplate(unittest.TestCase):
    def setUp(self):
        self.data = bytearray(ENGLISH_ROM.read_bytes())

    def _template_target(self) -> int:
        ptr = struct.unpack_from("<I", self.data, mod.SAVE_TEMPLATE_PTR_SLOT)[0]
        return ptr - 0x08000000

    def test_applies_at_original_fixed_location(self):
        applied = mod.patch_save_template(self.data)
        self.assertEqual(applied, 1)
        off = self._template_target()
        template = bytes(self.data[off : off + 21])
        # {COLOR}{SHADOW} FD 04 / FD 03 / FD 02 <space> FD 07 : FD 08 <FF>
        self.assertEqual(
            template,
            bytes((0xFC, 0x01, 0x02, 0xFC, 0x03, 0x03))
            + bytes((0xFD, 0x04)) + b"\xba" + bytes((0xFD, 0x03)) + b"\xba"
            + bytes((0xFD, 0x02)) + b"\x00" + bytes((0xFD, 0x07)) + b"\xf0"
            + bytes((0xFD, 0x08)) + b"\xff",
        )

    def test_idempotent_second_run_changes_nothing(self):
        mod.patch_save_template(self.data)
        applied_again = mod.patch_save_template(self.data)
        self.assertEqual(applied_again, 0)

    def test_pointer_unchanged_no_relocation_performed(self):
        original_ptr = struct.unpack_from("<I", self.data, mod.SAVE_TEMPLATE_PTR_SLOT)[0]
        mod.patch_save_template(self.data)
        new_ptr = struct.unpack_from("<I", self.data, mod.SAVE_TEMPLATE_PTR_SLOT)[0]
        self.assertEqual(original_ptr, new_ptr, "template must be patched in place, not moved")

    def test_follows_relocated_pointer(self):
        # Simulate the IT pipeline having already moved a byte-identical
        # copy of the template elsewhere and repointed 0x1EB6260 at it —
        # this is the scenario the redesign (see module docstring) exists
        # to handle safely, without assuming a fixed template address.
        relocated_offset = 0x1FF0000  # arbitrary free area near ROM end, within bounds
        self.data[relocated_offset : relocated_offset + len(mod.SAVE_TEMPLATE_OLD)] = (
            mod.SAVE_TEMPLATE_OLD
        )
        struct.pack_into(
            "<I", self.data, mod.SAVE_TEMPLATE_PTR_SLOT, relocated_offset + 0x08000000
        )
        applied = mod.patch_save_template(self.data)
        self.assertEqual(applied, 1)
        patched = bytes(
            self.data[relocated_offset : relocated_offset + len(mod.SAVE_TEMPLATE_NEW)]
        )
        self.assertEqual(patched, mod.SAVE_TEMPLATE_NEW)


if __name__ == "__main__":
    unittest.main()
