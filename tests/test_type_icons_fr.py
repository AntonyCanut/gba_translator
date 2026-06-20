"""Unit tests for patch_type_icons_fr — French move-type icon graphics.

The type badges on the summary screen / battle move menu are a 4bpp tile
graphic (NOT text), present in two copies (0xB1EC64, 0x961A00). The 18 vanilla
type badges share their tile offset across both copies, but the CFRU-added Fairy
badge sits at a different tile in each (0x100 in the summary copy, 0xA8 in the
battle copy) — see TILEOFF_OVERRIDE. These tests run against a synthetic ROM so
they need no real ROM fixture.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "patch_type_icons_fr",
    Path(__file__).resolve().parent.parent / "scripts" / "patch_type_icons_fr.py",
)
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _make_rom() -> bytearray:
    """Synthetic ROM large enough to hold both icon-sheet copies (4x3 tiles each),
    with each icon's pill rows (8-19) filled with a recognisable colour. Icons in
    the real sheet share tiles (one icon's 3rd tile-row is another's 1st), so we do
    not seed per-icon residue here — see test_no_residue_below_french_name, which
    exercises the clearing logic on an isolated grid."""
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
    p = Path("/tmp/_typeicons_test.gba")
    p.write_bytes(rom)
    n = mod.apply_patches(p)
    assert n == len(mod.FR_NAME) * len(mod.BASES)


def test_french_names_rendered_in_both_copies():
    rom = _make_rom()
    mod_rom = bytearray(rom)
    # apply in-memory by reusing the stamping logic
    for base in mod.BASES:
        for icon, fr in mod.FR_NAME.items():
            off = mod._tileoff(base, icon)
            g = mod._read_icon(mod_rom, base, off)
            mod._stamp_name(g, fr, g[8][0])
            mod._write_icon(mod_rom, base, off, g)
    # after stamping, the text band (rows 10-16) must contain fill pixels (15)
    for base in mod.BASES:
        for icon in mod.FR_NAME:
            off = mod._tileoff(base, icon)
            g = mod._read_icon(mod_rom, base, off)
            fills = sum(g[r][c] == mod._FILL for r in range(10, 17) for c in range(32))
            assert fills > 0, f"{icon}@0x{base:07X}: no letter pixels stamped"
            # and it must differ from the blank-pill original
            assert g != mod._read_icon(rom, base, off)


def test_all_names_fit_32px():
    for icon, fr in mod.FR_NAME.items():
        assert mod._name_width(fr) <= 32, f"{icon} '{fr}' overflows 32px"


def test_all_glyphs_present():
    for fr in mod.FR_NAME.values():
        missing = [c for c in fr if c not in mod._FONT]
        assert not missing, f"'{fr}' uses undefined glyph(s) {missing}"


def test_idempotent():
    p = Path("/tmp/_typeicons_idem.gba")
    p.write_bytes(_make_rom())
    mod.apply_patches(p)
    once = p.read_bytes()
    mod.apply_patches(p)
    assert p.read_bytes() == once, "patch is not idempotent"


def test_steel_is_acier_per_owner_request():
    assert mod.FR_NAME["Steel"] == "ACIER"


def test_no_residue_from_previous_text():
    """Re-stamping must wipe ALL prior pixels in the text band (rows 10-17) before
    drawing — regression guard for the 'old word still showing' bug. We seed the
    whole band with garbage fill, stamp the French name, and require the result to
    be byte-identical to stamping the same name on a clean pill grid: i.e. nothing
    of the previous content survives anywhere in the band."""
    pill = 0xB
    for fr in mod.FR_NAME.values():
        clean = [[0] * 32 for _ in range(24)]
        dirty = [[0] * 32 for _ in range(24)]
        for r in range(8, 20):
            for c in range(32):
                clean[r][c] = dirty[r][c] = pill
        for r in mod._TEXT_ROWS:  # garbage from a previous (longer/English) name
            for c in range(32):
                dirty[r][c] = mod._FILL
        mod._stamp_name(clean, fr, pill)
        mod._stamp_name(dirty, fr, pill)
        for r in mod._TEXT_ROWS:
            assert dirty[r] == clean[r], f"'{fr}': residue survived at row {r}"


def test_font_is_full_height():
    """Every glyph must be the same 7px height as the game's original badge font
    (matches the untouched English/French art height) — guards against a shorter
    font sneaking back in."""
    for ch, rows in mod._FONT.items():
        assert len(rows) == 7, f"glyph '{ch}' is {len(rows)} rows, expected 7"


def test_fairy_uses_per_copy_tile_offset():
    """Fairy is the only CFRU-added badge whose letter tiles sit at a different
    offset in each sheet copy. Regression guard for the bug where the summary
    screen kept reading 'FAIRY': the summary copy (0xB1EC64) must resolve to tile
    0x100, while the battle copy (0x961A00) keeps the 0xA8 default. Every vanilla
    type must resolve to the same offset in both copies."""
    assert mod.TILEOFF_OVERRIDE.get(0xB1EC64, {}).get("Fairy") == 0x100
    assert mod._tileoff(0xB1EC64, "Fairy") == 0x100
    assert mod._tileoff(0x961A00, "Fairy") == 0xA8
    assert mod._tileoff(0x961A00, "Fairy") == mod.TILEOFF["Fairy"]
    for icon in mod.TILEOFF:
        if icon == "Fairy":
            continue
        assert mod._tileoff(0xB1EC64, icon) == mod._tileoff(0x961A00, icon) == mod.TILEOFF[icon]


def test_fairy_stamped_at_correct_offset_per_copy():
    """End-to-end: after patching, the French 'FEE' fill pixels must land on the
    tile the engine actually displays (0x100 for summary, 0xA8 for battle), not on
    the unused garbage slot. Decode-based proof on the synthetic ROM."""
    p = Path("/tmp/_typeicons_fairy.gba")
    p.write_bytes(_make_rom())
    mod.apply_patches(p)
    rom = bytearray(p.read_bytes())
    for base, off in ((0xB1EC64, 0x100), (0x961A00, 0xA8)):
        g = mod._read_icon(rom, base, off)
        fills = sum(g[r][c] == mod._FILL for r in range(10, 17) for c in range(32))
        assert fills > 0, f"Fairy 'FEE' not stamped at 0x{base:07X}+0x{off:X}"
