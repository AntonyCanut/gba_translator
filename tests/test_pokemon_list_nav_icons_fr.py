"""Regression guard for the Pokédex "Liste Pokémon" nav bar (GitHub issue #9).

At 0x415F51, the English source carries 3 button-icon control codes:
`<0xF8><0x0A>Pick <0xF8> OK <0xF8>ÀCancel` (D-pad, A button, B button). The FR
translation only had 2 placeholder tokens ({DPAD_UPDOWN}, {B_BUTTON}), missing
{SE_SHOP} (the A-button/"OK" icon) entirely — so the "OK" prompt on the Pokémon
List screen rendered without its button icon, the visual bug reported in the
issue.

`_apply_control_placeholders` (src/translators/19_build_translated_rom_generic.py)
resolves `{TOKEN}` placeholders positionally against the English control codes
in appearance order, so the placeholder *count* must match the English source
exactly — an extra or missing token misaligns every icon after it.
"""

from __future__ import annotations

import re
from pathlib import Path

OFFSET = 0x415F51
COMBINED_FR = Path(__file__).resolve().parent.parent / "languages/fr/combined_fr.txt"


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


def test_fr_pokemon_list_nav_has_all_three_button_icons():
    text = _last_entry(COMBINED_FR, OFFSET)
    assert "{DPAD_UPDOWN}" in text, f"missing D-pad icon before Choix: {text!r}"
    assert "{SE_SHOP}" in text, f"missing A-button/OK icon: {text!r}"
    assert "{B_BUTTON}" in text, f"missing B-button icon: {text!r}"
    i_dpad = text.index("{DPAD_UPDOWN}")
    i_ok = text.index("{SE_SHOP}")
    i_cancel = text.index("{B_BUTTON}")
    assert i_dpad < i_ok < i_cancel, (
        f"button icons must precede Choix/OK/Annul in that order: {text!r}"
    )
