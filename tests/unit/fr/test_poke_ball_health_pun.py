"""Regression guard for the Poké Ball gift NPC's health pun."""

from __future__ import annotations

import re
from pathlib import Path


COMBINED_FR = Path(__file__).resolve().parents[3] / "languages/fr/combined_fr.txt"
OFFSET = 0x1EE6521
EXPECTED = "Sers-t'en avec soin, de la ball !\\nHé hé, tu l'as ?"


def _load_last_wins(path: Path) -> dict[int, str]:
    entries: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^(0x[0-9a-fA-F]+): (.*)$", line)
        if match:
            entries[int(match.group(1), 16)] = match.group(2)
    return entries


def test_poke_ball_gift_keeps_french_health_pun() -> None:
    entries = _load_last_wins(COMBINED_FR)

    assert entries[OFFSET] == EXPECTED
    assert "bonne santé" not in entries[OFFSET]
