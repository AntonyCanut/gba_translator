"""
Regression guard for GitHub issue #28 ("Traduction dresseur 'Campeur Chad'")
and its 2026-07-23 reopen ("Les textes des deux dresseurs juste avant le
combat sont repassés en anglais").

Camper Chad and his Combat Duo partner Kelsey share one dialogue cluster
around 0x1F62xxx:
  - 0x23E871:  the "Camper" trainer-class name (fixed-width table cell).
  - 0x1F62555: Chad's refusal line when Kelsey already took the second
    Combat Duo slot ("Zut ! Kelsey a pris ma place !").
  - 0x1F62651 / 0x1F626B4 / 0x1F6276C: the "We're a team!" greeting the two
    trainers say right before the double battle starts — this is the "les
    deux dresseurs juste avant le combat" text from the reopen.
  - 0x1F626E1: Kelsey's own pre-battle line ("As long as I lose with Chad,
    the outcome doesn't matter to me!").

Why this needs a live-pointer check, not a fixed-offset read
--------------------------------------------------------------
The French lines are longer than the English source, so the build pipeline
relocates them to free space and repoints the script's pointer instead of
writing in place. Reading the *original* offset after a successful
relocation returns stale leftover English bytes even when the fix is
correctly live elsewhere — a false failure. Conversely, each of these
offsets is referenced by several *coincidental* unaligned byte sequences
picked up by the raw pointer scanner (nearby pointers in the same table
overlap by 1-3 bytes and spell out this offset's address); only the single
4-byte-aligned site is a genuine reference, so these tests hardcode that
real site rather than re-deriving it.

The regression itself was a stale committed ``output/roms/GenedRom-fr.gba``
that had drifted out of sync with ``combined_fr.txt`` (see #37/#118
precedents in docs/20_TRANSLATION_PRESERVATION.md): a fresh ``make
build-fr`` from the current source files already produces the correct
French text, so these tests exist to catch the *next* stale rebuild before
it ships, not the pipeline logic itself.

Run standalone:   pytest tests/test_camper_chad_kelsey_dialogue_fr.py -v
Run via Makefile: make test-rom
"""

import struct
import unittest
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder

FR_ROM = Path("output/roms/GenedRom-fr.gba")

GBA_BASE = 0x08000000


def _read_at(rom: bytes, offset: int, limit: int = 200) -> str:
    chunk = rom[offset : offset + limit]
    end = chunk.find(b"\xff")
    raw = chunk if end == -1 else chunk[: end + 1]
    return TextDecoder.decode_pokemon(raw, preserve_unknown=True)


def _follow_ptr(rom: bytes, ptr_offset: int, limit: int = 400) -> str:
    """Return decoded text at the GBA pointer stored at ptr_offset.

    Relocated strings move; the site holding the pointer does not. Reading
    at a string's *original* offset after relocation returns leftover
    English bytes even when the translation is correctly live elsewhere.
    """
    if ptr_offset + 4 > len(rom):
        return ""
    ptr = struct.unpack_from("<I", rom, ptr_offset)[0]
    if ptr < GBA_BASE or ptr >= GBA_BASE + len(rom):
        return ""
    return _read_at(rom, ptr - GBA_BASE, limit)


@pytest.mark.rom
class TestCamperChadKelseyDialogueFR(unittest.TestCase):
    """Camper Chad / Kelsey dialogue must stay French across rebuilds."""

    @classmethod
    def setUpClass(cls):
        if not FR_ROM.exists():
            raise unittest.SkipTest(f"FR ROM not found: {FR_ROM}")
        cls.rom = FR_ROM.read_bytes()

    def test_camper_trainer_class_name(self):
        """0x23E871: fixed-width class-name cell, 'Camper' -> 'Campeur'."""
        text = _read_at(self.rom, 0x23E871, limit=13).strip()
        self.assertEqual(text, "Campeur")

    def test_kelsey_took_my_slot_line(self):
        """0x1F62555: in-place refusal line shown when Kelsey already
        joined Chad's Combat Duo slot."""
        text = _read_at(self.rom, 0x1F62555)
        self.assertIn("Zut !", text)
        self.assertIn("Kelsey a pris ma place", text)
        self.assertNotIn("Drat!", text)
        self.assertNotIn("took up my second slot", text)

    # ── "les deux dresseurs juste avant le combat" (2026-07-23 reopen) ──

    def test_team_greeting_camp_and_battle_variant(self):
        """ptr@0x1E87338 -> relocated: Chad's "We're a team! We camp and
        battle together!" greeting, said right before the double battle."""
        text = _follow_ptr(self.rom, 0x1E87338)
        self.assertIn("On campe et", text)
        self.assertIn("on se bat ensemble", text)
        self.assertNotIn("We camp and battle together", text)

    def test_team_greeting_battle_and_picnic_short(self):
        """ptr@0x1E87324 -> relocated: short "We're a team! We battle and
        picnic together!" variant of the pre-battle greeting."""
        text = _follow_ptr(self.rom, 0x1E87324)
        self.assertIn("On se bat et", text)
        self.assertIn("pique-nique à deux", text)
        self.assertNotIn("We battle and picnic together", text)

    def test_team_greeting_battle_and_picnic_long(self):
        """ptr@0x1E87334 -> relocated: long "We're a team! We battle and
        picnic together! But we can't battle you..." variant."""
        text = _follow_ptr(self.rom, 0x1E87334)
        self.assertIn("pique-nique à deux", text)
        self.assertIn("Mais on ne peut pas te combattre", text)
        self.assertNotIn("We battle and picnic together", text)

    def test_kelsey_loses_with_chad_line(self):
        """ptr@0x1E8732C -> 0x1F626E1: Kelsey's own pre-battle line ("As
        long as I lose with Chad, the outcome doesn't matter to me!")."""
        text = _follow_ptr(self.rom, 0x1E8732C)
        self.assertIn("perds avec Chad", text)
        self.assertNotIn("lose with Chad", text)


if __name__ == "__main__":
    unittest.main()
