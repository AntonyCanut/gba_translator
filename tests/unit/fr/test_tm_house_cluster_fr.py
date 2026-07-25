"""Garde source du cluster anglais voisin des descriptions de CT (#100)."""

from __future__ import annotations

import re
from pathlib import Path

from src.core.dialogue_linewrap import line_width

COMBINED_FR = Path(__file__).resolve().parents[3] / "languages/fr/combined_fr.txt"
LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")
MISSION_TITLE_WIDTH = 176

EXPECTED = {
    0x1F540CF: "Ta visite me touche,\\nmais tu es si peu aimable.",
    0x1F54276: "Toutes les bonnes CT",
    0x1F5428A: "Il y a 120 CT en tout.\\nPeux-tu toutes les trouver ?",
    0x1F543BF: "Ces CT ne vont pas se\\ntrouver toutes seules !",
}


def _last_wins() -> dict[int, str]:
    entries: dict[int, str] = {}
    with COMBINED_FR.open("r", encoding="utf-8", newline="") as handle:
        for raw_line in handle:
            match = LINE_RE.match(raw_line.rstrip("\r\n"))
            if match:
                entries[int(match.group(1), 16)] = match.group(2)
    return entries


def test_tm_house_cluster_is_translated_in_the_live_source():
    entries = _last_wins()

    actual = {offset: entries.get(offset) for offset in EXPECTED}

    assert actual == EXPECTED


def test_tm_mission_title_fits_its_single_line_box():
    title = _last_wins()[0x1F54276]

    width = line_width(title)

    assert "\n" not in title
    assert width <= MISSION_TITLE_WIDTH
