"""Unit tests for patch_battle_recall_strings_fr.py and {FDxx} encoder fix."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.patch_battle_recall_strings_fr import (
    FR_STRINGS,
    RECALL_PTRS,
    apply_to_rom,
)
from src.core.text_codec import TextEncoder

GBA_BASE = 0x08000000

# ---------------------------------------------------------------------------
# Encoder fix: {FDxx} brace tokens must produce raw 2-byte sequences
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text,expected_hex", [
    ("{FD24}", "fd24ff"),
    ("{FD2E}", "fd2eff"),
    ("{FD25}", "fd25ff"),
    ("{FD2F}", "fd2fff"),
    ("{FD06}", "fd06ff"),
    ("{FD1D}", "fd1dff"),
    ("{FC09}", "fc09ff"),
])
def test_encode_pokemon_brace_control_token(text, expected_hex):
    """{FDxx}/{FCxx} tokens must encode as raw 2-byte sequences, not garbage."""
    result = TextEncoder.encode_pokemon(text)
    assert result.hex() == expected_hex, (
        f"encode_pokemon({text!r}) → {result.hex()}, expected {expected_hex}"
    )


def test_encode_pokemon_brace_token_in_sentence():
    """{FDxx} mixed with plain text must encode each part correctly."""
    # "{FD1D}: {FD06}, reviens !"
    result = TextEncoder.encode_pokemon("{FD1D}: {FD06}, reviens !")
    assert result[0:2] == b"\xfd\x1d", "first token should be FD1D"
    assert result[2] == 0xF0, "colon should be 0xF0"
    assert result[3] == 0x00, "space should be 0x00"
    assert result[4:6] == b"\xfd\x06", "second token should be FD06"
    assert result[-1] == 0xFF, "must end with terminator"


# ---------------------------------------------------------------------------
# Patch logic: apply_to_rom
# ---------------------------------------------------------------------------


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
    for (ptr_off, old_body_off), fr_bytes in zip(RECALL_PTRS, FR_STRINGS):
        new_ptr = struct.unpack_from("<I", rom, ptr_off)[0]
        old_ptr = GBA_BASE + old_body_off
        assert new_ptr != old_ptr, (
            f"pointer @0x{ptr_off:06X} was not updated (still {old_ptr:08X})"
        )
        new_off = new_ptr - GBA_BASE
        assert rom[new_off: new_off + len(fr_bytes)] == fr_bytes, (
            f"FR string not found at new offset 0x{new_off:06X}"
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


def test_fr_strings_end_with_terminator():
    for i, fr in enumerate(FR_STRINGS):
        assert fr[-1] == 0xFF, f"FR_STRINGS[{i}] does not end with 0xFF terminator"


def test_fr_strings_start_with_fd1d():
    """All three FR strings must start with the trainer-name buffer token {FD1D}."""
    for i, fr in enumerate(FR_STRINGS):
        assert fr[:2] == b"\xfd\x1d", (
            f"FR_STRINGS[{i}] does not start with FD1D (trainer name token)"
        )
