"""Verrous de non-régression pour la barre de vie (GitHub issue #84).

Le correctif d'issue #84 tient à quatre choses, et chacune peut être défaite
par une modification anodine ailleurs dans le dépôt :

1. **L'ordre du build.** ``repair_localized_lz77_blocks`` recopie la planche
   espagnole — corps de 7 rangées, tuile 11 vide, donc aucun cap — par-dessus
   la planche du résumé. Seul le fait que ``hp_labels`` tourne *après* cette
   étape sauve la barre. Déplacer une ligne du Makefile ou une entrée de
   ``lang.yaml`` suffit à ramener le défaut, sans qu'aucun test d'art ne bouge.

2. **La référence anglaise partagée.** Les trois langues restaurent la même
   planche anglaise. Corriger l'art d'une seule langue ferait diverger les
   builds en silence.

3. **Les colonnes protégées.** Le libellé du menu Pokémon (« PV »/« KP »/« PS »)
   est dessiné à côté du cap gauche de la barre : les colonnes 14-15 de la zone
   de libellé ne doivent jamais être écrites, et le tracé du résumé ne doit
   jamais toucher la colonne 7 de la tuile 10.

4. **Le contrôle négatif.** ``scripts/regress_summary_hp_bar.py`` est ce qui
   prouve que les tests e2e peuvent échouer. S'il cessait d'abîmer réellement
   les planches, toute la validation passerait par construction.

Les tests d'art et d'ordre ne lisent aucune ROM (tier rapide) ; ceux marqués
``rom`` comparent les ROMs construites à ``englishrom.gba`` — la référence est
la ROM anglaise, jamais une capture d'un build traduit (un golden issu du build
FR ne prouverait que sa propre reproduction).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from languages.de.patches import hp_labels as de_hp  # noqa: E402
from languages.fr.patches import hp_labels as fr_hp  # noqa: E402
from languages.fr.patches.font import lz77_compress, lz77_decompress  # noqa: E402
from languages.it.patches import hp_labels as it_hp  # noqa: E402
from scripts.regress_summary_hp_bar import (  # noqa: E402
    PARTY_CAP_TILES,
    regress,
)
from tests.test_build_fr_pipeline import (  # noqa: E402
    _expand,
    _extract_target_block,
    _parse_make_vars,
)

MAKEFILE = ROOT / "Makefile"
ENGLISH_ROM = ROOT / "input" / "roms" / "englishrom.gba"

HP_LABELS_SCRIPT = "hp_labels.py"
REPAIR_STABLE_SCRIPT = "repair_stable_lz77_blocks.py"
REPAIR_LOCALIZED_SCRIPT = "repair_localized_lz77_blocks.py"

# Étapes déclaratives des builds génériques (languages/<code>/lang.yaml).
YAML_HP_LABELS_STEP = "hp_labels"
YAML_REPAIR_STEPS = ("repair_lz77", "repair_localized_lz77")

TILE = fr_hp.TILE

# Le tracé du libellé de chaque langue, avec la variante d'entrée la plus
# hostile : la planche espagnole sans caps, celle que le build recopie.
LANGUAGES = {
    "fr": (fr_hp, "GenedRom-fr.gba"),
    "de": (de_hp, "GenedRom-de.gba"),
    "it": (it_hp, "GenedRom-it.gba"),
}

# Tuiles de la planche résumé qui ne portent aucune lettre : corps de la barre
# (0-8) et cap droit (11). Elles doivent rester l'art anglais au bit près.
BAR_ONLY_TILES = list(range(9)) + [11]


def _spanish_sheet(module) -> dict[int, str]:
    """La planche espagnole telle que la recopie ``repair_localized_lz77``."""
    return module.GREEN_OLD_VARIANTS["ES « PS »"]


def _drawn_summary_sheet(module) -> dict[int, str]:
    """Planche résumé produite par la langue à partir de la planche espagnole."""
    return module._expected_new(_spanish_sheet(module), module._draw_green_label)


def _drawn_party_tiles(module) -> dict[int, str]:
    return module._expected_new(module.PARTY_OLD_TILES, module._draw_party_label)


def _sheet_bytes(tiles: dict[int, str]) -> bytes:
    return b"".join(bytes.fromhex(tiles[t]) for t in sorted(tiles))


def _left_cap_column(tile_hex: str) -> list[int]:
    """Colonne 7 d'une tuile 4bpp (nibble haut du 4e octet de chaque rangée)."""
    data = bytes.fromhex(tile_hex)
    return [data[row * 4 + 3] >> 4 for row in range(8)]


class TestBuildOrderKeepsTheBarPatchLast(unittest.TestCase):
    """``hp_labels`` doit tourner après les deux réparations LZ77, partout."""

    @classmethod
    def setUpClass(cls) -> None:
        text = MAKEFILE.read_text(encoding="utf-8")
        variables = _parse_make_vars(text)
        _, recipe = _extract_target_block(text, "build-fr")
        cls.recipe = _expand(recipe, variables)

    def test_build_fr_runs_hp_labels(self) -> None:
        self.assertIn(
            f"languages/fr/patches/{HP_LABELS_SCRIPT}",
            self.recipe,
            "build-fr ne dessine plus les libellés HP — la barre reste espagnole",
        )

    def test_build_fr_runs_hp_labels_after_both_lz77_repairs(self) -> None:
        hp_at = self.recipe.find(f"languages/fr/patches/{HP_LABELS_SCRIPT}")
        stable_at = self.recipe.find(REPAIR_STABLE_SCRIPT)
        localized_at = self.recipe.find(REPAIR_LOCALIZED_SCRIPT)
        self.assertNotEqual(hp_at, -1)
        self.assertNotEqual(stable_at, -1)
        self.assertNotEqual(localized_at, -1)
        self.assertLess(
            stable_at, hp_at,
            "hp_labels doit tourner après repair_stable_lz77_blocks",
        )
        self.assertLess(
            localized_at, hp_at,
            "hp_labels doit tourner après repair_localized_lz77_blocks, "
            "sinon la planche espagnole sans caps revient (issue #84)",
        )

    def test_generic_builds_run_hp_labels_after_both_lz77_repairs(self) -> None:
        for code in ("de", "it"):
            with self.subTest(language=code):
                config = yaml.safe_load(
                    (ROOT / "languages" / code / "lang.yaml").read_text(encoding="utf-8")
                )
                steps = [s for s in config["patches"] if isinstance(s, str)]
                self.assertIn(
                    YAML_HP_LABELS_STEP, steps,
                    f"languages/{code}/lang.yaml ne déclare plus hp_labels",
                )
                hp_at = steps.index(YAML_HP_LABELS_STEP)
                for repair in YAML_REPAIR_STEPS:
                    self.assertIn(repair, steps, f"{code}: étape {repair} absente")
                    self.assertLess(
                        steps.index(repair), hp_at,
                        f"{code}: hp_labels doit rester après {repair}, "
                        "sinon la planche espagnole sans caps revient (issue #84)",
                    )

    def test_every_language_with_a_patch_wires_it_in(self) -> None:
        """Une langue qui embarque le patch doit aussi l'exécuter."""
        for code, (module, _rom) in LANGUAGES.items():
            with self.subTest(language=code):
                self.assertTrue(
                    (ROOT / "languages" / code / "patches" / HP_LABELS_SCRIPT).exists(),
                    f"languages/{code}/patches/{HP_LABELS_SCRIPT} manquant",
                )
                self.assertEqual(module.GREEN_BLOCK, 0x00E9B4B8)
                self.assertEqual(module.PARTY_BLOCK, 0x008001D0)


class TestEnglishBarArtIsSharedByEveryLanguage(unittest.TestCase):
    """Les trois langues restaurent exactement la même barre anglaise."""

    def test_english_reference_sheets_are_identical(self) -> None:
        for code, (module, _rom) in LANGUAGES.items():
            with self.subTest(language=code):
                self.assertEqual(
                    module.GREEN_EN_TILES, fr_hp.GREEN_EN_TILES,
                    f"{code}: la planche anglaise de référence a divergé",
                )

    def test_spanish_variant_is_the_capless_sheet(self) -> None:
        """La planche recopiée par le build est bien celle qui casse la barre."""
        for code, (module, _rom) in LANGUAGES.items():
            with self.subTest(language=code):
                spanish = _spanish_sheet(module)
                self.assertEqual(
                    spanish[11], "00" * TILE,
                    f"{code}: la tuile 11 espagnole devrait être vide (cap droit absent)",
                )
                self.assertNotEqual(
                    spanish[0], module.GREEN_EN_TILES[0],
                    f"{code}: le corps espagnol devrait différer du corps anglais",
                )

    def test_every_language_restores_the_english_body_and_both_caps(self) -> None:
        for code, (module, _rom) in LANGUAGES.items():
            with self.subTest(language=code):
                drawn = _drawn_summary_sheet(module)
                for tile in BAR_ONLY_TILES:
                    self.assertEqual(
                        drawn[tile], fr_hp.GREEN_EN_TILES[tile],
                        f"{code}: tuile {tile} n'est pas l'art anglais de la barre",
                    )
                self.assertEqual(
                    _left_cap_column(drawn[10]),
                    _left_cap_column(fr_hp.GREEN_EN_TILES[10]),
                    f"{code}: le cap gauche (tuile 10, colonne 7) a été repeint",
                )

    def test_every_language_keeps_the_party_bar_cap_columns(self) -> None:
        for code, (module, _rom) in LANGUAGES.items():
            with self.subTest(language=code):
                drawn = _drawn_party_tiles(module)
                for tile in PARTY_CAP_TILES:
                    old = bytes.fromhex(module.PARTY_OLD_TILES[tile])
                    new = bytes.fromhex(drawn[tile])
                    for row in range(8):
                        self.assertEqual(
                            old[row * 4 + 3], new[row * 4 + 3],
                            f"{code}: tuile {tile} rangée {row}, colonnes 14-15 "
                            "(cap gauche du menu Pokémon) modifiées",
                        )

    def test_every_language_sheet_fits_its_lz77_slot(self) -> None:
        for code, (module, _rom) in LANGUAGES.items():
            with self.subTest(language=code):
                size = len(lz77_compress(_sheet_bytes(_drawn_summary_sheet(module))))
                self.assertLessEqual(
                    size, module.GREEN_SLOT_LEN,
                    f"{code}: planche recompressée ({size} o) hors du créneau "
                    f"de {module.GREEN_SLOT_LEN} o — le patch serait ignoré",
                )

    def test_languages_draw_distinct_labels(self) -> None:
        """Chaque langue dessine ses propres lettres, jamais celles d'une autre."""
        drawn = {code: _drawn_summary_sheet(module)
                 for code, (module, _rom) in LANGUAGES.items()}
        codes = sorted(drawn)
        for i, left in enumerate(codes):
            for right in codes[i + 1:]:
                with self.subTest(pair=f"{left}/{right}"):
                    self.assertNotEqual(
                        (drawn[left][9], drawn[left][10]),
                        (drawn[right][9], drawn[right][10]),
                        f"{left} et {right} dessinent le même libellé",
                    )

    def test_labels_differ_from_the_english_one(self) -> None:
        for code, (module, _rom) in LANGUAGES.items():
            with self.subTest(language=code):
                drawn = _drawn_summary_sheet(module)
                self.assertNotEqual(
                    (drawn[9], drawn[10]),
                    (fr_hp.GREEN_EN_TILES[9], fr_hp.GREEN_EN_TILES[10]),
                    f"{code}: le libellé est resté « HP »",
                )

    def test_patch_is_idempotent_on_its_own_output(self) -> None:
        """Repasser le patch sur une planche déjà corrigée ne change rien."""
        for code, (module, _rom) in LANGUAGES.items():
            with self.subTest(language=code):
                once = _drawn_summary_sheet(module)
                twice = module._expected_new(once, module._draw_green_label)
                self.assertEqual(once, twice, f"{code}: second passage non neutre")


class TestRegressionHarnessReallyBreaksTheBar(unittest.TestCase):
    """Le contrôle négatif doit abîmer réellement les deux planches.

    Sans ce test, ``regress_summary_hp_bar.py`` pourrait devenir inopérant et
    les tests e2e passeraient alors par construction — exactement le défaut qui
    avait laissé la barre tronquée survivre à deux passes vertes.
    """

    ROM_SIZE = 0x00F00000  # couvre les deux blocs (0x008001D0 et 0x00E9B4B8)
    PARTY_TILE_COUNT = 64

    def _party_sheet(self) -> bytearray:
        sheet = bytearray(self.PARTY_TILE_COUNT * TILE)
        for tile, hexdata in fr_hp.PARTY_OLD_TILES.items():
            sheet[tile * TILE:(tile + 1) * TILE] = bytes.fromhex(hexdata)
        return sheet

    def _summary_sheet(self) -> bytes:
        return _sheet_bytes(_drawn_summary_sheet(fr_hp))

    def _write_rom(self, path: Path) -> None:
        rom = bytearray(self.ROM_SIZE)
        rom[0xB2] = 0x96  # marqueur GBA attendu par les deux scripts
        summary = lz77_compress(self._summary_sheet())
        party = lz77_compress(bytes(self._party_sheet()))
        rom[fr_hp.GREEN_BLOCK:fr_hp.GREEN_BLOCK + len(summary)] = summary
        rom[fr_hp.PARTY_BLOCK:fr_hp.PARTY_BLOCK + len(party)] = party
        path.write_bytes(rom)

    @staticmethod
    def _tiles_at(rom: bytearray, block: int) -> bytearray:
        result = lz77_decompress(rom, block)
        assert result is not None, f"bloc 0x{block:08X} indécompressable"
        return bytearray(result[0])

    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.rom_path = Path(self._tmp.name) / "sandbox.gba"
        self._write_rom(self.rom_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_regress_strips_the_summary_bar_caps(self) -> None:
        regress(self.rom_path)
        tiles = self._tiles_at(bytearray(self.rom_path.read_bytes()), fr_hp.GREEN_BLOCK)
        cap_right = tiles[11 * TILE:12 * TILE]
        self.assertEqual(
            bytes(cap_right), b"\x00" * TILE,
            "le cap droit devrait avoir disparu — le contrôle négatif n'abîme plus rien",
        )
        body = bytes(tiles[0:TILE]).hex()
        self.assertNotEqual(
            body, fr_hp.GREEN_EN_TILES[0],
            "le corps de barre devrait être revenu à la géométrie espagnole",
        )

    def test_regress_blanks_the_party_bar_cap(self) -> None:
        before = self._tiles_at(bytearray(self.rom_path.read_bytes()), fr_hp.PARTY_BLOCK)
        regress(self.rom_path)
        after = self._tiles_at(bytearray(self.rom_path.read_bytes()), fr_hp.PARTY_BLOCK)
        for tile in PARTY_CAP_TILES:
            changed = any(
                before[tile * TILE + row * 4 + 3] != after[tile * TILE + row * 4 + 3]
                for row in range(8)
            )
            self.assertTrue(
                changed,
                f"tuile {tile}: le cap gauche du menu Pokémon n'a pas été effacé",
            )

    def test_regress_leaves_the_rest_of_the_party_sheet_alone(self) -> None:
        """Le contrôle négatif ne doit toucher que le cap, sinon il prouve trop."""
        before = self._tiles_at(bytearray(self.rom_path.read_bytes()), fr_hp.PARTY_BLOCK)
        regress(self.rom_path)
        after = self._tiles_at(bytearray(self.rom_path.read_bytes()), fr_hp.PARTY_BLOCK)
        self.assertEqual(len(before), len(after))
        for index in range(len(before)):
            tile, within = divmod(index, TILE)
            if tile in PARTY_CAP_TILES and within % 4 == 3:
                continue
            self.assertEqual(
                before[index], after[index],
                f"octet {within} de la tuile {tile} modifié hors du cap",
            )

    def test_patch_heals_a_regressed_summary_sheet(self) -> None:
        """Rejouer ``hp_labels`` sur une ROM abîmée restaure barre et caps."""
        regress(self.rom_path)
        self.assertGreaterEqual(
            fr_hp.apply_patches(self.rom_path), 1,
            "le patch devrait reconnaître la planche espagnole et la réparer",
        )
        tiles = self._tiles_at(bytearray(self.rom_path.read_bytes()), fr_hp.GREEN_BLOCK)
        expected = _drawn_summary_sheet(fr_hp)
        for tile in BAR_ONLY_TILES:
            self.assertEqual(
                bytes(tiles[tile * TILE:(tile + 1) * TILE]).hex(), expected[tile],
                f"tuile {tile} non restaurée après réparation",
            )


class TestE2eHarnessStaysWired(unittest.TestCase):
    """Le scénario e2e doit rester branché, avec son contrôle négatif.

    La validation en jeu ne vaut que si elle tourne encore : renommer la
    commande npm, faire pointer la config ailleurs ou remplacer la sauvegarde
    du rapporteur désarmerait toute la preuve sans casser un seul test d'art.
    """

    NPM_SCRIPT = "test:e2e:hp-bar"
    CONFIG = ROOT / "tests" / "e2e-playwright" / "playwright.hp-bar.config.ts"
    SPEC = ROOT / "tests" / "e2e-playwright" / "specs" / "hp-bar.spec.ts"
    ANCHOR = (ROOT / "tests" / "e2e-playwright" / "snapshots" / "specs"
              / "hp-bar.spec.ts-snapshots" / "summary-stat-labels-anchor.png")
    SAVE = ROOT / "tests" / "fixtures" / "saves" / "party_hp_bar_fr.sav"
    SAVE_SHA256 = "86b7d3daafa4bff101e294bd5b8c736a6004db321398e397ff1c9599127a79ac"
    # STAT_LABELS_REGION dans tests/e2e-playwright/helpers/hp-bar-regions.ts.
    ANCHOR_SIZE = (56, 72)

    def test_npm_script_runs_the_hp_bar_config(self) -> None:
        import json

        scripts = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["scripts"]
        self.assertIn(self.NPM_SCRIPT, scripts, "commande npm du scénario absente")
        self.assertIn("playwright.hp-bar.config.ts", scripts[self.NPM_SCRIPT])

    def test_config_targets_the_spec(self) -> None:
        self.assertTrue(self.CONFIG.exists(), "config Playwright absente")
        self.assertIn("specs/hp-bar.spec.ts", self.CONFIG.read_text(encoding="utf-8"))
        self.assertTrue(self.SPEC.exists(), "scénario e2e absent")

    def test_spec_still_runs_the_negative_control(self) -> None:
        spec = self.SPEC.read_text(encoding="utf-8")
        self.assertIn(
            "regress_summary_hp_bar.py", spec,
            "le scénario ne joue plus le contrôle négatif : les comparaisons "
            "pourraient repasser par construction",
        )
        self.assertIn(
            "englishrom.gba", spec,
            "la référence doit rester la ROM anglaise, pas un golden issu d'un "
            "build traduit",
        )

    def test_recognition_anchor_matches_the_stat_label_region(self) -> None:
        self.assertTrue(self.ANCHOR.exists(), "ancre de reconnaissance absente")
        header = self.ANCHOR.read_bytes()[:24]
        self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n", "ancre non PNG")
        width = int.from_bytes(header[16:20], "big")
        height = int.from_bytes(header[20:24], "big")
        self.assertEqual((width, height), self.ANCHOR_SIZE,
                         "l'ancre ne couvre plus la colonne de libellés de stats")

    def test_reporter_save_fixture_is_unchanged(self) -> None:
        import hashlib

        self.assertTrue(self.SAVE.exists(), "sauvegarde du rapporteur absente")
        digest = hashlib.sha256(self.SAVE.read_bytes()).hexdigest()
        self.assertEqual(digest, self.SAVE_SHA256,
                         "la sauvegarde versionnée a changé : le scénario ne "
                         "part plus de la partie du rapporteur")


@pytest.mark.rom
class TestBuiltRomsShipTheEnglishBar(unittest.TestCase):
    """Chaque ROM livrée doit porter la barre anglaise, caps compris."""

    @classmethod
    def setUpClass(cls) -> None:
        if not ENGLISH_ROM.exists():
            pytest.skip("englishrom.gba absente")
        english = bytearray(ENGLISH_ROM.read_bytes())
        summary = lz77_decompress(english, fr_hp.GREEN_BLOCK)
        party = lz77_decompress(english, fr_hp.PARTY_BLOCK)
        assert summary is not None and party is not None
        cls.en_summary = bytes(summary[0])
        cls.en_party = bytes(party[0])

    def _built_rom(self, name: str) -> bytearray:
        path = ROOT / "output" / "roms" / name
        if not path.exists():
            self.skipTest(f"{name} non construite")
        return bytearray(path.read_bytes())

    def test_summary_bar_body_and_caps_match_the_english_rom(self) -> None:
        for code, (_module, rom_name) in LANGUAGES.items():
            with self.subTest(language=code):
                rom = self._built_rom(rom_name)
                decoded = lz77_decompress(rom, fr_hp.GREEN_BLOCK)
                self.assertIsNotNone(decoded, f"{code}: planche indécompressable")
                tiles = bytes(decoded[0])
                for tile in BAR_ONLY_TILES:
                    self.assertEqual(
                        tiles[tile * TILE:(tile + 1) * TILE],
                        self.en_summary[tile * TILE:(tile + 1) * TILE],
                        f"{code}: tuile {tile} diffère de la barre anglaise",
                    )
                for row in range(8):
                    off = 10 * TILE + row * 4 + 3
                    self.assertEqual(
                        tiles[off] >> 4, self.en_summary[off] >> 4,
                        f"{code}: cap gauche (tuile 10, rangée {row}) perdu",
                    )

    def test_party_bar_cap_columns_match_the_english_rom(self) -> None:
        for code, (_module, rom_name) in LANGUAGES.items():
            with self.subTest(language=code):
                rom = self._built_rom(rom_name)
                decoded = lz77_decompress(rom, fr_hp.PARTY_BLOCK)
                self.assertIsNotNone(decoded, f"{code}: planche indécompressable")
                tiles = bytes(decoded[0])
                for tile in PARTY_CAP_TILES:
                    for row in range(8):
                        off = tile * TILE + row * 4 + 3
                        self.assertEqual(
                            tiles[off], self.en_party[off],
                            f"{code}: tuile {tile} rangée {row}, colonnes 14-15 "
                            "(cap gauche du menu Pokémon) diffèrent de l'anglais",
                        )

    def test_no_built_rom_still_carries_the_capless_spanish_sheet(self) -> None:
        for code, (module, rom_name) in LANGUAGES.items():
            with self.subTest(language=code):
                rom = self._built_rom(rom_name)
                decoded = lz77_decompress(rom, fr_hp.GREEN_BLOCK)
                self.assertIsNotNone(decoded)
                tiles = bytes(decoded[0])
                spanish = _spanish_sheet(module)
                for tile in BAR_ONLY_TILES:
                    self.assertNotEqual(
                        tiles[tile * TILE:(tile + 1) * TILE].hex(), spanish[tile],
                        f"{code}: tuile {tile} est encore l'art espagnol sans caps",
                    )

    def test_built_labels_are_translated(self) -> None:
        """La ROM livrée doit bien porter le libellé de sa langue, pas « HP »."""
        for code, (module, rom_name) in LANGUAGES.items():
            with self.subTest(language=code):
                rom = self._built_rom(rom_name)
                decoded = lz77_decompress(rom, fr_hp.GREEN_BLOCK)
                self.assertIsNotNone(decoded)
                tiles = bytes(decoded[0])
                expected = _drawn_summary_sheet(module)
                for tile in (9, 10):
                    self.assertEqual(
                        tiles[tile * TILE:(tile + 1) * TILE].hex(), expected[tile],
                        f"{code}: le libellé de la barre n'est pas celui attendu",
                    )


if __name__ == "__main__":
    unittest.main()
