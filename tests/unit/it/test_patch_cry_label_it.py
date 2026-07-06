"""Regression guard for languages/it/patches/cry_label.py (B-188).

"Grido" overflows the fixed 3-glyph "Cry" cell, so the patch relocates the
body to free space and repoints its two known external pointers
(0x105FE4 / 0x1067B8, verified by a full-ROM scan for the EN body pointer —
the ticket-recorded 0x105FD8 "table_offsets" is the struct-row anchor 12
bytes earlier, not itself a pointer, and is deliberately left untouched).
"""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from languages.it.patches.cry_label import (
    CRY_PTR_OFFSETS,
    GBA_BASE,
    NAME,
    OLD_BODY_OFFSET,
    _body_bytes,
    apply_to_rom,
)


def _make_rom(size: int = 0x1200000) -> bytearray:
    """Minimal ROM: all 0xFF except the EN "Cry" body and its two pointers."""
    rom = bytearray(b"\xff" * size)
    en_body = b"\xf8\x04\xbd\xe6\xed\xff"  # <0xF8><0x04>Cry<0xFF>
    rom[OLD_BODY_OFFSET : OLD_BODY_OFFSET + len(en_body)] = en_body
    for off in CRY_PTR_OFFSETS:
        struct.pack_into("<I", rom, off, GBA_BASE + OLD_BODY_OFFSET)
    return rom


class TestCryLabelIt(unittest.TestCase):
    def test_apply_relocates_and_repoints(self):
        rom = _make_rom()
        count = apply_to_rom(rom, dry_run=False)
        self.assertEqual(count, 1)
        body = _body_bytes(NAME)
        for off in CRY_PTR_OFFSETS:
            new_ptr = struct.unpack_from("<I", rom, off)[0]
            self.assertNotEqual(new_ptr, GBA_BASE + OLD_BODY_OFFSET)
            new_off = new_ptr - GBA_BASE
            self.assertEqual(rom[new_off : new_off + len(body)], body)

    def test_both_pointers_agree_on_new_target(self):
        rom = _make_rom()
        apply_to_rom(rom, dry_run=False)
        ptrs = [struct.unpack_from("<I", rom, off)[0] for off in CRY_PTR_OFFSETS]
        self.assertEqual(ptrs[0], ptrs[1])

    def test_old_en_body_untouched(self):
        rom = _make_rom()
        en_body = bytes(rom[OLD_BODY_OFFSET : OLD_BODY_OFFSET + 6])
        apply_to_rom(rom, dry_run=False)
        self.assertEqual(bytes(rom[OLD_BODY_OFFSET : OLD_BODY_OFFSET + 6]), en_body)

    def test_apply_is_idempotent(self):
        rom = _make_rom()
        count1 = apply_to_rom(rom, dry_run=False)
        count2 = apply_to_rom(rom, dry_run=False)
        self.assertEqual(count1, 1)
        self.assertEqual(count2, 0)

    def test_dry_run_does_not_write(self):
        rom = _make_rom()
        original = bytearray(rom)
        count = apply_to_rom(rom, dry_run=True)
        self.assertEqual(count, 1)
        self.assertEqual(rom, original)

    def test_skips_when_pointers_inconsistent(self):
        rom = _make_rom()
        # Simulate a partially-repointed / corrupted state.
        struct.pack_into("<I", rom, CRY_PTR_OFFSETS[0], 0xDEADBEEF)
        count = apply_to_rom(rom, dry_run=False)
        self.assertEqual(count, 0)

    def test_body_bytes_shape(self):
        body = _body_bytes(NAME)
        self.assertEqual(body[:2], b"\xf8\x04")
        self.assertEqual(body[-1], 0xFF)
        self.assertEqual(len(body), 2 + len(NAME) + 1)


if __name__ == "__main__":
    unittest.main()
