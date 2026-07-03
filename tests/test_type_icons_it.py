"""Unit tests for patch_type_icons_it — Italian move-type icon graphics.

Italian port of test_type_icons_de. Same 4bpp two-copy sheet (0xB1EC64 summary,
0x961A00 battle); Fairy sits at a per-copy offset (0x100 summary, 0xA8 battle).
Italian only needs one extra glyph (Q, for ACQUA). Tests run against a
synthetic ROM so they need no real ROM fixture.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "patch_type_icons_it",
    Path(__file__).resolve().parent.parent / "scripts" / "patch_type_icons_it.py",
)
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _make_rom() -> bytearray:
    """Synthetic ROM large enough to hold both icon-sheet copies, with each icon's
    pill rows (8-19) filled with a recognisable colour."""
    size = max(mod.BASES) + 0x140 * 32
    rom = bytearray(size)
    for base in mod.BASES:
        for icon in mod.TILEOFF:
            g = [[0] * 32 for _ in range(24)]
            for r in range(8, 20):
                for c in range(32):
                    g[r][c] = 0xB  # pill colour
            mod._write_icon(rom, base, mod._tileoff(base, icon), g)
    return rom


def test_patches_both_copies():
    rom = _make_rom()
    p = Path("/tmp/_typeicons_it_test.gba")
    p.write_bytes(rom)
    n = mod.apply_patches(p)
    assert n == len(mod.IT_NAME) * len(mod.BASES)


def test_italian_names_rendered_in_both_copies():
    rom = _make_rom()
    mod_rom = bytearray(rom)
    for base in mod.BASES:
        for icon, it in mod.IT_NAME.items():
            off = mod._tileoff(base, icon)
            g = mod._read_icon(mod_rom, base, off)
            mod._stamp_name(g, it, g[8][0])
            mod._write_icon(mod_rom, base, off, g)
    for base in mod.BASES:
        for icon in mod.IT_NAME:
            off = mod._tileoff(base, icon)
            g = mod._read_icon(mod_rom, base, off)
            fills = sum(g[r][c] == mod._FILL for r in range(10, 17) for c in range(32))
            assert fills > 0, f"{icon}@0x{base:07X}: no letter pixels stamped"
            assert g != mod._read_icon(rom, base, off)


def test_all_names_fit_32px():
    for icon, it in mod.IT_NAME.items():
        assert mod._name_width(it) <= 32, f"{icon} '{it}' overflows 32px"


def test_all_glyphs_present():
    for it in mod.IT_NAME.values():
        missing = [c for c in it if c not in mod._FONT]
        assert not missing, f"'{it}' uses undefined glyph(s) {missing}"


def test_extra_italian_glyph_defined():
    """Italian type names introduce one letter the shared FR/DE badge font lacks."""
    assert "Q" in mod._FONT, "glyph 'Q' missing — needed by ACQUA"


def test_idempotent():
    p = Path("/tmp/_typeicons_it_idem.gba")
    p.write_bytes(_make_rom())
    mod.apply_patches(p)
    once = p.read_bytes()
    mod.apply_patches(p)
    assert p.read_bytes() == once, "patch is not idempotent"


def test_official_italian_type_names():
    """Spot-check the Italian localisation the badges must display."""
    assert mod.IT_NAME["Water"] == "ACQUA"
    assert mod.IT_NAME["Fight"] == "LOTTA"
    assert mod.IT_NAME["Poison"] == "VELENO"
    assert mod.IT_NAME["Dragon"] == "DRAGO"
    assert mod.IT_NAME["Dark"] == "BUIO"
    # NORMAL is close enough to the English art and must not be redrawn.
    assert "Normal" not in mod.IT_NAME


def test_no_residue_from_previous_text():
    """Re-stamping must wipe ALL prior pixels in the text band (rows 10-17)."""
    pill = 0xB
    for it in mod.IT_NAME.values():
        clean = [[0] * 32 for _ in range(24)]
        dirty = [[0] * 32 for _ in range(24)]
        for r in range(8, 20):
            for c in range(32):
                clean[r][c] = dirty[r][c] = pill
        for r in mod._TEXT_ROWS:
            for c in range(32):
                dirty[r][c] = mod._FILL
        mod._stamp_name(clean, it, pill)
        mod._stamp_name(dirty, it, pill)
        for r in mod._TEXT_ROWS:
            assert dirty[r] == clean[r], f"'{it}': residue survived at row {r}"


def test_font_is_full_height():
    for ch, rows in mod._FONT.items():
        assert len(rows) == 7, f"glyph '{ch}' is {len(rows)} rows, expected 7"


def test_fairy_uses_per_copy_tile_offset():
    assert mod.TILEOFF_OVERRIDE.get(0xB1EC64, {}).get("Fairy") == 0x100
    assert mod._tileoff(0xB1EC64, "Fairy") == 0x100
    assert mod._tileoff(0x961A00, "Fairy") == 0xA8
    assert mod._tileoff(0x961A00, "Fairy") == mod.TILEOFF["Fairy"]
    for icon in mod.TILEOFF:
        if icon == "Fairy":
            continue
        assert mod._tileoff(0xB1EC64, icon) == mod._tileoff(0x961A00, icon) == mod.TILEOFF[icon]


def test_fairy_stamped_at_correct_offset_per_copy():
    p = Path("/tmp/_typeicons_it_fairy.gba")
    p.write_bytes(_make_rom())
    mod.apply_patches(p)
    rom = bytearray(p.read_bytes())
    for base, off in ((0xB1EC64, 0x100), (0x961A00, 0xA8)):
        g = mod._read_icon(rom, base, off)
        fills = sum(g[r][c] == mod._FILL for r in range(10, 17) for c in range(32))
        assert fills > 0, f"Fairy 'FOLLETT' not stamped at 0x{base:07X}+0x{off:X}"
