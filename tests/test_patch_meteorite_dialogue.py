"""Tests pour patch_meteorite_dialogue_fr.

Le monologue météorite de Borrius (0x7A9A75, 1046 octets) dépasse le plafond de
1000 octets de l'extracteur de pointeurs : il n'entre jamais dans l'extraction,
donc ni la CSV trilingue ni le JSON de traduction ne le contiennent, et la ROM
buildée affiche le texte anglais. Le patch relocalise la traduction française
(déjà présente dans combined_fr.txt) en espace libre et repointe le pointeur.
"""

import os
import struct
import unittest
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder, TextEncoder
from scripts import patch_meteorite_dialogue_fr as patch

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
    CELL = 0x40

    def setUp(self):
        self._saved = dict(patch.TARGETS)
        patch.TARGETS.clear()
        patch.TARGETS[self.OFFSET] = "Il y a trente ans"

    def tearDown(self):
        patch.TARGETS.clear()
        patch.TARGETS.update(self._saved)

    def _build(self):
        english = "Thirty years ago, a large meteorite was hurtling towards Borrius."
        src = bytearray(0x4000)
        rom = bytearray(0x4000)
        enc_en = _encode(english)
        for data in (src, rom):
            data[self.OFFSET:self.OFFSET + len(enc_en)] = enc_en
            data[self.CELL:self.CELL + 4] = struct.pack("<I", BASE + self.OFFSET)
        rom[0x1000:0x3000] = b"\xff" * 0x2000  # espace libre pour relocaliser
        return rom, bytes(src)

    def test_relocates_and_repoints(self):
        rom, src = self._build()
        combined = {self.OFFSET: "Il y a trente ans, une grande météorite\nfonçait vers Borrius."}

        stats = patch.apply(rom, combined, src)

        self.assertEqual(stats["targets"], 1)
        self.assertEqual(stats["repointed"], 1)
        self.assertEqual(stats["failed"], 0)
        # Le pointeur ne vise plus l'original anglais…
        new_offset = _deref(rom, self.CELL)
        self.assertNotEqual(new_offset, self.OFFSET)
        # …mais une copie française proprement terminée.
        result = _decode(rom, new_offset)
        self.assertTrue(result.startswith("Il y a trente ans"))
        self.assertIn("météorite", result)
        self.assertEqual(rom[new_offset + len(_encode(result)) - 1], 0xFF)
        # Plus aucun pointeur vivant vers l'original.
        self.assertNotIn(struct.pack("<I", BASE + self.OFFSET), bytes(rom))
        self.assertEqual(patch.verify(rom), [])

    def test_idempotent(self):
        rom, src = self._build()
        combined = {self.OFFSET: "Il y a trente ans, une grande météorite fonçait."}

        patch.apply(rom, combined, src)
        before = bytes(rom)
        stats = patch.apply(rom, combined, src)  # second passage

        self.assertEqual(stats["targets"], 0)
        self.assertEqual(stats["skipped"], 1)
        self.assertEqual(bytes(rom), before)  # aucune relocalisation en double


FR_ROM = os.path.join("output", "roms", "GenedRom-fr.gba")
SOURCE_ROM = os.path.join("input", "roms", "englishrom.gba")
COMBINED = "combined_fr.txt"


@pytest.mark.rom
@unittest.skipUnless(
    os.path.isfile(FR_ROM) and os.path.isfile(SOURCE_ROM) and os.path.isfile(COMBINED),
    "ROM FR / source / combined_fr.txt absents",
)
class PatchOnRealRomTests(unittest.TestCase):
    """Bout en bout : sur la vraie ROM, le pointeur résout vers le texte FR."""

    def test_long_dialogues_are_french(self):
        rom = bytearray(Path(FR_ROM).read_bytes())
        source = Path(SOURCE_ROM).read_bytes()
        combined = patch.load_combined(Path(COMBINED))

        stats = patch.apply(rom, combined, source)
        self.assertEqual(stats["failed"], 0)
        self.assertEqual(patch.verify(rom), [])

        # Pour CHAQUE cible : plus aucun pointeur vivant vers l'original anglais,
        # et la copie relocalisée contient bien le préfixe français attendu.
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
