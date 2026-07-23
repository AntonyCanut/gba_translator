"""Regression guard for the Pokédex "Liste Pokémon" nav bar (GitHub issue #9).

At 0x415F51, the English source carries 3 button-icon control codes:
`<0xF8><0x0A>Pick <0xF8> OK <0xF8>ÀCancel` (D-pad, A button, B button). Both
the FR and DE translations only had 2 placeholder tokens ({DPAD_UPDOWN},
{B_BUTTON}), missing {SE_SHOP} (the A-button/"OK" icon) entirely — so the
"OK" prompt on the Pokémon List screen rendered without its button icon, the
visual bug reported in the issue. Same offset, same shared base-ROM string
table, same bug in both languages (see multilang-regression pattern).

`_apply_control_placeholders` (src/translators/19_build_translated_rom_generic.py)
resolves `{TOKEN}` placeholders positionally against the English control codes
in appearance order, so the placeholder *count* must match the English source
exactly — an extra or missing token misaligns every icon after it.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path

import pytest

OFFSET = 0x415F51
COMBINED_FR = Path(__file__).resolve().parent.parent / "languages/fr/combined_fr.txt"
COMBINED_DE = Path(__file__).resolve().parent.parent / "languages/de/combined_de.txt"
BUILT_ROM = Path(__file__).resolve().parent.parent / "output/roms/GenedRom-fr.gba"
EXPECTED_FR_NAV = "{DPAD_UPDOWN}Choix {SE_SHOP}OK {B_BUTTON}Annul."
EXPECTED_FR_NAV_BYTES = bytes.fromhex(
    "f80abddce3ddec00f800c9c500f801bbe2e2e9e0adff"
)
FR_NAV_POINTERS = (0x103234, 0x103514, 0x1423A8)
ROM_BASE = 0x08000000


def _last_entry(path: Path, offset: int) -> str:
    """Parse a combined_*.txt file; for duplicate offsets the LAST entry wins."""
    entry = None
    line_re = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")
    target = f"{offset:06X}"
    for raw in path.read_text(encoding="utf-8").splitlines():
        m = line_re.match(raw)
        if m and m.group(1).upper() == target:
            entry = m.group(2)
    assert entry is not None, f"offset {offset:#x} not found in {path}"
    return entry


def _assert_has_all_three_button_icons(text: str) -> None:
    assert "{DPAD_UPDOWN}" in text, f"missing D-pad icon: {text!r}"
    assert "{SE_SHOP}" in text, f"missing A-button/OK icon: {text!r}"
    assert "{B_BUTTON}" in text, f"missing B-button icon: {text!r}"
    i_dpad = text.index("{DPAD_UPDOWN}")
    i_ok = text.index("{SE_SHOP}")
    i_cancel = text.index("{B_BUTTON}")
    assert i_dpad < i_ok < i_cancel, (
        f"button icons must precede Choix/OK/Annul in that order: {text!r}"
    )


def _read_pointed_bytes(rom: bytes, pointer_offset: int) -> bytes:
    target = struct.unpack_from("<I", rom, pointer_offset)[0] - ROM_BASE
    assert 0 <= target < len(rom)
    return rom[target:rom.index(0xFF, target) + 1]


def test_fr_pokemon_list_nav_has_all_three_button_icons():
    _assert_has_all_three_button_icons(_last_entry(COMBINED_FR, OFFSET))


def test_fr_pokemon_list_nav_uses_punctuated_cancel_abbreviation():
    assert _last_entry(COMBINED_FR, OFFSET) == EXPECTED_FR_NAV


def test_de_pokemon_list_nav_has_all_three_button_icons():
    _assert_has_all_three_button_icons(_last_entry(COMBINED_DE, OFFSET))


@pytest.mark.rom
def test_fr_pokemon_list_live_pointers_render_punctuated_cancel():
    rom = BUILT_ROM.read_bytes()

    assert all(
        _read_pointed_bytes(rom, pointer) == EXPECTED_FR_NAV_BYTES
        for pointer in FR_NAV_POINTERS
    )
