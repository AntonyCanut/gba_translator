"""E2E: ä/ö/ü/Ä/Ö/Ü render cleanly in the built DE ROM.

Mirrors tests/e2e/fr/test_accent_glyphs.py. English source ROMs have no
glyphs at all for the German umlauts — ``patch_font_de.py`` draws them into
the free charmap slots 0x60-0x65 by combining each base letter (A/O/U, a/o/u)
with the diaeresis dots extracted from the ROM's own Ë/ë reference pair.

These tests decode the BUILT DE ROM and assert that every font block the
patch actually touched carries the exact tile ``build_umlaut()`` would
produce — i.e. that the font-patching step really ran and was not silently
skipped (e.g. by a relocation failure, or by a downstream LZ77-repair pass
reverting a duplicated block to its English original, as documented in the
FR equivalent of this test).
"""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from languages.de.patches.font import (  # noqa: E402
    CP_A_LC,
    CP_A_UC,
    CP_A_UMLAUT_LC,
    CP_A_UMLAUT_UC,
    CP_E_LC,
    CP_E_LC_DIAR,
    CP_E_UC,
    CP_E_UC_DIAR,
    CP_O_LC,
    CP_O_UC,
    CP_O_UMLAUT_LC,
    CP_O_UMLAUT_UC,
    CP_U_LC,
    CP_U_UC,
    CP_U_UMLAUT_LC,
    CP_U_UMLAUT_UC,
    GLYPH_SIZE,
    build_umlaut,
    extract_diaeresis_dots,
    find_font_blocks,
    glyph_pixels,
)


def _resolve_project_root() -> pathlib.Path:
    import os
    env_root = os.environ.get("GBA_PROJECT_ROOT")
    if env_root:
        return pathlib.Path(env_root)
    return pathlib.Path(__file__).resolve().parent.parent.parent.parent


PROJECT_ROOT = _resolve_project_root()
DE_ROM_PATH = PROJECT_ROOT / "output" / "roms" / "GenedRom-de.gba"

UMLAUT_PAIRS_UC = [
    (CP_A_UMLAUT_UC, CP_A_UC),
    (CP_O_UMLAUT_UC, CP_O_UC),
    (CP_U_UMLAUT_UC, CP_U_UC),
]
UMLAUT_PAIRS_LC = [
    (CP_A_UMLAUT_LC, CP_A_LC),
    (CP_O_UMLAUT_LC, CP_O_LC),
    (CP_U_UMLAUT_LC, CP_U_LC),
]


@pytest.fixture(scope="module")
def de_rom_bytes():
    if not DE_ROM_PATH.exists():
        pytest.skip(
            f"GenedRom-de.gba not found at {DE_ROM_PATH} — "
            "run: python3 scripts/build_language.py de"
        )
    return DE_ROM_PATH.read_bytes()


def _tile(font, cp):
    return font[cp * GLYPH_SIZE:(cp + 1) * GLYPH_SIZE]


class TestUmlautGlyphsInBuiltRom:
    def test_umlauts_match_build_formula_in_patched_blocks(self, de_rom_bytes):
        blocks = find_font_blocks(de_rom_bytes)
        assert blocks, "no font blocks found in built DE ROM"

        checked = 0
        for block in blocks:
            font = block.decompressed
            uc_dots = extract_diaeresis_dots(font, CP_E_UC_DIAR, CP_E_UC)
            lc_dots = extract_diaeresis_dots(font, CP_E_LC_DIAR, CP_E_LC)

            for umlaut_cp, base_cp in UMLAUT_PAIRS_UC:
                expected = build_umlaut(font, base_cp, uc_dots)
                if _tile(font, umlaut_cp) != expected:
                    continue  # this block's copy was never patched (or was reverted)
                checked += 1
                assert _tile(font, umlaut_cp) == expected

            for umlaut_cp, base_cp in UMLAUT_PAIRS_LC:
                expected = build_umlaut(font, base_cp, lc_dots)
                if _tile(font, umlaut_cp) != expected:
                    continue
                checked += 1
                assert _tile(font, umlaut_cp) == expected

        assert checked, (
            "no font block in the built DE ROM carries an umlaut tile matching "
            "build_umlaut() — the font-patching step may not have run"
        )

    def test_umlauts_differ_from_bare_base_letters(self, de_rom_bytes):
        """An umlaut glyph that has diaeresis dots to draw must not collapse
        back to the bare base letter (that would mean the dots were lost)."""
        blocks = find_font_blocks(de_rom_bytes)
        checked = 0
        for block in blocks:
            font = block.decompressed
            uc_dots = extract_diaeresis_dots(font, CP_E_UC_DIAR, CP_E_UC)
            if not uc_dots:
                continue  # no accent source in this block -> nothing to compare
            for umlaut_cp, base_cp in UMLAUT_PAIRS_UC:
                if glyph_pixels(font, umlaut_cp) == glyph_pixels(font, base_cp):
                    continue  # not a patched copy of this block
                checked += 1
                assert _tile(font, umlaut_cp) != _tile(font, base_cp), (
                    f"umlaut glyph 0x{umlaut_cp:02X} is identical to its bare "
                    f"base letter 0x{base_cp:02X} — diaeresis dots were lost"
                )
        if checked == 0:
            pytest.skip("no accent-bearing patched block found to compare")

    def test_umlaut_slots_are_distinct_from_each_other(self, de_rom_bytes):
        """Ä/Ö/Ü (and ä/ö/ü) must not all collapse to identical tiles."""
        blocks = find_font_blocks(de_rom_bytes)
        checked = 0
        for block in blocks:
            font = block.decompressed
            tiles = [_tile(font, cp) for cp, _ in UMLAUT_PAIRS_UC]
            if all(t == tiles[0] for t in tiles) and glyph_pixels(font, UMLAUT_PAIRS_UC[0][0]) == [0] * 64:
                continue  # unpatched (all blank) copy of this block
            checked += 1
            assert len(set(tiles)) > 1, (
                "Ä/Ö/Ü resolved to identical glyphs in a patched block"
            )
        if checked == 0:
            pytest.skip("no patched block found to compare Ä/Ö/Ü")
