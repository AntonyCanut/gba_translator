"""Unit tests for patch_battle_recall_strings_de.py."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.de.patches.battle_recall_strings import (
    DE_STRINGS,
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
    for (ptr_off, old_body_off), de_bytes in zip(RECALL_PTRS, DE_STRINGS):
        new_ptr = struct.unpack_from("<I", rom, ptr_off)[0]
        old_ptr = GBA_BASE + old_body_off
        assert new_ptr != old_ptr, (
            f"pointer @0x{ptr_off:06X} was not updated (still {old_ptr:08X})"
        )
        new_off = new_ptr - GBA_BASE
        assert rom[new_off: new_off + len(de_bytes)] == de_bytes, (
            f"DE string not found at new offset 0x{new_off:06X}"
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


def test_de_strings_end_with_terminator():
    for i, de in enumerate(DE_STRINGS):
        assert de[-1] == 0xFF, f"DE_STRINGS[{i}] does not end with 0xFF terminator"


def test_de_strings_start_with_fd1d():
    """All three DE strings must start with the trainer-name buffer token {FD1D}."""
    for i, de in enumerate(DE_STRINGS):
        assert de[:2] == b"\xfd\x1d", (
            f"DE_STRINGS[{i}] does not start with FD1D (trainer name token)"
        )


def test_de_strings_contain_zuruck():
    """Sanity: every DE string actually says "zurück" (come back)."""
    zurueck = bytes([0xEE, 0xE9, 0xE6, 0xF6, 0xD7, 0xDF])  # 'z','u','r','ü','c','k'
    for i, de in enumerate(DE_STRINGS):
        assert zurueck in de, f"DE_STRINGS[{i}] does not contain 'zurück'"
