"""Regression guard for scripts/patch_long_dialogues_it.py.

Over-cap Italian dialogues (New Game+, Battle Circus/Sands/Tower rules,
champion congratulation) are relocated to free space by this post-build
step. It runs mid-pipeline in languages/it/lang.yaml, *before*
status_badges / hp_labels / dexnav_headers, etc.

The generic IT builder consumes almost all of the ROM's free space, so
this relocation can find no room by the time it runs. When that happens
the dialogue must stay English as a **soft degradation** — exactly like
the `shop` and `cry_label` steps — instead of returning a non-zero exit
code that aborts the whole remaining pipeline (which shipped an IT ROM
without the later graphics patches; see the 3 dexnav/hp/status test
modules that broke against it).

These tests build tiny synthetic ROMs in memory and pin both behaviours:
relocation succeeds when free space exists, and the step degrades to a
warning (exit 0) when it does not.
"""

from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import patch_long_dialogues_it as mod  # noqa: E402

_OFF = mod.MAIN_TEXT_START            # first byte of the main text region
_PTR_CELL = 0x100                     # 4-byte-aligned pointer site (free region)
_EN_LEN = 1200                        # > EXTRACTOR_MAX_TEXT_LENGTH (1000)
_IT_TEXT = "Testo italiano lungo."


def _source_rom() -> bytes:
    """EN base whose string at ``_OFF`` overflows the extractor cap."""
    rom = bytearray(b"\x00" * (_OFF + _EN_LEN + 16))
    rom[_OFF:_OFF + _EN_LEN] = b"\x41" * _EN_LEN   # 'A' * _EN_LEN, no 0xFF
    rom[_OFF + _EN_LEN] = 0xFF                      # terminator
    return bytes(rom)


def _target_rom(free_space: bool) -> bytearray:
    """Built IT ROM with a live pointer to ``_OFF``.

    ``free_space=True`` leaves the ROM full of 0xFF (allocatable runs);
    ``False`` fills it with 0x00 so no free run exists anywhere.
    """
    fill = b"\xff" if free_space else b"\x00"
    rom = bytearray(fill * (_OFF + _EN_LEN + 16))
    struct.pack_into("<I", rom, _PTR_CELL, mod.GBA_BASE + _OFF)
    return rom


class TestLongDialoguesIt(unittest.TestCase):
    def test_relocates_and_repoints_when_free_space_exists(self):
        source = _source_rom()
        rom = _target_rom(free_space=True)
        stats = mod.patch(rom, {_OFF: _IT_TEXT}, source)

        self.assertEqual(stats["relocated"], 1)
        self.assertEqual(stats["failed"], 0)

        new_target = struct.unpack_from("<I", rom, _PTR_CELL)[0] - mod.GBA_BASE
        self.assertNotEqual(new_target, _OFF)          # pointer was moved
        encoded = mod._encode(_IT_TEXT)
        self.assertEqual(bytes(rom[new_target:new_target + len(encoded)]), encoded)

    def test_records_failure_when_no_free_space(self):
        source = _source_rom()
        rom = _target_rom(free_space=False)
        stats = mod.patch(rom, {_OFF: _IT_TEXT}, source)

        self.assertEqual(stats["relocated"], 0)
        self.assertEqual(stats["failed"], 1)
        # Pointer left untouched — dialogue stays English rather than corrupt.
        self.assertEqual(
            struct.unpack_from("<I", rom, _PTR_CELL)[0] - mod.GBA_BASE, _OFF
        )

    def test_main_exit_zero_on_free_space_exhaustion(self):
        """A partial relocation failure must NOT abort the build pipeline.

        This is the whole point of the fix: build_language.py runs every
        step with check=True, so a non-zero exit here skips status_badges /
        hp_labels / dexnav_headers and ships an incomplete ROM. The step is
        best-effort, so it warns and returns 0.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            rom_path = tmp / "rom.gba"
            src_path = tmp / "en.gba"
            combined_path = tmp / "combined_it.txt"
            rom_path.write_bytes(bytes(_target_rom(free_space=False)))
            src_path.write_bytes(_source_rom())
            combined_path.write_text(f"0x{_OFF:X}: {_IT_TEXT}\n", encoding="utf-8")

            exit_code = mod.main([
                "--rom", str(rom_path),
                "--combined", str(combined_path),
                "--source", str(src_path),
            ])

        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
