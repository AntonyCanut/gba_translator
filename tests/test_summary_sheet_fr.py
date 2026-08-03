"""La planche dessinée à la main est la source de vérité du bloc 0x00E9A460 (#145).

L'auteur de l'issue a redessiné les libellés de la page « Infos Pokémon »
(N° / NOM / DO / N°ID / OBJET) et ceux du panneau d'attaque (POUVOIR / PRECIS.)
directement dans la planche extraite. ``make build-fr`` réinjecte désormais
``languages/fr/sprites/summary_stat_labels.png`` **après** ``hp_labels.py`` et
``summary_stat_labels.py``, qui redessinent par programme l'ovale « PV » et les
quatre gélules de stats dans le même bloc.

Ce fichier verrouille ce partage : le dessin doit porter la sortie exacte des
deux patchs, sinon les réinjecter dans cet ordre reviendrait à annuler
silencieusement leur traduction. Modifier un seul des deux côtés fait échouer
les tests plutôt que de partir en jeu.
"""

import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from languages.fr.patches.font import lz77_decompress
from languages.fr.patches.hp_labels import (
    GREY_OLD_TILES,
    _draw_grey_label,
)
from languages.fr.patches.summary_stat_labels import (
    BLOCK,
    LABELS,
    SLOT_LEN,
    label_pixels,
    read_label,
)
from src.graphics.sprite_image import read_indexed_image

ROOT = Path(__file__).parent.parent
REFERENCE_PNG = ROOT / "languages" / "fr" / "sprites" / "summary_stat_labels.png"
BUILT_FR_ROM = ROOT / "output" / "roms" / "GenedRom-fr.gba"
ENGLISH_ROM = ROOT / "input" / "roms" / "englishrom.gba"

SHEET_WIDTH, SHEET_HEIGHT = 128, 256
TILE_COUNT = (SHEET_WIDTH // 8) * (SHEET_HEIGHT // 8)

# Colonne de gauche de la page « Infos » : six créneaux de 12 px empilés depuis
# y=56, chacun tenant une gélule. Le dessin en traduit cinq et laisse « TYPE »
# tel quel — transparent en français, comme « DEFENSE » dans la colonne stats.
INFO_LABEL_SLOTS: tuple[tuple[str, int, bool], ...] = (
    ("No → N°", 56, True),
    ("NAME → NOM", 68, True),
    ("TYPE", 80, False),
    ("OT → DO", 92, True),
    ("IDNo → N°ID", 104, True),
    ("ITEM → OBJET", 116, True),
)
INFO_LABEL_X = range(0, 32)

# Le panneau d'attaque (POWER → POUVOIR, ACCURACY → PRECIS.) occupe la dernière
# colonne de tuiles de la planche.
MOVE_PANEL_X = range(96, 128)
MOVE_PANEL_Y = range(56, 112)


def _tiles(rom_path: Path) -> bytearray:
    result = lz77_decompress(bytearray(rom_path.read_bytes()), BLOCK)
    assert result is not None, f"bloc 0x{BLOCK:08X} indécompressable dans {rom_path}"
    return bytearray(result[0])


def _px(tiles: bytearray, x: int, y: int) -> int:
    tile = (y // 8) * (SHEET_WIDTH // 8) + x // 8
    byte = tiles[tile * 32 + (y % 8) * 4 + (x % 8) // 2]
    return byte & 0xF if x % 2 == 0 else byte >> 4


def _reference_grid() -> list[list[int]]:
    width, height, grid = read_indexed_image(REFERENCE_PNG)
    assert (width, height) == (SHEET_WIDTH, SHEET_HEIGHT)
    return [list(row) for row in grid]


def _reference_tiles() -> bytearray:
    """La planche de référence, dans la disposition linéaire du tileset ROM."""
    grid = _reference_grid()
    tiles = bytearray(TILE_COUNT * 32)
    for tile in range(TILE_COUNT):
        ox, oy = (tile % 16) * 8, (tile // 16) * 8
        for row in range(8):
            for col in range(0, 8, 2):
                low = grid[oy + row][ox + col] & 0xF
                high = grid[oy + row][ox + col + 1] & 0xF
                tiles[tile * 32 + row * 4 + col // 2] = low | (high << 4)
    return tiles


class TestReferenceSheetShape(unittest.TestCase):
    def test_reference_png_exists_with_the_expected_size(self):
        width, height, _ = read_indexed_image(REFERENCE_PNG)
        self.assertEqual((width, height), (SHEET_WIDTH, SHEET_HEIGHT))

    def test_reference_png_stays_within_sixteen_colours(self):
        used = {value for row in _reference_grid() for value in row}
        self.assertTrue(used <= set(range(16)), f"indices hors palette : {used}")


class TestReferenceSheetCarriesThePatchedArt(unittest.TestCase):
    """Le dessin doit contenir la sortie des deux patchs qu'il recouvre."""

    def setUp(self):
        self.tiles = _reference_tiles()

    def test_french_stat_capsules_are_present(self):
        for y0, english, french in LABELS:
            with self.subTest(label=french):
                self.assertEqual(
                    read_label(self.tiles, y0), label_pixels(french),
                    f"le dessin a perdu « {french} » (retour à « {english} » ?)",
                )

    @pytest.mark.rom
    def test_grey_pv_oval_matches_hp_labels(self):
        """Les 4 tuiles du « PV » gris valent exactement ce que dessine hp_labels."""
        if not ENGLISH_ROM.exists():
            self.skipTest("englishrom.gba absent")
        expected = _tiles(ENGLISH_ROM)
        _draw_grey_label(expected)
        for tile in GREY_OLD_TILES:
            with self.subTest(tile=tile):
                self.assertEqual(
                    self.tiles[tile * 32:(tile + 1) * 32],
                    expected[tile * 32:(tile + 1) * 32],
                    f"tuile {tile} : le dessin et hp_labels._draw_grey_label divergent",
                )


@pytest.mark.rom
class TestReferenceSheetTranslatesTheInfoPage(unittest.TestCase):
    """Ce qui est traduit diffère de l'anglais, ce qui ne l'est pas est intact."""

    @classmethod
    def setUpClass(cls):
        if not ENGLISH_ROM.exists():
            pytest.skip("englishrom.gba absent")
        cls.english = _tiles(ENGLISH_ROM)
        cls.reference = _reference_tiles()

    def _differs(self, xs, ys) -> int:
        return sum(1 for y in ys for x in xs
                   if _px(self.reference, x, y) != _px(self.english, x, y))

    def test_translated_info_labels_differ_from_english(self):
        for name, y0, translated in INFO_LABEL_SLOTS:
            with self.subTest(label=name):
                changed = self._differs(INFO_LABEL_X, range(y0, y0 + 12))
                if translated:
                    self.assertGreater(
                        changed, 0,
                        f"« {name} » est resté l'art anglais : planche ré-extraite "
                        "d'une ROM non patchée ?",
                    )
                else:
                    self.assertEqual(
                        changed, 0, f"« {name} » devait rester tel quel",
                    )

    def test_move_panel_labels_differ_from_english(self):
        self.assertGreater(self._differs(MOVE_PANEL_X, MOVE_PANEL_Y), 0,
                           "POWER / ACCURACY sont restés en anglais")


@pytest.mark.rom
class TestBuiltFrRomMatchesTheReferenceSheet(unittest.TestCase):
    """La ROM livrée porte le dessin, pixel pour pixel."""

    @classmethod
    def setUpClass(cls):
        if not BUILT_FR_ROM.exists():
            pytest.skip("GenedRom-fr.gba non construite")
        cls.rom = bytearray(BUILT_FR_ROM.read_bytes())

    def test_sheet_equals_the_reference_png(self):
        result = lz77_decompress(self.rom, BLOCK)
        self.assertIsNotNone(result)
        self.assertEqual(bytes(result[0]), bytes(_reference_tiles()),
                         "la ROM et languages/fr/sprites/summary_stat_labels.png "
                         "ont divergé : relancer make build-fr")

    def test_recompressed_block_still_fits_its_slot(self):
        result = lz77_decompress(self.rom, BLOCK)
        self.assertIsNotNone(result)
        self.assertLessEqual(result[1], SLOT_LEN)


if __name__ == "__main__":
    unittest.main()
