"""Tests for patch_mission_descriptions_fr.

The bounty board renders a mission description in a narrow, non-scrolling
3-line window. The generic builder re-wraps every ``dialogue`` string to the
192 px / 2-line dialogue box and rewrites later ``\\n`` to a ``{SCROLL}`` (0xFA)
code — which overflows and mangles the mission window. This patch runs last and
rewrites each description verbatim from combined_fr.txt (no re-wrap, no scroll),
relocating + repointing via the *English*-ROM pointer site so it wins even when
the generic pass already relocated (and mangled) the string.
"""

import struct
import unittest

from src.core.text_codec import TextDecoder, TextEncoder
from languages.fr.patches import mission_descriptions as patch

BASE = patch.ROM_POINTER_BASE


def _encode(text):
    return TextEncoder.encode(text, "pokemon")


def _decode(rom, offset):
    end = rom.find(b"\xff", offset)
    return TextDecoder.decode_pokemon(rom[offset:end], preserve_unknown=True)


def _deref(rom, cell):
    return int.from_bytes(rom[cell:cell + 4], "little") - BASE


class MissionPatchTests(unittest.TestCase):
    OFFSET = 0x500
    CELL = 0x40
    EN = "A young boy in a Pikachu costume\nhas run away from home to Route 8!"
    FR = "Un garçon déguisé en Pikachu\na fui vers la Route 8 !\nRamène-le sain et sauf."

    def setUp(self):
        self._saved = patch.TARGETS
        patch.TARGETS = (self.OFFSET,)

    def tearDown(self):
        patch.TARGETS = self._saved

    def _rom_pair(self, fr_cell_target=None):
        """Build (fr_rom, src_rom). ``fr_cell_target`` simulates a prior
        relocation by the generic pass (the FR cell already points elsewhere)."""
        src = bytearray(0x4000)
        rom = bytearray(0x4000)
        enc_en = _encode(self.EN)
        for data in (src, rom):
            data[self.OFFSET:self.OFFSET + len(enc_en)] = enc_en
        # source cell -> original EN string (the stable site)
        src[self.CELL:self.CELL + 4] = struct.pack("<I", BASE + self.OFFSET)
        rom[self.CELL:self.CELL + 4] = struct.pack(
            "<I", BASE + (fr_cell_target if fr_cell_target is not None else self.OFFSET)
        )
        rom[0x1000:0x3000] = b"\xff" * 0x2000  # free space to relocate into
        return rom, bytes(src)

    def test_relocates_repoints_and_keeps_three_lines(self):
        rom, src = self._rom_pair()
        stats = patch.apply(rom, {self.OFFSET: self.FR}, src)

        self.assertEqual(stats["targets"], 1)
        self.assertEqual(stats["repointed"], 1)
        self.assertEqual(stats["failed"], 0)

        new = _deref(rom, self.CELL)
        self.assertNotEqual(new, self.OFFSET)
        text = _decode(rom, new)
        self.assertEqual(text, self.FR)
        # at most 3 source lines, and never a scroll code (0xFA)
        self.assertLessEqual(text.count("\n"), 2)
        encoded = _encode(self.FR)
        self.assertNotIn(0xFA, encoded[:-1])

    def test_wins_over_prior_generic_relocation(self):
        # Generic pass already moved the (mangled) string to 0x800 and repointed
        # the FR cell there. The patch must still fix it via the EN-ROM site.
        rom, src = self._rom_pair(fr_cell_target=0x800)
        mangled = _encode("Pikachu costume garbage with {SCROLL} inside".replace(
            "{SCROLL}", ""))
        rom[0x800:0x800 + len(mangled)] = mangled

        stats = patch.apply(rom, {self.OFFSET: self.FR}, src)
        self.assertEqual(stats["targets"], 1)
        new = _deref(rom, self.CELL)
        self.assertNotIn(new, (self.OFFSET, 0x800))
        self.assertEqual(_decode(rom, new), self.FR)

    def test_verify_flags_scroll_code(self):
        rom, src = self._rom_pair()
        patch.apply(rom, {self.OFFSET: self.FR}, src)
        # a clean run verifies cleanly
        self.assertEqual(patch.verify(rom, src, {self.OFFSET: self.FR}), [])


if __name__ == "__main__":
    unittest.main()
