"""Fast unit tests for the version-display verifier (no ROM required).

These synthesise an in-memory ROM whose NOT FOR SALE tileset is built with the
production renderer, then prove the *independent* blind decoder reads back the
exact ``FR.2.0.<build>`` string and that ``verify()`` catches mismatches.
"""

import struct
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.patch_version_fr import (
    _GBA_BASE,
    _NFS_TILESET_PTR_OFF,
    _VER_GRID_COLS,
    _VER_GRID_ROWS,
    _VER_TILE_START,
    _blit_band_to_tiles,
    _compute_checksum,
    _lz77_compress,
    _render_version_band,
    version_string,
)
from scripts.verify_version_display import (
    decode_version_string,
    slot_machine_pointers,
    verify,
    _SLOT_MACHINE_PTRS,
)

# A fake ROM only needs to be large enough to hold the header, the version
# pointer (0xEC610) and the compressed tileset payload.
_ROM_SIZE = 0x200000
_TILESET_PAYLOAD_OFF = 0x100000


def _build_fake_rom(build_number: int) -> bytearray:
    """Construct a minimal ROM whose NOT FOR SALE band renders ``build_number``."""
    rom = bytearray(b"\xFF" * _ROM_SIZE)
    rom[0xB2] = 0x96  # GBA magic
    rom[0xBC] = build_number & 0xFF
    rom[0xBD] = _compute_checksum(rom)

    # Render + blit the version band into a tileset of the expected length.
    n_tiles = _VER_TILE_START + _VER_GRID_COLS * _VER_GRID_ROWS
    tileset = bytearray(32 * n_tiles)
    _blit_band_to_tiles(tileset, _render_version_band(version_string(build_number)))

    compressed = _lz77_compress(bytes(tileset))
    rom[_TILESET_PAYLOAD_OFF:_TILESET_PAYLOAD_OFF + len(compressed)] = compressed
    struct.pack_into("<I", rom, _NFS_TILESET_PTR_OFF, _TILESET_PAYLOAD_OFF + _GBA_BASE)
    return rom


class TestBlindDecoder(unittest.TestCase):
    def test_decodes_each_build_number(self):
        for build in (0, 1, 5, 42, 99, 999, 9999):
            rom = _build_fake_rom(build)
            self.assertEqual(
                decode_version_string(rom),
                version_string(build),
                f"blind decode mismatch for build {build}",
            )

    def test_decode_independent_of_renderer(self):
        # The decoder must literally spell "FR.2.0.7", not just match bytes.
        rom = _build_fake_rom(7)
        self.assertEqual(decode_version_string(rom), "FR.2.0.7")

    def test_no_question_marks(self):
        rom = _build_fake_rom(1234)
        self.assertNotIn("?", decode_version_string(rom))


class TestVerify(unittest.TestCase):
    def test_passes_for_matching_build(self):
        rom = _build_fake_rom(42)
        self.assertEqual(verify(rom, 42), [])

    def test_detects_screen_mismatch(self):
        # ROM renders build 42 but we expect 43 -> the screen text differs.
        rom = _build_fake_rom(42)
        problems = verify(rom, 43)
        self.assertTrue(problems)
        self.assertTrue(any("NOT FOR SALE" in p for p in problems))

    def test_detects_header_mismatch(self):
        rom = _build_fake_rom(42)
        rom[0xBC] = 0x00  # corrupt the header software-version byte
        problems = verify(rom, 42)
        self.assertTrue(any("0xBC" in p for p in problems))


class TestSlotMachinePointers(unittest.TestCase):
    def test_reads_two_pointers(self):
        rom = _build_fake_rom(1)
        ptrs = slot_machine_pointers(rom)
        self.assertEqual(len(ptrs), len(_SLOT_MACHINE_PTRS))


if __name__ == "__main__":
    unittest.main()
