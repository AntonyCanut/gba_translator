"""
Regression guard for the Pokémon Center trade-counter "battle via Link
Cable" message, fixed in GitHub issue #19.

Before the fix, ``0x1BC3C7`` read:

    Tu peux combattre un autre Dresseur\\nvia un câble Game Link GBA.

whose first line is 200px wide against the 192px message-box budget
(``src/core/dialogue_linewrap.py``'s ``DEFAULT_MAX_LINE_WIDTH``), so the
text overran the box and the player could not advance the dialogue. The
fix shortens the wording ("un câble Link" instead of "un câble Game Link
GBA.") and re-balances the break so both lines fit.

The corrected string is shorter than the English original it replaces, so
the build keeps it in place at its static offset (no relocation) — the raw
bytes are asserted directly there.

Run standalone: pytest tests/test_pokemon_center_trade_message_fr.py -v
"""

from pathlib import Path

import pytest

from src.core.dialogue_linewrap import DEFAULT_MAX_LINE_WIDTH, line_widths
from src.core.text_codec import TextDecoder

FR_ROM = Path("output/roms/GenedRom-fr.gba")

OFFSET = 0x1BC3C7
EXPECTED_TEXT = "Tu peux combattre un autre\nDresseur via un câble Link."


@pytest.mark.skipif(not FR_ROM.exists(), reason="FR ROM not built")
def test_pc_trade_link_cable_message_fits_and_matches():
    rom = FR_ROM.read_bytes()
    end = rom.find(b"\xff", OFFSET)
    decoded = TextDecoder.decode(rom[OFFSET:end + 1], "pokemon")

    assert decoded == EXPECTED_TEXT

    widths = line_widths(decoded)
    assert all(w <= DEFAULT_MAX_LINE_WIDTH for w in widths), (
        f"line(s) exceed the {DEFAULT_MAX_LINE_WIDTH}px message box: {widths}"
    )
