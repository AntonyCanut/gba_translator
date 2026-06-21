"""
Build-independent guard for the Unova-starter choice in ``combined_fr.txt``.

Context (ticket "Choix Pokémon")
--------------------------------
A Borrius NPC lets the player pick one of three Unova starters. The choice menu
is three consecutive option strings, each prefixed by a per-option ``{COLOR}``
code, immediately followed by a "You received a ..." confirmation message:

    0x1F63D68  {COLOR}É Snivy     -> Vipélierre
    0x1F63D71  {COLOR}Ê Tepig     -> Gruikui
    0x1F63D7A  {COLOR}Ë Oshawott  -> Moustillon   (was the only one translated)
    0x7E6816   "You received a Snivy, Tepig, and Oshawott from the woman!"

Only Oshawott->Moustillon had ever been added to ``combined_fr.txt``, so the menu
rendered "Snivy / Tepig / Moustillon" in-game. These tests assert the source of
truth keeps the French names for all three options (last-wins value) and that no
English species name leaks back into the confirmation message.

Why a source-level test: ``combined_fr.txt`` has ~957 duplicated offsets where
the last entry wins, and bulk fix scripts can silently drop an inline entry. This
catches a revert before a rebuild, in the fast unit profile, with no ROM needed.

Run standalone:  pytest tests/test_unova_starter_choice_combined_fr.py -v
"""

import re
from pathlib import Path

import pytest

COMBINED_FR = Path(__file__).resolve().parent.parent / "combined_fr.txt"

_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")


def _load_last_wins() -> dict[int, str]:
    """Parse combined_fr.txt into {offset:int -> French text}, last entry wins."""
    mapping: dict[int, str] = {}
    with COMBINED_FR.open("r", encoding="utf-8", newline="") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            m = _LINE_RE.match(line)
            if not m:
                continue
            mapping[int(m.group(1), 16)] = m.group(2)
    return mapping


# (offset, expected_fr, english_name)
CHOICE_OPTIONS = [
    (0x1F63D68, "{COLOR}ÉVipélierre", "Snivy"),
    (0x1F63D71, "{COLOR}ÊGruikui", "Tepig"),
    (0x1F63D7A, "{COLOR}ËMoustillon", "Oshawott"),
]

# Confirmation message must carry the three French names, never the English ones.
RECEIVED_MSG_OFFSET = 0x7E6816
FR_NAMES = ("Vipélierre", "Gruikui", "Moustillon")
EN_NAMES = ("Snivy", "Tepig", "Oshawott")


@pytest.fixture(scope="module")
def combined() -> dict[int, str]:
    if not COMBINED_FR.is_file():
        pytest.fail(f"Source of truth not found: {COMBINED_FR}")
    return _load_last_wins()


class TestUnovaStarterChoiceCombinedFR:
    """The Borrius Unova-starter choice must be fully French in combined_fr.txt."""

    @pytest.mark.parametrize(
        "offset, expected_fr, en_name",
        CHOICE_OPTIONS,
        ids=[en for (_o, _fr, en) in CHOICE_OPTIONS],
    )
    def test_choice_option_is_french(self, combined, offset, expected_fr, en_name):
        assert offset in combined, (
            f"Choice option 0x{offset:06X} [{en_name}] is missing from "
            "combined_fr.txt — the menu entry was dropped and renders in English."
        )
        actual = combined[offset].strip()
        assert actual == expected_fr, (
            f"Choice option 0x{offset:06X} [{en_name}]: expected {expected_fr!r}, "
            f"got {actual!r} (a fix script likely overwrote the live entry)."
        )

    def test_received_message_is_french(self, combined):
        assert RECEIVED_MSG_OFFSET in combined, (
            f"Received-message 0x{RECEIVED_MSG_OFFSET:06X} is missing from "
            "combined_fr.txt — the confirmation stays in English."
        )
        text = combined[RECEIVED_MSG_OFFSET]
        for fr in FR_NAMES:
            assert fr in text, (
                f"Received message lost the French name {fr!r}: {text!r}"
            )
        for en in EN_NAMES:
            assert en not in text, (
                f"Received message still contains the English name {en!r}: {text!r}"
            )
