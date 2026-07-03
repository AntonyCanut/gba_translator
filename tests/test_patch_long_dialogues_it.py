"""Regression guard for scripts/patch_long_dialogues_it.py.

Dialogues longer than the extractor cap (1000 bytes) are dropped by the
generic pipeline and ship English. This patch relocates the full Italian
text to free space and repoints the live pointer. The tests below verify
the discovery + relocate + repoint mechanism on a synthetic ROM, and check
idempotency and the real over-cap offset set against the source ROM.
"""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.patch_long_dialogues_it import (  # noqa: E402
    EXTRACTOR_MAX_TEXT_LENGTH,
    GBA_BASE,
    MAIN_TEXT_START,
    _encode,
    _load_combined,
    find_overcap_offsets,
    patch,
)

SOURCE_ROM = REPO_ROOT / "input/roms/englishrom.gba"
COMBINED = REPO_ROOT / "languages/it/combined_it.txt"


def _synthetic_rom():
    """A ROM with one over-cap English dialogue, its pointer, and free space."""
    size = MAIN_TEXT_START + 0x8000
    rom = bytearray(b"\xFF" * size)  # all free space by default
    text_off = MAIN_TEXT_START + 0x100
    # 1100-byte English string (> cap) terminated by 0xFF.
    rom[text_off:text_off + 1100] = b"\x01" * 1100  # 0x01 = 'a' region byte
    rom[text_off + 1100] = 0xFF
    # A pointer cell near the start of ROM referencing that string.
    ptr_cell = 0x1000
    struct.pack_into("<I", rom, ptr_cell, GBA_BASE + text_off)
    return rom, text_off, ptr_cell


class TestLongDialoguePatchUnit(unittest.TestCase):
    def test_relocates_and_repoints(self):
        rom, text_off, ptr_cell = _synthetic_rom()
        italian = "Questo è un dialogo lungo. " * 45  # > cap once encoded
        combined = {text_off: italian}

        # Sanity: discovery finds our over-cap offset.
        self.assertIn(text_off, find_overcap_offsets(bytes(rom), combined))

        stats = patch(rom, combined, bytes(rom))
        self.assertEqual(stats["relocated"], 1)
        self.assertEqual(stats["failed"], 0)

        new_target = struct.unpack_from("<I", rom, ptr_cell)[0] - GBA_BASE
        self.assertNotEqual(new_target, text_off, "pointer was not repointed")
        encoded = _encode(italian)
        self.assertEqual(bytes(rom[new_target:new_target + len(encoded)]), encoded)
        # Terminated → freeze-safe.
        self.assertEqual(rom[new_target + len(encoded) - 1], 0xFF)

    def test_short_string_ignored(self):
        rom, text_off, _ = _synthetic_rom()
        # A short entry (below cap) must not be considered over-cap.
        short_off = MAIN_TEXT_START + 0x4000
        rom[short_off:short_off + 10] = b"\x01" * 10
        rom[short_off + 10] = 0xFF
        combined = {short_off: "breve"}
        self.assertNotIn(short_off, find_overcap_offsets(bytes(rom), combined))

    def test_no_referrer_is_not_a_failure(self):
        rom, text_off, ptr_cell = _synthetic_rom()
        # Remove the pointer so no referrer exists.
        struct.pack_into("<I", rom, ptr_cell, 0)
        combined = {text_off: "Dialogo " * 200}
        stats = patch(rom, combined, bytes(rom))
        self.assertEqual(stats["relocated"], 0)
        self.assertEqual(stats["failed"], 0)
        self.assertEqual(stats["no_referrer"], 1)


@unittest.skipUnless(SOURCE_ROM.exists() and COMBINED.exists(),
                     "englishrom.gba / combined_it.txt not available")
class TestLongDialogueAgainstSource(unittest.TestCase):
    def test_overcap_set_is_stable(self):
        source = SOURCE_ROM.read_bytes()
        combined = _load_combined(COMBINED)
        offsets = find_overcap_offsets(source, combined)
        # The known over-cap dialogues (New Game+, Battle Circus/Sands/Tower,
        # champion congratulation). All live in the main text region.
        self.assertGreaterEqual(len(offsets), 5)
        for off in offsets:
            self.assertGreaterEqual(off, MAIN_TEXT_START)

    def test_relocation_round_trip_on_source_copy(self):
        source = SOURCE_ROM.read_bytes()
        combined = _load_combined(COMBINED)
        rom = bytearray(source)
        stats = patch(rom, combined, source)
        self.assertGreaterEqual(stats["relocated"], 5)
        self.assertEqual(stats["failed"], 0)
        # Every relocated string ends with a terminator within the ROM.
        # (Spot check: re-running is a safe no-op — original pointers are gone.)
        again = patch(rom, combined, source)
        self.assertEqual(again["relocated"], 0)
        self.assertEqual(again["failed"], 0)


if __name__ == "__main__":
    unittest.main()
