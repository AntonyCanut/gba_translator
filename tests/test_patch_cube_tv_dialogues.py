"""Tests pour patch_cube_tv_dialogues_fr (B-98).

Les dialogues prologue (Cube V3) et mission télévision (Borrius) ont chacun
une entrée d'extraction et de traduction, mais sont trop longs pour leur slot
en place. Le pointeur du prologue et celui d'ouverture de la mission TV sont
déjà migrés par la passe générique (`--allow-relocate`) ; le second pointeur
de la mission TV (0x1FB07FE) précède un opcode non reconnu par le filtre de
sites plausibles et reste donc sur l'original anglais. Le patch relocalise la
traduction française (déjà présente dans combined_fr.txt) en espace libre et
repointe tout pointeur vivant restant.
"""

import os
import struct
import unittest
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder, TextEncoder
from languages.fr.patches import cube_tv_dialogues as patch

BASE = patch.ROM_POINTER_BASE


def _encode(text):
    return TextEncoder.encode(text, "pokemon")


def _decode(rom, offset):
    end = rom.find(b"\xff", offset)
    return TextDecoder.decode_pokemon(rom[offset:end], preserve_unknown=True)


def _deref(rom, cell):
    return int.from_bytes(rom[cell:cell + 4], "little") - BASE


class SyntheticRelocationTests(unittest.TestCase):
    """apply() sur une ROM synthétique : relocalisation + repointage."""

    OFFSET = 0x500
    CELL_A = 0x40
    CELL_B = 0x80

    def setUp(self):
        self._saved = dict(patch.TARGETS)
        patch.TARGETS.clear()
        patch.TARGETS[self.OFFSET] = "Vous n'avez pas encore"

    def tearDown(self):
        patch.TARGETS.clear()
        patch.TARGETS.update(self._saved)

    def _build(self, second_referrer=False):
        english = "You still have yet to gather data on the children."
        src = bytearray(0x4000)
        rom = bytearray(0x4000)
        enc_en = _encode(english)
        for data in (src, rom):
            data[self.OFFSET:self.OFFSET + len(enc_en)] = enc_en
            data[self.CELL_A:self.CELL_A + 4] = struct.pack("<I", BASE + self.OFFSET)
            if second_referrer:
                data[self.CELL_B:self.CELL_B + 4] = struct.pack("<I", BASE + self.OFFSET)
        rom[0x1000:0x3000] = b"\xff" * 0x2000  # espace libre pour relocaliser
        return rom, bytes(src)

    def test_relocates_and_repoints_all_referrers(self):
        rom, src = self._build(second_referrer=True)
        combined = {self.OFFSET: "Vous n'avez pas encore rassemblé de données."}

        stats = patch.apply(rom, combined, src)

        self.assertEqual(stats["targets"], 1)
        self.assertEqual(stats["repointed"], 2)
        self.assertEqual(stats["failed"], 0)
        new_a = _deref(rom, self.CELL_A)
        new_b = _deref(rom, self.CELL_B)
        self.assertEqual(new_a, new_b)
        self.assertNotEqual(new_a, self.OFFSET)
        result = _decode(rom, new_a)
        self.assertTrue(result.startswith("Vous n'avez pas encore"))
        self.assertEqual(rom[new_a + len(_encode(result)) - 1], 0xFF)
        self.assertNotIn(struct.pack("<I", BASE + self.OFFSET), bytes(rom))
        self.assertEqual(patch.verify(rom), [])

    def test_skips_when_already_fully_migrated(self):
        """A target whose only referrer was already repointed by the generic
        pass (no live pointer to the original left) is left untouched."""
        rom, src = self._build(second_referrer=False)
        combined = {self.OFFSET: "Vous n'avez pas encore rassemblé de données."}
        patch.apply(rom, combined, src)  # migrates the single referrer
        before = bytes(rom)

        stats = patch.apply(rom, combined, src)  # second pass: nothing left to do

        self.assertEqual(stats["targets"], 0)
        self.assertEqual(stats["skipped"], 1)
        self.assertEqual(bytes(rom), before)


FR_ROM = os.path.join("output", "roms", "GenedRom-fr.gba")
SOURCE_ROM = os.path.join("input", "roms", "englishrom.gba")
COMBINED = "languages/fr/combined_fr.txt"


@pytest.mark.rom
@unittest.skipUnless(
    os.path.isfile(FR_ROM) and os.path.isfile(SOURCE_ROM) and os.path.isfile(COMBINED),
    "ROM FR / source / combined_fr.txt absents",
)
class PatchOnRealRomTests(unittest.TestCase):
    """Bout en bout : sur la vraie ROM, le pointeur résout vers le texte FR."""

    def test_cube_tv_dialogues_are_french(self):
        rom = bytearray(Path(FR_ROM).read_bytes())
        source = Path(SOURCE_ROM).read_bytes()
        combined = patch.load_combined(Path(COMBINED))

        stats = patch.apply(rom, combined, source)
        self.assertEqual(stats["failed"], 0)
        self.assertEqual(patch.verify(rom), [])

        for offset, prefix in patch.TARGETS.items():
            self.assertNotIn(
                struct.pack("<I", BASE + offset), bytes(rom),
                msg=f"0x{offset:08X}: un pointeur vise encore l'original anglais",
            )
            self.assertIn(
                _encode(prefix)[:-1], bytes(rom),
                msg=f"0x{offset:08X}: préfixe FR « {prefix} » absent de la ROM",
            )


if __name__ == "__main__":
    unittest.main()
