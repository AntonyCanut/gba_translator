"""Regression guard for issue #42 — accents broken on small text (menus,
Pokémon names, Pokédex).

Root cause: ``repair_stable_lz77_blocks.py`` restores any LZ77 block whose
compressed bytes are identical between the English and Spanish ROMs. Font
blocks are always EN==ES (the font isn't localized for Spanish), so every
font block looked "stable" and got reverted to the malformed English é/è —
silently undoing the à/é/è/ç accent fix from ``languages/fr/patches/font.py``
on 7 of the 8 font blocks. ``repair_localized_lz77_blocks.py`` already
excludes font blocks via ``is_font_block`` for the same reason; this locks
in the matching exclusion in the stable-block repair pass.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from languages.fr.patches.font import (
    CP_GRAVE_A,
    apply_patches,
    build_grave_a,
    find_font_blocks,
)
from scripts.repair_stable_lz77_blocks import repair_stable_blocks

EN_ROM = Path('input/roms/englishrom.gba')
ES_ROM = Path('input/roms/spanishrom.gba')


class TestRepairStableFontExclusion(unittest.TestCase):
    @unittest.skipUnless(EN_ROM.exists() and ES_ROM.exists(), 'ROMs missing')
    def test_accent_fix_survives_stable_repair(self) -> None:
        english = EN_ROM.read_bytes()
        spanish = ES_ROM.read_bytes()

        target = bytearray(english)
        patched_fonts, _tables, _relocated = apply_patches(target)
        self.assertGreater(patched_fonts, 0, 'sanity: apply_patches must patch something')

        stable, repaired = repair_stable_blocks(target, english, spanish, 0x100, 0x20000)
        self.assertGreater(stable, 0, 'sanity: some non-font blocks should be stable')
        self.assertEqual(repaired, 0, 'no block should need restoring right after apply_patches')

        font_blocks = find_font_blocks(bytes(target))
        self.assertTrue(font_blocks, 'no font blocks found after repair')

        survivors = [
            b for b in font_blocks
            if b.decompressed[CP_GRAVE_A * 32:(CP_GRAVE_A + 1) * 32] == build_grave_a(b.decompressed)
        ]
        self.assertEqual(
            len(survivors), len(font_blocks),
            f'only {len(survivors)}/{len(font_blocks)} font blocks kept the accent fix '
            'after repair_stable_lz77_blocks — it is reverting font glyphs to English',
        )


if __name__ == '__main__':
    unittest.main()
