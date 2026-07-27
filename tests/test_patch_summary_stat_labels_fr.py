"""Tests de régression des libellés de stats FR de la page « Capacités » (#145).

ATTACK / SP.ATK / SP.DEF / SPEED sont des images de mots gravées dans le
tileset LZ77 0x00E9A460 : aucune passe de traduction ne les atteint, seul
``languages/fr/patches/summary_stat_labels.py`` les traduit.

Le test le plus important est :class:`TestModelMatchesEnglishSheet` : il
revérifie contre la ROM anglaise que la fonte et le modèle de gélule
reproduisent **au pixel près** les cinq gélules de statistiques d'origine. Si
ce test tombe, le patch redessine sur une base erronée et doit être resynchronisé
plutôt que forcé.
"""

import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.fr.patches.font import lz77_decompress
from languages.fr.patches.summary_stat_labels import (
    BACKGROUND,
    BLOCK,
    GLYPHS,
    GLYPH_ROWS,
    LABELS,
    LETTER,
    PILL,
    PILL_HEIGHT,
    PILL_X0,
    PILL_X1,
    SLOT_LEN,
    apply_patches,
    capsule_mask,
    fits,
    label_pixels,
    letter_mask,
    patch_sheet,
    px_get,
    read_label,
    render_word,
)

BUILT_FR_ROM = Path(__file__).parent.parent / "output" / "roms" / "GenedRom-fr.gba"
ENGLISH_ROM = Path(__file__).parent.parent / "input" / "roms" / "englishrom.gba"

# Les six gélules de la colonne de statistiques, y compris celles que le patch
# laisse volontairement en l'état.
ENGLISH_LABELS = (
    (54, "ATTACK"),
    (66, "DEFENSE"),
    (78, "SP.ATK"),
    (90, "SP.DEF"),
    (102, "SPEED"),
)


def _sheet(rom_path: Path) -> bytearray:
    result = lz77_decompress(bytearray(rom_path.read_bytes()), BLOCK)
    assert result is not None, f"bloc 0x{BLOCK:08X} indécompressable"
    return bytearray(result[0])


class TestGlyphs(unittest.TestCase):
    def test_every_glyph_has_seven_rows_of_equal_width(self):
        for char, glyph in GLYPHS.items():
            with self.subTest(char=char):
                self.assertEqual(len(glyph), GLYPH_ROWS)
                self.assertEqual(len({len(row) for row in glyph}), 1)

    def test_every_glyph_uses_only_hash_and_dot(self):
        for char, glyph in GLYPHS.items():
            with self.subTest(char=char):
                self.assertTrue(set("".join(glyph)) <= {"#", "."})

    def test_translations_only_use_known_glyphs(self):
        known = set(GLYPHS) | {" "}
        for _, english, french in LABELS:
            with self.subTest(label=english):
                self.assertTrue(set(english) <= known)
                self.assertTrue(set(french) <= known)

    def test_drawn_glyphs_follow_the_sheet_style(self):
        """« U » et « Q », absents de l'anglais, restent cohérents avec « O »."""
        self.assertEqual(GLYPHS["U"][:5], GLYPHS["O"][1:6])
        self.assertEqual(GLYPHS["Q"][:5], GLYPHS["O"][:5])


class TestCapsuleGeometry(unittest.TestCase):
    def test_letters_stay_on_rows_one_to_seven(self):
        for _, _, french in LABELS:
            with self.subTest(label=french):
                rows = {row for _, row in letter_mask(french)}
                self.assertTrue(rows <= set(range(1, PILL_HEIGHT - 1)))

    def test_every_french_label_fits_the_sheet(self):
        for _, _, french in LABELS:
            with self.subTest(label=french):
                self.assertTrue(fits(french), f"« {french} » déborde de la gélule")

    def test_an_overlong_label_is_rejected(self):
        self.assertFalse(fits("ATTAQUE ATTAQUE"))

    def test_capsule_top_and_bottom_hug_the_word(self):
        """Les rangées 0 et 8 suivent le mot : plus court, gélule plus étroite."""
        wide = capsule_mask(letter_mask("ATTAQUE"))
        narrow = capsule_mask(letter_mask("EXP."))
        self.assertLess(len(narrow[0]), len(wide[0]))
        self.assertEqual(len(narrow[4]), len(wide[4]), "le corps reste fixe")

    def test_label_pixels_cover_the_whole_area_with_three_colours(self):
        pixels = label_pixels("VITESSE")
        self.assertEqual(len(pixels), PILL_HEIGHT * (PILL_X1 - PILL_X0 + 1))
        self.assertEqual(set(pixels.values()), {LETTER, PILL, BACKGROUND})

    def test_space_separates_words_more_than_letters(self):
        with_space, width_space = render_word("AA A")
        without_space, width_plain = render_word("AAA")
        self.assertGreater(width_space, width_plain)
        self.assertTrue(with_space and without_space)


@pytest.mark.rom
class TestModelMatchesEnglishSheet(unittest.TestCase):
    """La fonte + le modèle de gélule reproduisent la feuille anglaise au pixel."""

    @classmethod
    def setUpClass(cls):
        if not ENGLISH_ROM.exists():
            pytest.skip("englishrom.gba absent")
        cls.tiles = _sheet(ENGLISH_ROM)

    def test_each_english_capsule_is_reproduced_exactly(self):
        for y0, word in ENGLISH_LABELS:
            with self.subTest(label=word):
                self.assertEqual(read_label(self.tiles, y0), label_pixels(word))


@pytest.mark.rom
class TestPatchOnAnEnglishSheet(unittest.TestCase):
    """Application, idempotence et refus d'une feuille inattendue."""

    @classmethod
    def setUpClass(cls):
        if not ENGLISH_ROM.exists():
            pytest.skip("englishrom.gba absent")
        cls.english = _sheet(ENGLISH_ROM)

    def test_patch_translates_every_label(self):
        tiles = bytearray(self.english)
        patched, _ = patch_sheet(tiles)
        self.assertEqual(patched, len(LABELS))
        for y0, _, french in LABELS:
            self.assertEqual(read_label(tiles, y0), label_pixels(french))

    def test_patch_is_idempotent(self):
        tiles = bytearray(self.english)
        patch_sheet(tiles)
        after_first = bytes(tiles)
        patched, _ = patch_sheet(tiles)
        self.assertEqual(patched, 0)
        self.assertEqual(bytes(tiles), after_first)

    def test_untranslated_labels_are_left_alone(self):
        """DEFENSE et EXP. ne bougent pas, ni le « PV » gris de hp_labels."""
        tiles = bytearray(self.english)
        patch_sheet(tiles)
        for y0 in (66, 114):
            self.assertEqual(read_label(tiles, y0), read_label(self.english, y0))
        # Le « HP » gris vit sur les tuiles 100/101 + 116/117 (x32..47, y48..63).
        for y in range(48, 64):
            for x in range(32, 48):
                self.assertEqual(px_get(tiles, x, y), px_get(self.english, x, y))

    def test_unknown_art_is_skipped_not_corrupted(self):
        tiles = bytearray(self.english)
        y0 = LABELS[0][0]
        before = read_label(tiles, y0)
        # Un seul pixel modifié suffit à invalider la gélule ATTACK.
        from languages.fr.patches.summary_stat_labels import px_set
        px_set(tiles, PILL_X0 + 5, y0 + 4, LETTER)
        patched, messages = patch_sheet(tiles)
        self.assertEqual(patched, len(LABELS) - 1)
        self.assertTrue(any("WARN" in message for message in messages))
        self.assertNotEqual(read_label(tiles, y0), label_pixels("ATTAQUE"))
        self.assertNotEqual(read_label(tiles, y0), before)  # notre pixel triché


@pytest.mark.rom
class TestBuiltFrRom(unittest.TestCase):
    """La ROM FR livrée affiche les libellés français."""

    @classmethod
    def setUpClass(cls):
        if not BUILT_FR_ROM.exists():
            pytest.skip("GenedRom-fr.gba non construite")
        cls.tiles = _sheet(BUILT_FR_ROM)

    def test_stat_labels_are_french(self):
        for y0, english, french in LABELS:
            with self.subTest(label=french):
                self.assertEqual(read_label(self.tiles, y0), label_pixels(french),
                                 f"« {english} » n'est pas devenu « {french} »")

    def test_defense_and_exp_are_untouched(self):
        self.assertEqual(read_label(self.tiles, 66), label_pixels("DEFENSE"))

    def test_recompressed_block_fits_its_slot(self):
        rom = bytearray(BUILT_FR_ROM.read_bytes())
        result = lz77_decompress(rom, BLOCK)
        self.assertIsNotNone(result)
        self.assertLessEqual(result[1], SLOT_LEN)


@pytest.mark.rom
class TestApplyPatchesOnARomCopy(unittest.TestCase):
    """Bout en bout sur une copie de ROM : écriture réelle puis relecture."""

    def test_apply_then_reapply(self):
        if not BUILT_FR_ROM.exists():
            pytest.skip("GenedRom-fr.gba non construite")
        import shutil
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "rom.gba"
            shutil.copy2(BUILT_FR_ROM, copy)
            apply_patches(copy)            # déjà traduite ou traduit maintenant
            first = copy.read_bytes()
            self.assertEqual(apply_patches(copy), 0)
            self.assertEqual(copy.read_bytes(), first)
            tiles = _sheet(copy)
            for y0, _, french in LABELS:
                self.assertEqual(read_label(tiles, y0), label_pixels(french))


if __name__ == "__main__":
    unittest.main()
