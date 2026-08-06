"""Regression tests for context-sensitive FR PC/Box « Move » labels.

The tight 4-byte « Move » cells (0x418484, 0x418EB5, 0xA4E1F1) cannot hold the
5-byte « Dépl. » in place — the inject pass overflowed 0xA4E1F1 into the next
string, producing the corrupt « Dépl.Dépl. où ? » the reporter photographed. The
patch relocates every such string to a baseline-free 0xFF block and repoints all
their pointers. The selection menu renders « Déplacer » (issue #173), while the
compact secondary menu and HUD keep a terminated « Dépl. » (issue #29). The
pointer-less mail submenu « Move To Bag » is fixed in place to « Vers le sac ».
"""

import struct
import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.fr.patches.pc_move_labels import (
    DEFAULT_BOX_PREFIX_EN_OFFSET,
    DEFAULT_BOX_PREFIX_FR,
    DEFAULT_BOX_PREFIX_POINTER,
    DEFAULT_BOX_PREFIX_SLOT,
    FREESPACE_BASE,
    MAIL_MOVE_TO_BAG_EN,
    MAIL_MOVE_TO_BAG_FR,
    MAIL_MOVE_TO_BAG_OFFSET,
    MAIL_MOVE_TO_BAG_PREIMAGES,
    MAIN_MENU_RELOCATIONS,
    ROM_BASE,
    _RELOCATIONS,
    _enc,
    apply,
)
from languages.fr.dedicated_patch_offsets import GENERIC_PLACEHOLDER_TRANSLATIONS
from scripts import apply_combined_fr
from src.core.text_codec import TextDecoder, TextEncoder

BUILT_FR_ROM = Path(__file__).parent.parent / "output" / "roms" / "GenedRom-fr.gba"
COMBINED_FR = Path(__file__).parent.parent / "languages" / "fr" / "combined_fr.txt"
ROM_SIZE = 0x2000000

PC_MAIN_MENU_LABELS = {
    0x41858D: "Déplacer Pokémon",
    0x41859A: "Déplacer objet",
    0x4185A5: "Salut !",
}

PC_MAIN_MENU_POINTERS = {
    0x3CDA20: "Déplacer Pokémon",
    0x3CDA28: "Déplacer objet",
    0x3CDA40: "Salut !",
}

PC_BOX_SELECTION_POINTERS = (0x3D3548, 0x9A41C4)
PC_SECONDARY_MOVE_POINTER = 0xA6CAAC
PC_SELECTION_STATUS_OFFSET = 0x41825C
PC_SELECTION_STATUS_POINTERS = (0x3CEAA8, 0x3CEB40, 0x9A427C, 0x9A4314)
PC_SELECTION_STATUS_SOURCE = "{DYNAMIC} sélectionné."
PC_SELECTION_STATUS_DECODED = "<0xF7>  sélectionné."

EMPTY_MAIL_MESSAGE_OFFSET = 0x4177EE
EMPTY_MAIL_MESSAGE_POINTERS = (0xEB938, 0xEB9B0)
EMPTY_MAIL_MESSAGE_FR = "Pas de lettre ici."


def _fake_rom() -> bytearray:
    rom = bytearray(b"\xff" * ROM_SIZE)
    rom[0xB2] = 0x96
    # Seed each pointer site with its original cell address.
    for entry in _RELOCATIONS:
        for loc, orig in entry["orig"].items():
            struct.pack_into("<I", rom, loc, ROM_BASE | orig)
    for entry in MAIN_MENU_RELOCATIONS:
        struct.pack_into("<I", rom, entry["pointer"], ROM_BASE | entry["orig"])
    # Seed the walked mail string with its English original.
    rom[MAIL_MOVE_TO_BAG_OFFSET:MAIL_MOVE_TO_BAG_OFFSET + len(MAIL_MOVE_TO_BAG_EN)] = (
        MAIL_MOVE_TO_BAG_EN
    )
    struct.pack_into(
        "<I", rom, DEFAULT_BOX_PREFIX_POINTER, ROM_BASE | DEFAULT_BOX_PREFIX_EN_OFFSET
    )
    return rom


def _decode_at(rom: bytes, off: int) -> str:
    raw = bytes(rom[off:off + 64])
    end = raw.find(b"\xff")
    return TextDecoder.decode_pokemon(raw[: end if end >= 0 else 64], preserve_unknown=True)


def _load_last_wins() -> dict[int, str]:
    mapping = {}
    with COMBINED_FR.open("r", encoding="utf-8", newline="") as stream:
        for raw in stream:
            line = raw.rstrip("\r\n")
            if not line.startswith("0x"):
                continue
            offset, separator, text = line.partition(":")
            if separator:
                mapping[int(offset, 16)] = text.removeprefix(" ")
    return mapping


class TestConstants(unittest.TestCase):
    def test_pc_selection_status_source_uses_requested_wording(self):
        mapping = _load_last_wins()
        self.assertEqual(mapping[PC_SELECTION_STATUS_OFFSET], PC_SELECTION_STATUS_SOURCE)

    def test_pc_main_menu_source_uses_full_requested_labels(self):
        mapping = _load_last_wins()
        for offset, expected in PC_MAIN_MENU_LABELS.items():
            self.assertEqual(mapping[offset], expected, f"offset 0x{offset:X}")

    def test_release_csv_keeps_historical_allocator_footprint(self):
        combined = dict(PC_MAIN_MENU_LABELS)
        apply_combined_fr._exclude_dedicated_offsets(combined, [])
        self.assertEqual(combined, GENERIC_PLACEHOLDER_TRANSLATIONS)

    def test_allocator_placeholders_never_apply_to_other_languages(self):
        combined = dict(PC_MAIN_MENU_LABELS)
        apply_combined_fr._exclude_dedicated_offsets(
            combined, [], dedicated_offsets=frozenset()
        )
        self.assertEqual(combined, PC_MAIN_MENU_LABELS)

    def test_mail_replacement_fits_in_place(self):
        # « Vers le sac » must be no longer than the English « Move To Bag » cell.
        self.assertEqual(len(MAIL_MOVE_TO_BAG_FR), len(MAIL_MOVE_TO_BAG_EN))

    def test_all_mail_preimages_match_fixed_cell_width(self):
        for preimage in MAIL_MOVE_TO_BAG_PREIMAGES:
            self.assertEqual(len(preimage), len(MAIL_MOVE_TO_BAG_FR))

    def test_freespace_base_is_addressable_rom(self):
        self.assertLess(FREESPACE_BASE, ROM_SIZE)


class TestApply(unittest.TestCase):
    def test_all_pointers_render_configured_label(self):
        rom = _fake_rom()
        n = apply(rom)
        # 7 contextual + 3 main + 1 box pointer + 1 in-place mail string.
        self.assertEqual(n, 12)
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

    def test_box_selection_uses_full_move_label(self):
        rom = _fake_rom()
        apply(rom)

        for loc in PC_BOX_SELECTION_POINTERS:
            ptr = struct.unpack_from("<I", rom, loc)[0]
            self.assertEqual(_decode_at(rom, ptr - ROM_BASE), "Déplacer")

    def test_secondary_move_menu_keeps_compact_label(self):
        rom = _fake_rom()
        apply(rom)

        ptr = struct.unpack_from("<I", rom, PC_SECONDARY_MOVE_POINTER)[0]
        self.assertEqual(_decode_at(rom, ptr - ROM_BASE), "Dépl.")

    def test_mail_move_to_bag(self):
        rom = _fake_rom()
        apply(rom)
        self.assertEqual(_decode_at(rom, MAIL_MOVE_TO_BAG_OFFSET), "Vers le sac")

    def test_default_box_prefix_is_relocated_without_generic_injector(self):
        rom = _fake_rom()
        apply(rom)

        ptr = struct.unpack_from("<I", rom, DEFAULT_BOX_PREFIX_POINTER)[0]
        self.assertEqual(ptr, ROM_BASE | DEFAULT_BOX_PREFIX_SLOT)
        self.assertEqual(_decode_at(rom, DEFAULT_BOX_PREFIX_SLOT), DEFAULT_BOX_PREFIX_FR)

    def test_main_menu_labels_are_relocated_without_generic_injector(self):
        rom = _fake_rom()
        apply(rom)

        for entry in MAIN_MENU_RELOCATIONS:
            ptr = struct.unpack_from("<I", rom, entry["pointer"])[0]
            self.assertEqual(ptr, ROM_BASE | entry["slot"])
            self.assertEqual(_decode_at(rom, entry["slot"]), entry["text"])

    def test_main_menu_accepts_allocator_stable_legacy_payload(self):
        rom = _fake_rom()
        entry = MAIN_MENU_RELOCATIONS[0]
        legacy_slot = 0x100000
        legacy_blob = _enc(entry["legacy"]) + b"\xff"
        rom[legacy_slot:legacy_slot + len(legacy_blob)] = legacy_blob
        struct.pack_into("<I", rom, entry["pointer"], ROM_BASE | legacy_slot)

        apply(rom)

        self.assertEqual(
            struct.unpack_from("<I", rom, entry["pointer"])[0],
            ROM_BASE | entry["slot"],
        )

    def test_normalizes_generic_abbreviated_mail_label(self):
        rom = _fake_rom()
        legacy_fr = _enc("Dépl au sac")
        rom[MAIL_MOVE_TO_BAG_OFFSET:MAIL_MOVE_TO_BAG_OFFSET + len(legacy_fr)] = legacy_fr

        apply(rom)

        self.assertEqual(_decode_at(rom, MAIL_MOVE_TO_BAG_OFFSET), "Vers le sac")

    def test_idempotent(self):
        rom = _fake_rom()
        self.assertEqual(apply(rom), 12)
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

    def test_box_selection_uses_full_move_label(self):
        for loc in PC_BOX_SELECTION_POINTERS:
            self.assertEqual(self._follow(loc), "Déplacer", f"ptr@0x{loc:X}")

    def test_secondary_move_menu_keeps_compact_label(self):
        self.assertEqual(self._follow(PC_SECONDARY_MOVE_POINTER), "Dépl.")

    def test_selection_status_uses_requested_wording(self):
        for loc in PC_SELECTION_STATUS_POINTERS:
            self.assertEqual(
                self._follow(loc),
                PC_SELECTION_STATUS_DECODED,
                f"ptr@0x{loc:X}",
            )

    def test_selection_status_keeps_dynamic_control_and_terminator(self):
        expected = b"\xf7\x00" + TextEncoder.encode_pokemon(" sélectionné.")

        for loc in PC_SELECTION_STATUS_POINTERS:
            ptr = struct.unpack_from("<I", self.rom, loc)[0]
            self.assertEqual(ptr, ROM_BASE | PC_SELECTION_STATUS_OFFSET)
        actual = self.rom[
            PC_SELECTION_STATUS_OFFSET:PC_SELECTION_STATUS_OFFSET + len(expected)
        ]
        self.assertEqual(actual, expected)

    def test_hud_hint(self):
        for loc in (0xC05D8, 0xC12E0, 0xC283C, 0xC4FE8):
            self.assertEqual(self._follow(loc), "<0xF8>ÏDépl.", f"ptr@0x{loc:X}")

    def _assert_main_menu_label(self, loc: int):
        expected = PC_MAIN_MENU_POINTERS[loc]
        ptr = struct.unpack_from("<I", self.rom, loc)[0]
        off = ptr - ROM_BASE
        encoded = _enc(expected)
        self.assertEqual(self._follow(loc), expected, f"ptr@0x{loc:X}")
        self.assertEqual(self.rom[off:off + len(encoded)], encoded)
        self.assertEqual(self.rom[off + len(encoded)], 0xFF)

    def test_box_main_menu_label_and_terminator(self):
        self._assert_main_menu_label(0x3CDA20)

    def test_item_and_exit_main_menu_labels_and_terminators(self):
        for loc in (0x3CDA28, 0x3CDA40):
            self._assert_main_menu_label(loc)

    def test_mail_move_to_bag(self):
        raw = self.rom[MAIL_MOVE_TO_BAG_OFFSET:MAIL_MOVE_TO_BAG_OFFSET + 12]
        end = raw.find(b"\xff")
        self.assertEqual(
            TextDecoder.decode_pokemon(raw[:end], preserve_unknown=True), "Vers le sac"
        )

    def test_empty_mail_message_uses_requested_wording_and_wait_control(self):
        expected = _enc(f"{EMPTY_MAIL_MESSAGE_FR} ") + b"\xfc\x09\xff"

        for loc in EMPTY_MAIL_MESSAGE_POINTERS:
            ptr = struct.unpack_from("<I", self.rom, loc)[0]
            self.assertEqual(ptr, ROM_BASE | EMPTY_MAIL_MESSAGE_OFFSET)
            actual = self.rom[
                EMPTY_MAIL_MESSAGE_OFFSET:EMPTY_MAIL_MESSAGE_OFFSET + len(expected)
            ]
            self.assertEqual(actual, expected, f"ptr@0x{loc:X}")

        visible = TextDecoder.decode_pokemon(expected[:-3], preserve_unknown=True)
        self.assertEqual(visible.rstrip(), EMPTY_MAIL_MESSAGE_FR)

    def test_no_residual_corruption(self):
        # The corrupt « Dépl.Dépl. où ? » must be gone everywhere it was read.
        self.assertNotIn("Dépl.Dépl.", self._follow(0xA6CAAC))


if __name__ == "__main__":
    unittest.main()
