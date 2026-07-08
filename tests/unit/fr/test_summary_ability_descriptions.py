"""Regression guard for the FR summary ability descriptions.

Issue #95 ("Info Talent trop longue") targeted the Pokémon summary screen,
where the ability description must stay on a single line. These source-level
assertions keep the three longest affected entries short enough to avoid the
wrap that originally spilled onto a second line.
"""

from pathlib import Path


COMBINED_FR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "languages"
    / "fr"
    / "combined_fr.txt"
)


def _load_entries() -> dict[int, str]:
    entries: dict[int, str] = {}
    for line in COMBINED_FR.read_text(encoding="utf-8").splitlines():
        if not line.startswith("0x"):
            continue
        offset_text, text = line.split(": ", 1)
        entries[int(offset_text, 16)] = text
    return entries


def test_summary_ability_descriptions_fit_one_line():
    entries = _load_entries()
    assert entries[0x24F3D8] == "Repousse les Pokémon sauvages."
    assert entries[0x24F481] == "Esquive + sous tempêtesable."
    assert entries[0x24F534] == "Change de type selon cap."
