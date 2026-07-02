"""Source-level regression test for the "roi de Borrius" intro text.

Both in-game copies of the EN line "the Borrian king gathered the legendary
Pokémon:" refer to *several* legendary Pokémon (the trio summoned to seal the
dark force), so the FR text must use the plural "les Pokémon légendaires",
never the singular "le Pokémon légendaire".

``combined_fr.txt`` has a duplicate entry for 0x1F11684 (case-insensitive,
last-wins): an older uppercase entry already said "légendaires", but a later
lowercase entry reverted it to the singular "convoqua le\\lPokémon
légendaire". This test reads the *live* (last-wins) value directly from the
source file so the regression is caught before any rebuild.
"""

import re
from pathlib import Path

import pytest

COMBINED_FR = Path(__file__).resolve().parent.parent / "languages/fr/combined_fr.txt"

_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")


def _load_last_wins() -> dict[int, str]:
    mapping: dict[int, str] = {}
    with COMBINED_FR.open("r", encoding="utf-8", newline="") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            m = _LINE_RE.match(line)
            if not m:
                continue
            offset = int(m.group(1), 16)
            mapping[offset] = m.group(2)
    return mapping


# Both offsets carry the same EN line ("the Borrian king gathered the
# legendary Pokémon:"); the FR text differs slightly (rassembla / convoqua)
# but both must be plural.
INTRO_LEGENDARY_OFFSETS = [0x8CC9B2, 0x1F11684]


@pytest.fixture(scope="module")
def combined() -> dict[int, str]:
    if not COMBINED_FR.is_file():
        pytest.fail(f"Source of truth not found: {COMBINED_FR}")
    return _load_last_wins()


@pytest.mark.parametrize("offset", INTRO_LEGENDARY_OFFSETS, ids=[hex(o) for o in INTRO_LEGENDARY_OFFSETS])
def test_intro_legendary_pokemon_is_plural(combined, offset):
    text = combined.get(offset)
    assert text is not None, f"Offset {hex(offset)} missing from {COMBINED_FR.name}"
    assert "Pokémon légendaires" in text or "légendaires" in text, (
        f"{hex(offset)}: expected plural 'Pokémon légendaires', got: {text!r}"
    )
    assert "Pokémon légendaire :" not in text, (
        f"{hex(offset)}: reverted to singular 'Pokémon légendaire', got: {text!r}"
    )
