"""
Regression guard for the "Braille Converter" key-item name (FR).

Bug (parent P-127, screenshot): the key item "Braille Converter" was translated
"Convertisseur Braille" (21 chars). Its name lives in a fixed in-place slot sized
to the English "Braille Converter" (17 bytes), so the longer French string either
overflowed into the neighbouring item name — rendering the mangled
"Convertisseur BraillZon" — or was dropped as ``too_long`` and reverted to
English. Fix: use "Lecteur Braille" (15 bytes), matching the Italian
"Lettore Braille" approach; it fits the slot and stays true to the item (a device
used to read Braille).

This is a build-independent source-level guard (no ROM needed): it reads the
source of truth ``combined_fr.txt`` (last-wins) and asserts the encoded French
name fits the English slot, so a future rewrite that re-lengthens it is caught in
the fast unit profile before any rebuild.
"""

import re
from pathlib import Path

from src.core.text_codec import TextEncoder

COMBINED_FR = Path(__file__).resolve().parent.parent / "languages/fr/combined_fr.txt"

BRAILLE_CONVERTER_OFFSET = 0xEB92FC
EN_NAME = "Braille Converter"
EXPECTED_FR = "Lecteur Braille"

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


def test_braille_converter_name_is_expected_french():
    assert _last_wins(BRAILLE_CONVERTER_OFFSET) == EXPECTED_FR


def test_braille_converter_name_fits_english_slot():
    """The in-place item-name slot is sized to the English name; the French
    name must not exceed it, or it overflows into the next item name."""
    enc = TextEncoder()
    en_bytes = enc.encode(EN_NAME, "pokemon")
    fr_bytes = enc.encode(_last_wins(BRAILLE_CONVERTER_OFFSET), "pokemon")
    assert len(fr_bytes) <= len(en_bytes), (
        f"FR name is {len(fr_bytes)} bytes but the slot only holds "
        f"{len(en_bytes)} bytes (English '{EN_NAME}'); it would overflow."
    )
