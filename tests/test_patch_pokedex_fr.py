import unittest

from src.core import pokedex
from src.core.text_codec import TextDecoder, TextEncoder
from scripts import patch_pokedex_fr


def _encode(text):
    return TextEncoder.encode_pokemon(text)


def _decode(rom, offset):
    end = rom.find(b"\xff", offset)
    return TextDecoder.decode_pokemon(rom[offset:end], preserve_unknown=True)


def _deref(rom, offset):
    value = int.from_bytes(rom[offset:offset + 4], "little")
    return value - patch_pokedex_fr.ROM_POINTER_BASE


class PatchPokedexTests(unittest.TestCase):
    def setUp(self):
        self._base, self._count = pokedex.DEX_TABLE_BASE, pokedex.DEX_TABLE_COUNT
        pokedex.DEX_TABLE_BASE = 0x100
        pokedex.DEX_TABLE_COUNT = 4

    def tearDown(self):
        pokedex.DEX_TABLE_BASE, pokedex.DEX_TABLE_COUNT = self._base, self._count

    def _ptr(self, offset):
        return (offset + patch_pokedex_fr.ROM_POINTER_BASE).to_bytes(4, "little")

    def test_rewraps_in_place_without_changing_words(self):
        four_line = (
            "Il évite agilement les attaques\nennemies et crache des boules\n"
            "de feu par le groin. Il aime\ngriller des Baies."
        )
        src = bytearray(0x4000)
        rom = bytearray(0x4000)
        slot = 0x800
        for data in (src, rom):
            enc = _encode(four_line)
            data[slot:slot + len(enc)] = enc
            data[0x100:0x104] = self._ptr(slot)

        stats = patch_pokedex_fr.apply(rom, bytes(src), {slot: four_line}, {})
        self.assertEqual(stats["failed"], 0)
        result = _decode(rom, slot)
        self.assertLessEqual(result.count("\n") + 1, pokedex.DEX_MAX_LINES)
        self.assertEqual(result.replace("\n", " "), four_line.replace("\n", " "))
        # not relocated: pointer unchanged
        self.assertEqual(_deref(rom, 0x100), slot)

    def test_relocates_when_override_exceeds_slot(self):
        # Source slot holds a short description; the override is longer and
        # must be relocated into the free-space block, repointing the struct.
        short = "Un Pokémon vif."
        long_override = (
            "Il transforme des jets d'eau sous pression en shuriken "
            "qui tournent vite et coupent le métal."
        )
        src = bytearray(0x8000)
        rom = bytearray(0x8000)
        slot = 0x400
        for data in (src, rom):
            enc = _encode(short)
            data[slot:slot + len(enc)] = enc
            data[0x100:0x104] = self._ptr(slot)
        # a 0xFF free-space run large enough for relocation
        rom[0x2000:0x6000] = b"\xff" * 0x4000

        stats = patch_pokedex_fr.apply(
            rom, bytes(src), {slot: short}, {str(slot): long_override}
        )
        self.assertEqual(stats["failed"], 0)
        self.assertEqual(stats["relocated"], 1)
        self.assertEqual(stats["shortened"], 1)
        new_offset = _deref(rom, 0x100)
        self.assertNotEqual(new_offset, slot)
        result = _decode(rom, new_offset)
        self.assertEqual(result.replace("\n", " "), long_override)
        self.assertLessEqual(result.count("\n") + 1, pokedex.DEX_MAX_LINES)

    def test_collision_slot_falls_back_to_source_and_relocates(self):
        # The JSON maps the offset to a non-description (a shared ability
        # name); the real description lives in the source ROM and must be
        # relocated so the shared string is left untouched.
        description = "Il ne produit qu'une perle durant son existence rare et précieuse."
        ability = "Bouclier"
        src = bytearray(0x8000)
        rom = bytearray(0x8000)
        slot = 0x400
        # source slot: the genuine species description
        denc = _encode(description)
        src[slot:slot + len(denc)] = denc
        src[0x100:0x104] = self._ptr(slot)
        # built rom slot: the shared ability string at the same offset
        aenc = _encode(ability)
        rom[slot:slot + len(aenc)] = aenc
        rom[0x100:0x104] = self._ptr(slot)
        rom[0x2000:0x6000] = b"\xff" * 0x4000

        stats = patch_pokedex_fr.apply(rom, bytes(src), {slot: ability}, {})
        self.assertEqual(stats["failed"], 0)
        self.assertEqual(stats["relocated"], 1)
        # shared ability string preserved in place
        self.assertEqual(_decode(rom, slot), ability)
        # struct now points at the relocated species description
        new_offset = _deref(rom, 0x100)
        self.assertNotEqual(new_offset, slot)
        self.assertEqual(_decode(rom, new_offset).replace("\n", " "), description)


if __name__ == "__main__":
    unittest.main()
