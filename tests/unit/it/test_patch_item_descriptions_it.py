"""Regression guard for the combined_it.txt-driven general item-description
pass in ``languages/it/patches/item_names.py`` (``apply_item_desc_fixes``).

The ordinary-item descriptions (Poké Ball catch blurbs, Berry effects, sprays,
potions …) live in the fixed tables at 0x3D0000 / 0x7B0000 / 0xEB0000, keyed by
each item entry's ``+0x14`` description pointer. This suite drives the pass with
a synthetic mini-ROM covering the four behaviours that matter:

* in-place rewrite when the Italian text fits the English slot,
* relocation + repoint when it does not, with dedup for items that share a
  description pointer,
* skipping a cell the pipeline already translated (never clobber good Italian),
* graceful degradation (leave English, never crash) when free space is gone.
"""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from languages.it.patches import item_names as mod  # noqa: E402
from src.core.text_codec import TextDecoder, TextEncoder  # noqa: E402

ITEM_TABLE_BASE = mod.ITEM_TABLE_BASE
ITEM_STRIDE = mod.ITEM_STRIDE
DESC_PTR_OFFSET = mod.DESC_PTR_OFFSET
ROM_POINTER_BASE = mod.ROM_POINTER_BASE

# A description offset inside the general-item region and a free-space run that
# the FreeSpaceAllocator will accept (outside its EXCLUDE_RANGES, ≥ 1 KB of
# 0xFF in both the target and the reserved English ROM).
DESC_BASE = 0x3D4F00
FREE_RUN_START = 0x600000
FREE_RUN_LEN = 0x4000
ROM_SIZE = 0x880000  # large enough to hold the item table at 0x876074


def _put_string(rom: bytearray, offset: int, text: str) -> int:
    """Write ``text`` (encoded, 0xFF-terminated) at ``offset``; return length."""
    encoded = TextEncoder.encode_pokemon(text)
    rom[offset:offset + len(encoded)] = encoded
    return len(encoded)


def _set_item(rom: bytearray, index: int, name: str, desc_offset: int) -> int:
    base = ITEM_TABLE_BASE + index * ITEM_STRIDE
    raw = TextEncoder.encode_pokemon(name)
    rom[base:base + len(raw)] = raw
    rom[base + mod.NAME_FIELD:base + mod.NAME_FIELD + 2] = b"\xAB\x01"
    rom[base + DESC_PTR_OFFSET:base + DESC_PTR_OFFSET + 4] = struct.pack(
        "<I", desc_offset + ROM_POINTER_BASE
    )
    return base


def _live_desc(rom: bytearray, index: int) -> str:
    base = ITEM_TABLE_BASE + index * ITEM_STRIDE
    ptr = int.from_bytes(rom[base + DESC_PTR_OFFSET:base + DESC_PTR_OFFSET + 4], "little")
    off = ptr - ROM_POINTER_BASE
    end = rom.find(b"\xff", off)
    return TextDecoder.decode_pokemon(rom[off:end])


class TestApplyItemDescFixes(unittest.TestCase):
    def _blank_rom(self) -> bytearray:
        return bytearray(b"\xff" * ROM_SIZE)

    def test_in_place_when_it_fits(self):
        en = self._blank_rom()
        it = self._blank_rom()
        english = "A device for catching wild Pokemon."
        _put_string(en, DESC_BASE, english)
        _put_string(it, DESC_BASE, english)  # pipeline left it English
        _set_item(en, 0, "Poke Ball", DESC_BASE)
        _set_item(it, 0, "Poke Ball", DESC_BASE)

        italian = "Cattura un Pokemon."  # shorter than the English slot
        combined = {DESC_BASE: italian}
        patched = mod.apply_item_desc_fixes(it, combined=combined, source_rom=bytes(en))

        self.assertEqual(patched, 1)
        self.assertEqual(_live_desc(it, 0), italian)
        # Pointer unchanged (written in place at the original offset).
        base = ITEM_TABLE_BASE
        self.assertEqual(
            int.from_bytes(it[base + DESC_PTR_OFFSET:base + DESC_PTR_OFFSET + 4], "little"),
            DESC_BASE + ROM_POINTER_BASE,
        )

    def test_relocates_when_too_long(self):
        en = self._blank_rom()
        it = self._blank_rom()
        english = "Short."
        _put_string(en, DESC_BASE, english)
        _put_string(it, DESC_BASE, english)
        _set_item(en, 0, "Master Ball", DESC_BASE)
        _set_item(it, 0, "Master Ball", DESC_BASE)

        italian = "Una Ball di altissimo livello che cattura\nqualsiasi Pokemon senza mai fallire."
        combined = {DESC_BASE: italian}
        patched = mod.apply_item_desc_fixes(it, combined=combined, source_rom=bytes(en))

        self.assertEqual(patched, 1)
        # Repointed away from the (too-small) original slot into the free run.
        base = ITEM_TABLE_BASE
        new_ptr = int.from_bytes(
            it[base + DESC_PTR_OFFSET:base + DESC_PTR_OFFSET + 4], "little"
        ) - ROM_POINTER_BASE
        self.assertNotEqual(new_ptr, DESC_BASE)
        self.assertGreaterEqual(new_ptr, FREE_RUN_START)
        self.assertEqual(_live_desc(it, 0), italian.replace("\\n", "\n"))

    def test_shared_pointer_is_relocated_once(self):
        en = self._blank_rom()
        it = self._blank_rom()
        english = "Short."
        _put_string(en, DESC_BASE, english)
        _put_string(it, DESC_BASE, english)
        # Two items whose English description pointer is the same offset.
        _set_item(en, 0, "Master Ball", DESC_BASE)
        _set_item(it, 0, "Master Ball", DESC_BASE)
        _set_item(en, 1, "Master Ball2", DESC_BASE)
        _set_item(it, 1, "Master Ball2", DESC_BASE)

        italian = "Una Ball di altissimo livello che cattura\nqualsiasi Pokemon senza mai fallire."
        combined = {DESC_BASE: italian}
        patched = mod.apply_item_desc_fixes(it, combined=combined, source_rom=bytes(en))

        self.assertEqual(patched, 2)
        b0, b1 = ITEM_TABLE_BASE, ITEM_TABLE_BASE + ITEM_STRIDE
        p0 = int.from_bytes(it[b0 + DESC_PTR_OFFSET:b0 + DESC_PTR_OFFSET + 4], "little")
        p1 = int.from_bytes(it[b1 + DESC_PTR_OFFSET:b1 + DESC_PTR_OFFSET + 4], "little")
        self.assertEqual(p0, p1)  # both point at the single relocated copy
        self.assertEqual(_live_desc(it, 0), italian)
        self.assertEqual(_live_desc(it, 1), italian)

    def test_skips_already_translated(self):
        en = self._blank_rom()
        it = self._blank_rom()
        english = "A device for catching wild Pokemon."
        _put_string(en, DESC_BASE, english)
        # The pipeline already relocated + translated this one elsewhere.
        already = "Gia in italiano."
        _put_string(it, 0x3D5300, already)
        _set_item(en, 0, "Poke Ball", DESC_BASE)
        _set_item(it, 0, "Poke Ball", 0x3D5300)

        combined = {DESC_BASE: "Testo che NON deve essere scritto."}
        patched = mod.apply_item_desc_fixes(it, combined=combined, source_rom=bytes(en))

        self.assertEqual(patched, 0)
        self.assertEqual(_live_desc(it, 0), already)

    def test_skips_when_no_combined_entry(self):
        en = self._blank_rom()
        it = self._blank_rom()
        english = "A device for catching wild Pokemon."
        _put_string(en, DESC_BASE, english)
        _put_string(it, DESC_BASE, english)
        _set_item(en, 0, "Great Ball", DESC_BASE)
        _set_item(it, 0, "Great Ball", DESC_BASE)

        patched = mod.apply_item_desc_fixes(it, combined={}, source_rom=bytes(en))
        self.assertEqual(patched, 0)
        self.assertEqual(_live_desc(it, 0), english)

    def test_ignores_pointers_outside_general_regions(self):
        # A description pointer in the TM/MN region (0xA30000) must be left to
        # the dedicated tm_item_descriptions pass, never touched here. That
        # region sits above the item table, so this test uses a bigger ROM.
        big = 0xA40000
        en = bytearray(b"\xff" * big)
        it = bytearray(b"\xff" * big)
        tm_off = 0xA31000
        english = "Short."
        _put_string(en, tm_off, english)
        _put_string(it, tm_off, english)
        _set_item(en, 0, "TM01", tm_off)
        _set_item(it, 0, "TM01", tm_off)

        combined = {tm_off: "Testo lungo che sarebbe rilocato se toccato."}
        patched = mod.apply_item_desc_fixes(it, combined=combined, source_rom=bytes(en))
        self.assertEqual(patched, 0)
        self.assertEqual(_live_desc(it, 0), english)

    def test_no_free_space_leaves_english(self):
        # A ROM with no allocatable free run: a too-long Italian description is
        # left English rather than crashing the build.
        en = bytearray(b"\x00" * ROM_SIZE)
        it = bytearray(b"\x00" * ROM_SIZE)
        english = "Short."
        _put_string(en, DESC_BASE, english)
        _put_string(it, DESC_BASE, english)
        _set_item(en, 0, "Master Ball", DESC_BASE)
        _set_item(it, 0, "Master Ball", DESC_BASE)

        italian = "Una Ball di altissimo livello che cattura\nqualsiasi Pokemon senza mai fallire."
        combined = {DESC_BASE: italian}
        patched = mod.apply_item_desc_fixes(it, combined=combined, source_rom=bytes(en))
        self.assertEqual(patched, 0)
        self.assertEqual(_live_desc(it, 0), english)

    def test_idempotent(self):
        en = self._blank_rom()
        it = self._blank_rom()
        english = "A device for catching wild Pokemon."
        _put_string(en, DESC_BASE, english)
        _put_string(it, DESC_BASE, english)
        _set_item(en, 0, "Poke Ball", DESC_BASE)
        _set_item(it, 0, "Poke Ball", DESC_BASE)

        italian = "Cattura un Pokemon."
        combined = {DESC_BASE: italian}
        self.assertEqual(mod.apply_item_desc_fixes(it, combined=combined, source_rom=bytes(en)), 1)
        # Second run: the cell now reads Italian (differs from English) → skipped.
        self.assertEqual(mod.apply_item_desc_fixes(it, combined=combined, source_rom=bytes(en)), 0)
        self.assertEqual(_live_desc(it, 0), italian)


if __name__ == "__main__":
    unittest.main()
