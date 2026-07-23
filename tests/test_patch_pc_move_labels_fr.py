"""Regression tests for the FR PC/Box « Move » → « Dépl. » label patch (issue #29).

The tight 4-byte « Move » cells (0x418484, 0x418EB5, 0xA4E1F1) cannot hold the
5-byte « Dépl. » in place — the inject pass overflowed 0xA4E1F1 into the next
string, producing the corrupt « Dépl.Dépl. où ? » the reporter photographed. The
patch relocates every such string to a baseline-free 0xFF block and repoints all
their pointers, so each menu renders a properly terminated « Dépl. » (with the
period). The pointer-less mail submenu « Move To Bag » is fixed in place to
« Vers le sac ».
"""

import struct
import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.fr.patches.pc_move_labels import (
    FREESPACE_BASE,
    MAIL_MOVE_TO_BAG_EN,
    MAIL_MOVE_TO_BAG_FR,
    MAIL_MOVE_TO_BAG_OFFSET,
    MAIL_MOVE_TO_BAG_PREIMAGES,
    ROM_BASE,
    _RELOCATIONS,
    _enc,
    apply,
)
from src.core.text_codec import TextDecoder

BUILT_FR_ROM = Path(__file__).parent.parent / "output" / "roms" / "GenedRom-fr.gba"
ROM_SIZE = 0x2000000


def _fake_rom() -> bytearray:
    rom = bytearray(b"\xff" * ROM_SIZE)
    rom[0xB2] = 0x96
    # Seed each pointer site with its original cell address.
    for entry in _RELOCATIONS:
        for loc, orig in entry["orig"].items():
            struct.pack_into("<I", rom, loc, ROM_BASE | orig)
    # Seed the walked mail string with its English original.
    rom[MAIL_MOVE_TO_BAG_OFFSET:MAIL_MOVE_TO_BAG_OFFSET + len(MAIL_MOVE_TO_BAG_EN)] = (
        MAIL_MOVE_TO_BAG_EN
    )
    return rom


def _decode_at(rom: bytes, off: int) -> str:
    raw = bytes(rom[off:off + 64])
    end = raw.find(b"\xff")
    return TextDecoder.decode_pokemon(raw[: end if end >= 0 else 64], preserve_unknown=True)


class TestConstants(unittest.TestCase):
    def test_mail_replacement_fits_in_place(self):
        # « Vers le sac » must be no longer than the English « Move To Bag » cell.
        self.assertEqual(len(MAIL_MOVE_TO_BAG_FR), len(MAIL_MOVE_TO_BAG_EN))

    def test_all_mail_preimages_match_fixed_cell_width(self):
        for preimage in MAIL_MOVE_TO_BAG_PREIMAGES:
            self.assertEqual(len(preimage), len(MAIL_MOVE_TO_BAG_FR))

    def test_freespace_base_is_addressable_rom(self):
        self.assertLess(FREESPACE_BASE, ROM_SIZE)


class TestApply(unittest.TestCase):
    def test_all_pointers_render_depl_with_period(self):
        rom = _fake_rom()
        n = apply(rom)
        # 8 pointer rewrites + 1 in-place mail string.
        self.assertEqual(n, 9)
        for entry in _RELOCATIONS:
            expected = entry["prefix"] + _enc(entry["text"])
            for loc in entry["pointers"]:
                ptr = struct.unpack_from("<I", rom, loc)[0]
                self.assertTrue(ROM_BASE <= ptr < 0x0A000000)
                off = ptr - ROM_BASE
                self.assertTrue(off >= FREESPACE_BASE, "must relocate into free block")
                self.assertEqual(bytes(rom[off:off + len(expected)]), expected)
                self.assertEqual(rom[off + len(expected)], 0xFF, "must be terminated")

    def test_no_corruption_at_original_cell(self):
        # The relocated pointer no longer reads the overflowed in-place bytes.
        rom = _fake_rom()
        apply(rom)
        ptr = struct.unpack_from("<I", rom, 0xA6CAAC)[0]
        self.assertEqual(_decode_at(rom, ptr - ROM_BASE), "Dépl.")

    def test_mail_move_to_bag(self):
        rom = _fake_rom()
        apply(rom)
        self.assertEqual(_decode_at(rom, MAIL_MOVE_TO_BAG_OFFSET), "Vers le sac")

    def test_normalizes_generic_abbreviated_mail_label(self):
        rom = _fake_rom()
        legacy_fr = _enc("Dépl au sac")
        rom[MAIL_MOVE_TO_BAG_OFFSET:MAIL_MOVE_TO_BAG_OFFSET + len(legacy_fr)] = legacy_fr

        apply(rom)

        self.assertEqual(_decode_at(rom, MAIL_MOVE_TO_BAG_OFFSET), "Vers le sac")

    def test_idempotent(self):
        rom = _fake_rom()
        self.assertEqual(apply(rom), 9)
        self.assertEqual(apply(rom), 0)

    def test_skips_unexpected_pointer(self):
        rom = _fake_rom()
        struct.pack_into("<I", rom, 0xA6CAAC, 0x08123456)  # not the expected cell
        apply(rom)
        # Unexpected site left untouched.
        self.assertEqual(struct.unpack_from("<I", rom, 0xA6CAAC)[0], 0x08123456)

    def test_skips_when_free_slot_dirty(self):
        rom = _fake_rom()
        rom[FREESPACE_BASE] = 0x42  # first slot not free -> refuse to clobber
        apply(rom)
        # The plain-« Dépl. » pointers must remain at their originals.
        self.assertEqual(
            struct.unpack_from("<I", rom, 0x3D3548)[0], ROM_BASE | 0x418484
        )


@pytest.mark.rom
@pytest.mark.skipif(not BUILT_FR_ROM.exists(), reason="built FR ROM not present")
class TestBuiltRom(unittest.TestCase):
    def setUp(self):
        self.rom = BUILT_FR_ROM.read_bytes()

    def _follow(self, loc: int) -> str:
        ptr = struct.unpack_from("<I", self.rom, loc)[0]
        self.assertTrue(0x08000000 <= ptr < 0x0A000000, f"bad ptr 0x{ptr:08X}")
        return _decode_at(self.rom, ptr - 0x08000000)

    def test_box_option_and_secondary_menu(self):
        for loc in (0x3D3548, 0x9A41C4, 0xA6CAAC):
            self.assertEqual(self._follow(loc), "Dépl.", f"ptr@0x{loc:X}")

    def test_hud_hint(self):
        for loc in (0xC05D8, 0xC12E0, 0xC283C, 0xC4FE8):
            self.assertEqual(self._follow(loc), "<0xF8>ÏDépl.", f"ptr@0x{loc:X}")

    def test_box_main_menu(self):
        self.assertEqual(self._follow(0x3CDA20), "Dépl. Pokémon")

    def test_mail_move_to_bag(self):
        raw = self.rom[MAIL_MOVE_TO_BAG_OFFSET:MAIL_MOVE_TO_BAG_OFFSET + 12]
        end = raw.find(b"\xff")
        self.assertEqual(
            TextDecoder.decode_pokemon(raw[:end], preserve_unknown=True), "Vers le sac"
        )

    def test_no_residual_corruption(self):
        # The corrupt « Dépl.Dépl. où ? » must be gone everywhere it was read.
        self.assertNotIn("Dépl.Dépl.", self._follow(0xA6CAAC))


if __name__ == "__main__":
    unittest.main()
