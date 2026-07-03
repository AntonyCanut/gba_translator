"""Tests for patch_zone_names_fr.py.

Covers:
  - Normal case: all too-long zone names are relocated and repointed.
  - Idempotency: running a second time leaves the ROM unchanged.
  - Verification catches a missed target.
  - Stats are correct.
"""

from __future__ import annotations

import struct
import unittest
from pathlib import Path

# Add repo root and scripts to sys.path before importing the module under test.
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from languages.fr.patches.zone_names import (  # noqa: E402
    TARGETS,
    apply,
    find_referrers,
    load_combined,
    verify,
)
from src.core.text_codec import TextEncoder  # noqa: E402

ROM_POINTER_BASE = 0x08000000


# ---------------------------------------------------------------------------
# Minimal ROM helpers
# ---------------------------------------------------------------------------

def _build_rom(
    size: int = 0x2000000,
    target_texts: dict[int, bytes] | None = None,
) -> bytearray:
    """Return a bytearray of *size* bytes, seeded with target texts.

    Each text is placed at its ROM offset, terminated by 0xFF.
    A GBA pointer to each text is written 4 bytes before the text so
    ``find_referrers`` can find it.
    """
    rom = bytearray(b"\xff" * size)

    # Standard GBA ROM header magic so patches don't bail out early.
    rom[0xB2] = 0x96

    if target_texts:
        for offset, text_bytes in target_texts.items():
            # Write the EN text.
            rom[offset: offset + len(text_bytes)] = text_bytes
            rom[offset + len(text_bytes)] = 0xFF
            # Plant a pointer 4 bytes before the text (simulates pointer table).
            ptr_cell = offset - 4
            struct.pack_into("<I", rom, ptr_cell, ROM_POINTER_BASE + offset)

    return rom


def _en_bytes_for(offset: int) -> bytes:
    """Return plausible English bytes for each TARGETS offset."""
    en_texts = {
        0x071FC80: b"\xbc\xe0\xdd\xee\xee\xd5\xe6\xd8\x00\xbd\xdd\xe8\xed",  # Blizzard City
        0x0B51EAC: b"\xbb\xe2\xe8\xdd\xe7\xdd\xe7\x00\xcaE\xe3\xe6\xe8",      # Antisis Port
        0x078D811: b"\xbd\xe6\xd5\xe8\xd9\xe6\x00\xce\xe3\xeb\xe2",           # Crater Town
        0x078D851: b"\xbc\xe0\xdd\xee\xee\xd5\xe6\xd8\x00\xbd\xdd\xe8\xed",  # Blizzard City
        # Cinder Volcano West
        0x078D7C8: b"\xbd\xdd\xe2\xd8\xd9\xe6\x00\xd0\xe3\xe0\xd7\xd5\xe2\xe3\x00\xd1\xd9\xe7\xe8",
    }
    return en_texts.get(offset, b"\xd9\xd2\xd5\xe1\xe4\xd0\xd9")  # fallback


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPatchZoneNamesFr(unittest.TestCase):

    def _make_combined(self) -> dict[int, str]:
        """Return combined_fr.txt entries for each TARGETS offset."""
        return {
            0x071FC80: "Cimistral",
            0x0B51EAC: "Port d'Antésia",
            0x078D811: "Cratéris",
            0x078D851: "Cimistral",
            0x078D7C8: "Volcan Cendré Ouest",
        }

    def _make_rom(self) -> bytearray:
        texts = {off: _en_bytes_for(off) for off in TARGETS}
        return _build_rom(target_texts=texts)

    def test_all_targets_relocated(self):
        rom = self._make_rom()
        combined = self._make_combined()
        stats = apply(rom, combined, bytes(rom))  # source_rom = initial state

        self.assertEqual(stats["failed"], 0, "No target should fail free-space allocation")
        self.assertEqual(stats["no_source"], 0, "Every target must have a combined_fr entry")
        self.assertEqual(stats["targets"], len(TARGETS), "All targets must be relocated")
        self.assertGreaterEqual(stats["repointed"], len(TARGETS),
                                "At least one pointer per target must be repointed")

    def test_idempotency(self):
        rom = self._make_rom()
        combined = self._make_combined()
        src = bytes(rom)

        apply(rom, combined, src)
        rom_after_first = bytes(rom)

        # Second run: all pointers now point to new location → find_referrers returns []
        stats2 = apply(rom, combined, src)
        self.assertEqual(bytes(rom), rom_after_first,
                         "Second run must not modify the ROM")
        self.assertEqual(stats2["skipped"], len(TARGETS),
                         "All targets must be skipped on second run")

    def test_verify_all_pass(self):
        rom = self._make_rom()
        combined = self._make_combined()
        apply(rom, combined, bytes(rom))

        failures = verify(bytes(rom))
        self.assertEqual(failures, [],
                         f"verify() must report no failures after patch: {failures}")

    def test_verify_catches_unpatched(self):
        rom = self._make_rom()
        # Do NOT apply — targets still have live pointers to English text.
        failures = verify(bytes(rom))
        self.assertEqual(len(failures), len(TARGETS),
                         "verify() must report every un-patched target")

    def test_stats_no_source(self):
        rom = self._make_rom()
        # Empty combined → no source for any target.
        stats = apply(rom, {}, bytes(rom))
        self.assertEqual(stats["no_source"], len(TARGETS))
        self.assertEqual(stats["targets"], 0)

    def test_find_referrers(self):
        rom = self._make_rom()
        for offset in TARGETS:
            refs = find_referrers(bytes(rom), offset)
            self.assertGreater(len(refs), 0,
                               f"Pointer to 0x{offset:08X} must be present in test ROM")

    def test_fr_text_in_rom_after_patch(self):
        rom = self._make_rom()
        combined = self._make_combined()
        apply(rom, combined, bytes(rom))
        rom_bytes = bytes(rom)

        for offset, fr_frag in TARGETS.items():
            encoded = TextEncoder.encode(fr_frag, "pokemon")[:-1]  # strip 0xFF
            self.assertIn(encoded, rom_bytes,
                          f"French fragment {repr(fr_frag)} for 0x{offset:X} not found in ROM")


if __name__ == "__main__":
    unittest.main()
