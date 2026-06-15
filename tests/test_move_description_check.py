"""Tests pour la vérification des descriptions d'attaque."""

import os
import struct
import unittest

import pytest

from src.core.move_description_check import (
    MAX_LINES,
    MAX_LINE_WIDTH,
    MOVE_DESCRIPTION_TABLE,
    MOVE_NAME_TABLE,
    MOVE_NAME_STRIDE,
    GBA_ROM_BASE,
    check_all_moves,
    check_description_text,
    check_move,
    read_move_description,
    read_move_name,
)

FR_ROM = os.path.join("output", "roms", "GenedRom-fr.gba")


class TestCheckDescriptionText(unittest.TestCase):
    """Logique pure de mesure, sans ROM."""

    def test_short_description_fits(self):
        text = "Le lanceur fait les\ngros yeux."
        lines, too_many = check_description_text(text)
        self.assertFalse(too_many)
        self.assertEqual(len(lines), 2)
        self.assertTrue(all(not ln.too_wide for ln in lines))

    def test_five_narrow_lines_fit(self):
        text = "\n".join(["ligne courte"] * 5)
        lines, too_many = check_description_text(text)
        self.assertFalse(too_many)
        self.assertTrue(all(not ln.too_wide for ln in lines))

    def test_six_lines_overflow_vertically(self):
        text = "\n".join(["a"] * 6)
        lines, too_many = check_description_text(text)
        self.assertTrue(too_many)
        self.assertEqual(len(lines), 6)

    def test_wide_line_overflows_horizontally(self):
        # 30 caractères larges : nettement au-dessus de 130 px.
        text = "Mmmmmmmmmmmmmmmmmmmmmmmmmmmmmm"
        lines, too_many = check_description_text(text)
        self.assertFalse(too_many)
        self.assertTrue(lines[0].too_wide)
        self.assertGreater(lines[0].width, MAX_LINE_WIDTH)

    def test_width_threshold_is_respected(self):
        narrow = "iiii"
        lines, _ = check_description_text(narrow, max_width=1000)
        self.assertFalse(lines[0].too_wide)
        lines2, _ = check_description_text(narrow, max_width=1)
        self.assertTrue(lines2[0].too_wide)

    def test_line_chars_counted(self):
        lines, _ = check_description_text("abcde")
        self.assertEqual(lines[0].chars, 5)


class TestSyntheticRom(unittest.TestCase):
    """Lecture table/pointeurs sur une ROM synthétique minimale."""

    def _build_rom(self, index: int, name: bytes, desc: bytes) -> bytearray:
        rom = bytearray(0x0100_0000)  # 16 Mo, taille GBA minimale
        # Nom de l'attaque dans la table fixe.
        nbase = MOVE_NAME_TABLE + index * MOVE_NAME_STRIDE
        rom[nbase : nbase + len(name)] = name + b"\xff"
        # Description placée dans une zone libre, pointeur dans la table.
        desc_off = 0x00F0_0000
        rom[desc_off : desc_off + len(desc)] = desc + b"\xff"
        ptr_off = MOVE_DESCRIPTION_TABLE + index * 4
        struct.pack_into("<I", rom, ptr_off, GBA_ROM_BASE + desc_off)
        return rom

    def test_reads_name_and_description(self):
        # "Test" -> octets Pokemon ; description simple.
        from src.core.text_codec import TextEncoder

        name = TextEncoder.encode_pokemon("Charge")[:-1]  # sans terminateur
        desc = TextEncoder.encode_pokemon("Une charge\nbasique.")[:-1]
        rom = self._build_rom(5, name, desc)
        self.assertEqual(read_move_name(rom, 5), "Charge")
        self.assertEqual(read_move_description(rom, 5), "Une charge\nbasique.")

    def test_check_move_fits(self):
        from src.core.text_codec import TextEncoder

        name = TextEncoder.encode_pokemon("Charge")[:-1]
        desc = TextEncoder.encode_pokemon("Une charge\nbasique.")[:-1]
        rom = self._build_rom(5, name, desc)
        result = check_move(rom, 5)
        self.assertIsNotNone(result)
        self.assertTrue(result.fits)
        self.assertEqual(result.reasons, [])

    def test_check_move_too_many_lines(self):
        from src.core.text_codec import TextEncoder

        name = TextEncoder.encode_pokemon("Charge")[:-1]
        desc = TextEncoder.encode_pokemon("\n".join(["a"] * 7))[:-1]
        rom = self._build_rom(5, name, desc)
        result = check_move(rom, 5)
        self.assertFalse(result.fits)
        self.assertTrue(result.too_many_lines)
        self.assertTrue(result.reasons)

    def test_invalid_pointer_returns_none(self):
        rom = bytearray(0x0100_0000)
        # Pointeur nul -> invalide.
        self.assertIsNone(read_move_description(rom, 5))
        self.assertIsNone(check_move(rom, 5))


@pytest.mark.rom
@unittest.skipUnless(os.path.isfile(FR_ROM), f"ROM FR absente ({FR_ROM})")
class TestRealFrRom(unittest.TestCase):
    """Vérité terrain : ROM FR corrigée par patch_move_descriptions_fr.py.

    Avant correction, Morsure (« …faire tressailIl grogne… ») et Jet-Pierres
    débordaient et fusionnaient avec l'attaque suivante (cf. captures du
    ticket). Après le patch de re-wrap/relocalisation, toutes les
    descriptions tiennent dans la fenêtre de 5 lignes.
    """

    @classmethod
    def setUpClass(cls):
        with open(FR_ROM, "rb") as f:
            cls.rom = bytearray(f.read())

    def _find_move(self, name: str) -> int:
        for i in range(1, 894):
            if read_move_name(self.rom, i) == name:
                return i
        raise AssertionError(f"attaque introuvable : {name}")

    def test_grozyeux_fits(self):
        idx = self._find_move("Groz'Yeux")
        result = check_move(self.rom, idx)
        self.assertTrue(result.fits, result.reasons)

    def test_morsure_fits_and_unmerged(self):
        idx = self._find_move("Morsure")
        result = check_move(self.rom, idx)
        self.assertTrue(result.fits, result.reasons)
        # La fusion avec l'attaque suivante (« grogne », Charme) a disparu.
        # Le terme officiel « apeurer » remplace « tressaillir » (cf. ticket).
        self.assertIn("apeurer", result.description)
        self.assertNotIn("tressaillir", result.description)
        self.assertNotIn("grogne", result.description)

    def test_jetpierres_fits(self):
        idx = self._find_move("Jet-Pierres")
        result = check_move(self.rom, idx)
        self.assertTrue(result.fits, result.reasons)
        self.assertNotIn("tremblement", result.description)

    def test_all_moves_fit(self):
        # Garde-fou de non-régression : aucune description ne déborde.
        results = check_all_moves(self.rom)
        self.assertGreater(len(results), 100)
        overflow = [r for r in results if not r.fits]
        self.assertEqual(
            overflow, [],
            "descriptions débordantes : "
            + ", ".join(f"{r.name} {r.reasons}" for r in overflow[:10]),
        )


if __name__ == "__main__":
    unittest.main()
