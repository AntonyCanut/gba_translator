"""
Regression guard for two more item names that overflowed the fixed-width
in-place name slots (same class as Braille Converter, see
test_item_name_braille_converter_fr.py — parent P-127 / B-132).

- "Oddish Leaves" (13 bytes budget) was translated "Feuilles de Mystherbe"
  (21 bytes): way over budget, dropped as too_long, shipped in English.
  Fix: "Mystherbe" (9 bytes) — matches the noun already used everywhere
  else in the Dresco/Mystherbe questline dialogue ("des Mystherbe pour
  moi ?", "Tu n'as aucun Mystherbe...", etc.).
- "Trainer Catalogue" (17 bytes budget) was translated "Catalogue des
  Dresseurs" (23 bytes): also over budget. Fix: "Guide Dresseurs"
  (15 bytes), propagated to every mission/dialogue reference and the
  New Game+ carried-items list so the bag and the mission text agree.

This is a build-independent source-level guard (no ROM needed): it reads
the source of truth ``combined_fr.txt`` (last-wins) and asserts the
encoded French name fits the English slot.
"""

import re
from pathlib import Path

from src.core.text_codec import TextEncoder

COMBINED_FR = Path(__file__).resolve().parent.parent / "languages/fr/combined_fr.txt"

ODDISH_LEAVES_OFFSET = 0xEB92C0
ODDISH_LEAVES_EN = "Oddish Leaves"
ODDISH_LEAVES_FR = "Mystherbe"

TRAINER_CATALOGUE_OFFSET = 0xEB930E
TRAINER_CATALOGUE_EN = "Trainer Catalogue"
TRAINER_CATALOGUE_FR = "Guide Dresseurs"

# Mission/dialogue/New-Game+ references that must stay in sync with the
# renamed "Guide Dresseurs" item so the bag and the in-game text agree.
CATALOGUE_REFERENCES = {
    0x1F06B1D: "Guide Dresseurs",
    0x1F0714F: "Guide Dresseurs",
    0x1F07353: "Un Guide Dresseurs",
    0x1F0F004: "Guide Dresseurs",
}

_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")


def _last_wins(offset: int) -> str:
    """Return the last-wins French text for ``offset`` in combined_fr.txt."""
    value = None
    with COMBINED_FR.open("r", encoding="utf-8", newline="") as fh:
        for raw in fh:
            m = _LINE_RE.match(raw.rstrip("\r\n"))
            if m and int(m.group(1), 16) == offset:
                value = m.group(2)
    return value


def _assert_fits(offset: int, en_name: str, expected_fr: str) -> None:
    enc = TextEncoder()
    en_bytes = enc.encode(en_name, "pokemon")
    fr_text = _last_wins(offset)
    assert fr_text == expected_fr
    fr_bytes = enc.encode(fr_text, "pokemon")
    assert len(fr_bytes) <= len(en_bytes), (
        f"0x{offset:X}: FR name is {len(fr_bytes)} bytes but the slot only "
        f"holds {len(en_bytes)} bytes (English {en_name!r}); it would overflow."
    )


def test_oddish_leaves_name_fits_english_slot():
    _assert_fits(ODDISH_LEAVES_OFFSET, ODDISH_LEAVES_EN, ODDISH_LEAVES_FR)


def test_trainer_catalogue_name_fits_english_slot():
    _assert_fits(TRAINER_CATALOGUE_OFFSET, TRAINER_CATALOGUE_EN, TRAINER_CATALOGUE_FR)


def test_catalogue_references_use_renamed_item():
    """Every dialogue/mission mention of the item must use the same FR name
    as the bag entry, or the bag and the mission text would disagree."""
    for offset, expected_substring in CATALOGUE_REFERENCES.items():
        text = _last_wins(offset)
        assert text is not None, f"0x{offset:X}: entry missing from combined_fr.txt"
        assert expected_substring in text, (
            f"0x{offset:X}: expected {expected_substring!r} in {text!r}"
        )
        assert "Catalogue des Dresseurs" not in text and "Catalogue Dresseurs" not in text, (
            f"0x{offset:X}: still references the old item name: {text!r}"
        )
