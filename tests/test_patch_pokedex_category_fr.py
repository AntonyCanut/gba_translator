import os
import unittest

from scripts.patch_pokedex_category_fr import (
    CATEGORY_SUFFIX_OFFSET,
    PATCHES,
    apply_patches,
)
from src.core.text_codec import TextDecoder

EN_ROM = "input/roms/englishrom.gba"
ES_ROM = "input/roms/spanishrom.gba"
FR_BUILD = "output/roms/GenedRom-fr.gba"


def _rom_with(offset: int, content: bytes, size: int = 0x100) -> bytearray:
    data = bytearray(size)
    data[offset: offset + len(content)] = content
    return data


class TestApplyPatches(unittest.TestCase):
    def test_applies_single_patch(self):
        offset, old, new = PATCHES[0]
        data = _rom_with(offset, old, size=offset + len(old) + 4)
        self.assertEqual(apply_patches(data), 1)
        self.assertEqual(bytes(data[offset: offset + len(new)]), new)

    def test_idempotent_when_already_patched(self):
        offset, _old, new = PATCHES[0]
        data = _rom_with(offset, new, size=offset + len(new) + 4)
        self.assertEqual(apply_patches(data), 0)
        self.assertEqual(bytes(data[offset: offset + len(new)]), new)

    def test_raises_on_unexpected_bytes(self):
        offset, old, _new = PATCHES[0]
        data = _rom_with(offset, b"\x99" * len(old), size=offset + len(old) + 4)
        with self.assertRaises(ValueError):
            apply_patches(data)

    def test_raises_on_length_mismatch(self):
        patches = [(0x10, b"\xfe\x21", b"\x0a")]
        data = _rom_with(0x10, b"\xfe\x21")
        with self.assertRaises(ValueError):
            apply_patches(data, patches)


class TestPatchShape(unittest.TestCase):
    def test_patch_is_length_preserving(self):
        for offset, old, new in PATCHES:
            self.assertEqual(len(old), len(new), f"length mismatch at 0x{offset:X}")

    def test_new_bytes_decode_with_leading_space(self):
        _offset, old, new = PATCHES[0]
        # The terminator (0xFF) closes the string; decode the bytes before it.
        old_text = TextDecoder.decode_pokemon(old[: old.find(b"\xff")], preserve_unknown=True)
        new_text = TextDecoder.decode_pokemon(new[: new.find(b"\xff")], preserve_unknown=True)
        self.assertEqual(old_text, "Pokémon")          # fused (the bug)
        self.assertEqual(new_text, " Pokémon")         # space restored (the fix)
        self.assertTrue(new_text.startswith(" "))


@unittest.skipUnless(os.path.exists(EN_ROM), "English source ROM not available")
class TestMatchesEnglishLayout(unittest.TestCase):
    """The fix must reproduce the exact byte layout of the reference ROMs."""

    def test_new_bytes_equal_english_source(self):
        en = open(EN_ROM, "rb").read()
        _offset, _old, new = PATCHES[0]
        self.assertEqual(
            en[CATEGORY_SUFFIX_OFFSET: CATEGORY_SUFFIX_OFFSET + len(new)],
            new,
            "patch should restore the English ROM's ' Pokémon' layout verbatim",
        )

    @unittest.skipUnless(os.path.exists(ES_ROM), "Spanish source ROM not available")
    def test_spanish_source_also_has_leading_space(self):
        es = open(ES_ROM, "rb").read()
        _offset, _old, new = PATCHES[0]
        self.assertEqual(es[CATEGORY_SUFFIX_OFFSET: CATEGORY_SUFFIX_OFFSET + len(new)], new)


@unittest.skipUnless(os.path.exists(FR_BUILD), "Built French ROM not available")
class TestFrenchBuildPatched(unittest.TestCase):
    def test_built_rom_renders_leading_space(self):
        fr = bytearray(open(FR_BUILD, "rb").read())
        apply_patches(fr)  # idempotent: a freshly built ROM already has it via build-fr
        _offset, _old, new = PATCHES[0]
        self.assertEqual(fr[CATEGORY_SUFFIX_OFFSET: CATEGORY_SUFFIX_OFFSET + len(new)], new)


if __name__ == "__main__":
    unittest.main()
