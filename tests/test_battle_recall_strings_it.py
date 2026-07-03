"""Unit tests for languages/it/patches/battle_recall_strings.py."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.it.patches.battle_recall_strings import (
    IT_STRINGS,
    RECALL_PTRS,
    apply_to_rom,
)

GBA_BASE = 0x08000000


def _make_rom(size: int = 0x800000) -> bytearray:
    """Minimal ROM: all 0xFF except the three EN recall pointer values."""
    rom = bytearray(b"\xff" * size)
    for ptr_off, old_body_off in RECALL_PTRS:
        struct.pack_into("<I", rom, ptr_off, GBA_BASE + old_body_off)
    return rom


def test_apply_patches_all_three():
    rom = _make_rom()
    count = apply_to_rom(rom, dry_run=False)
    assert count == 3, f"expected 3 patches, got {count}"


def test_apply_redirects_pointers():
    rom = _make_rom()
    apply_to_rom(rom, dry_run=False)
    for (ptr_off, old_body_off), it_bytes in zip(RECALL_PTRS, IT_STRINGS):
        new_ptr = struct.unpack_from("<I", rom, ptr_off)[0]
        old_ptr = GBA_BASE + old_body_off
        assert new_ptr != old_ptr, (
            f"pointer @0x{ptr_off:06X} was not updated (still {old_ptr:08X})"
        )
        new_off = new_ptr - GBA_BASE
        assert rom[new_off: new_off + len(it_bytes)] == it_bytes, (
            f"IT string not found at new offset 0x{new_off:06X}"
        )


def test_apply_is_idempotent():
    rom = _make_rom()
    count1 = apply_to_rom(rom, dry_run=False)
    count2 = apply_to_rom(rom, dry_run=False)
    assert count1 == 3
    assert count2 == 0, "second application should be a no-op"


def test_dry_run_does_not_write():
    rom = _make_rom()
    original = bytearray(rom)
    count = apply_to_rom(rom, dry_run=True)
    assert count == 3
    assert rom == original, "dry-run must not modify ROM"


def test_it_strings_end_with_terminator():
    for i, it in enumerate(IT_STRINGS):
        assert it[-1] == 0xFF, f"IT_STRINGS[{i}] does not end with 0xFF terminator"


def test_it_strings_start_with_fd1d():
    """All three IT strings must start with the trainer-name buffer token {FD1D}."""
    for i, it in enumerate(IT_STRINGS):
        assert it[:2] == b"\xfd\x1d", (
            f"IT_STRINGS[{i}] does not start with FD1D (trainer name token)"
        )


def test_it_strings_contain_torna():
    """Sanity: every IT string actually says "torna"/"tornate" (come back)."""
    torna = bytes([0xE8, 0xE3, 0xE6, 0xE2, 0xD5])  # 't','o','r','n','a'
    for i, it in enumerate(IT_STRINGS):
        assert torna in it, f"IT_STRINGS[{i}] does not contain 'torna'"
