"""Tests pour patch_move_descriptions_fr et src.core.moves."""

import json
import os
import unittest
from pathlib import Path

import pytest

from src.core import moves
from src.core.text_codec import TextDecoder, TextEncoder
from scripts import patch_move_descriptions_fr

OVERRIDES = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "move_descriptions_fr_overrides.json"
)


def _encode(text):
    return TextEncoder.encode_pokemon(text)


def _decode(rom, offset):
    end = rom.find(b"\xff", offset)
    return TextDecoder.decode_pokemon(rom[offset:end], preserve_unknown=True)


def _deref(rom, offset):
    value = int.from_bytes(rom[offset:offset + 4], "little")
    return value - patch_move_descriptions_fr.ROM_POINTER_BASE


class MoveWrappingTests(unittest.TestCase):
    """Budget de la fenêtre (5 lignes, 122 px)."""

    def test_short_text_fits(self):
        self.assertTrue(moves.fits("Une charge\nbasique."))

    def test_rewrap_respects_max_lines(self):
        text = (
            "Le lanceur attaque l'ennemi avec une pluie de petites pierres "
            "faciles à lancer sur la cible."
        )
        wrapped = moves.rewrap(text)
        self.assertLessEqual(wrapped.count("\n") + 1, moves.MOVE_MAX_LINES)
        # Le re-wrap ne change que les retours à la ligne, pas les mots.
        self.assertEqual(wrapped.replace("\n", " "), text)

    def test_overlong_text_does_not_fit(self):
        text = " ".join(["motlong"] * 60)
        self.assertFalse(moves.fits(text))


class OverridesDataTests(unittest.TestCase):
    """Les raccourcis curés doivent tous tenir dans la fenêtre."""

    def test_every_override_fits(self):
        raw = json.loads(OVERRIDES.read_text(encoding="utf-8"))
        entries = {int(k): v for k, v in raw.items() if k.isdigit()}
        self.assertGreater(len(entries), 50)
        too_long = [k for k, v in entries.items() if not moves.fits(v)]
        self.assertEqual(too_long, [], f"raccourcis trop longs : {too_long}")


class PatchMoveDescriptionsTests(unittest.TestCase):
    """apply() sur une ROM synthétique (table d'attaques réduite)."""

    def setUp(self):
        self._base, self._count = moves.MOVE_DESCRIPTION_TABLE, moves.MOVE_COUNT
        moves.MOVE_DESCRIPTION_TABLE = 0x100
        moves.MOVE_COUNT = 2  # une seule attaque : index 1

    def tearDown(self):
        moves.MOVE_DESCRIPTION_TABLE, moves.MOVE_COUNT = self._base, self._count

    def _ptr(self, offset):
        return (offset + patch_move_descriptions_fr.ROM_POINTER_BASE).to_bytes(4, "little")

    def _cell(self):
        return moves.struct_offset(1)

    def test_rewraps_in_place_without_changing_words(self):
        text = (
            "Le lanceur attaque\nl'ennemi avec une\npluie de petites\n"
            "pierres faciles à lancer."
        )
        src = bytearray(0x4000)
        rom = bytearray(0x4000)
        slot = 0x800
        for data in (src, rom):
            enc = _encode(text)
            data[slot:slot + len(enc)] = enc
            data[self._cell():self._cell() + 4] = self._ptr(slot)

        stats = patch_move_descriptions_fr.apply(rom, bytes(src), {slot: text}, {})
        self.assertEqual(stats["failed"], 0)
        result = _decode(rom, slot)
        self.assertLessEqual(result.count("\n") + 1, moves.MOVE_MAX_LINES)
        self.assertEqual(result.replace("\n", " "), text.replace("\n", " "))
        self.assertEqual(_deref(rom, self._cell()), slot)  # not relocated

    def test_overlong_fused_slot_is_relocated_and_terminated(self):
        # Reproduit le bug Morsure : la description vivante a débordé son
        # créneau et fusionné avec la suivante (pas de terminateur). Le patch
        # doit la relocaliser, re-wrappée et proprement terminée.
        source_text = "L'ennemi est mordu par de tranchantes canines."
        fused = (
            "L'utilisateur mord avec crocs vicieux. Cela peut faire "
            "tressaillir l'ennemi. Il grogne d'un air mignon pour faire "
            "baisser l'Attaque de l'ennemi."
        )
        override = (
            "L'utilisateur mord avec crocs vicieux. "
            "Cela peut faire tressaillir l'ennemi."
        )
        src = bytearray(0x8000)
        rom = bytearray(0x8000)
        slot = 0x400
        src[slot:slot + len(_encode(source_text))] = _encode(source_text)
        src[self._cell():self._cell() + 4] = self._ptr(slot)
        # ROM construite : créneau fusionné, et le même pointeur d'origine.
        rom[slot:slot + len(_encode(fused))] = _encode(fused)
        rom[self._cell():self._cell() + 4] = self._ptr(slot)
        rom[0x2000:0x6000] = b"\xff" * 0x4000  # espace libre pour relocaliser

        stats = patch_move_descriptions_fr.apply(
            rom, bytes(src), {slot: source_text}, {1: override}
        )
        self.assertEqual(stats["failed"], 0)
        self.assertEqual(stats["relocated"], 1)
        self.assertEqual(stats["shortened"], 1)
        new_offset = _deref(rom, self._cell())
        self.assertNotEqual(new_offset, slot)
        result = _decode(rom, new_offset)
        # Fusion disparue + terminateur présent + tient dans la fenêtre.
        self.assertIn("tressaillir", result)
        self.assertNotIn("grogne", result)
        self.assertEqual(rom[new_offset + len(_encode(result)) - 1], 0xFF)
        self.assertLessEqual(result.count("\n") + 1, moves.MOVE_MAX_LINES)


FR_ROM = os.path.join("output", "roms", "GenedRom-fr.gba")
SOURCE_ROM = os.path.join("input", "roms", "englishrom.gba")


def _latest_translation():
    import glob

    # Only dated FR JSON files (names start with a digit). Excludes it_/de_
    # prefixed files so the test never applies Italian/German text to the FR ROM.
    files = sorted(glob.glob(os.path.join("output", "translation", "[0-9]*_translation_ready.json")))
    return files[-1] if files else None


@pytest.mark.rom
@unittest.skipUnless(
    os.path.isfile(FR_ROM) and os.path.isfile(SOURCE_ROM) and _latest_translation(),
    "ROM FR/source ou JSON de traduction absents",
)
class PatchOnRealRomTests(unittest.TestCase):
    """Bout en bout : appliquer le patch à la ROM réelle élimine tout débordement."""

    def test_apply_eliminates_all_overflow(self):
        from src.core import move_description_check as mdc

        rom = bytearray(Path(FR_ROM).read_bytes())
        source = Path(SOURCE_ROM).read_bytes()
        text_map = patch_move_descriptions_fr.load_text_map(Path(_latest_translation()))
        overrides = patch_move_descriptions_fr.load_overrides(OVERRIDES)

        stats = patch_move_descriptions_fr.apply(rom, source, text_map, overrides)
        self.assertEqual(stats["failed"], 0)

        overflow = [r for r in mdc.check_all_moves(rom) if not r.fits]
        self.assertEqual(
            overflow, [],
            ", ".join(f"{r.name} {r.reasons}" for r in overflow[:10]),
        )


if __name__ == "__main__":
    unittest.main()
