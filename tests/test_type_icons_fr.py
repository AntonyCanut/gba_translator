"""Unit tests for patch_type_icons_fr — French move-type icon graphics.

The type badges on the summary screen / battle move menu are a 4bpp tile
graphic (NOT text), present in two byte-identical copies (0xB1EC64, 0x961A00).
These tests run against a synthetic ROM so they need no real ROM fixture.
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
    size = max(mod.BASES) + 0xE0 * 32
    rom = bytearray(size)
    for base in mod.BASES:
        for icon, tileoff in mod.TILEOFF.items():
            g = [[0] * 32 for _ in range(24)]
            for r in range(8, 20):
                for c in range(32):
                    g[r][c] = 0xB  # pill colour
            mod._write_icon(rom, base, tileoff, g)
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
            g = mod._read_icon(mod_rom, base, mod.TILEOFF[icon])
            mod._stamp_name(g, fr, g[8][0])
            mod._write_icon(mod_rom, base, mod.TILEOFF[icon], g)
    # after stamping, the text band (rows 10-15) must contain fill pixels (15)
    for base in mod.BASES:
        for icon in mod.FR_NAME:
            g = mod._read_icon(mod_rom, base, mod.TILEOFF[icon])
            fills = sum(g[r][c] == mod._FILL for r in range(10, 16) for c in range(32))
            assert fills > 0, f"{icon}@0x{base:07X}: no letter pixels stamped"
            # and it must differ from the blank-pill original
            assert g != mod._read_icon(rom, base, mod.TILEOFF[icon])


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


def test_no_residue_below_french_name():
    """The full 8px-tall English-name band (rows 10-17) must be cleared, leaving
    no leftover pixels below the (shorter) French name — regression guard for the
    'word still showing underneath' bug. Exercised on an isolated grid seeded with
    fake English letters in rows 16-17 (the bottom of an 8px name)."""
    pill = 0xB
    for fr in mod.FR_NAME.values():
        g = [[0] * 32 for _ in range(24)]
        for r in range(8, 20):
            for c in range(32):
                g[r][c] = pill
        for r in (16, 17):  # bottom two rows of a fake English name
            for c in range(6, 26):
                g[r][c] = mod._FILL
        mod._stamp_name(g, fr, pill)
        for r in (16, 17):
            stray = [c for c in range(32) if g[r][c] != pill]
            assert not stray, f"'{fr}': residue at row {r}: {stray}"
