"""Regression guard for the first-floor Pokécenter Teala/Zadia dialogue.

Issue #102 asks for the NPC's French text to use the requested wording in the
Pokémon Center 1F room and to keep those translations in the source-of-truth
`languages/fr/combined_fr.txt` file.

This guard pins the live combined entries so a future bulk rewrite cannot bring
back the older Teala wording or the shortened Wireless System farewell.
"""

from __future__ import annotations

import re
from pathlib import Path

COMBINED_FR = Path(__file__).resolve().parents[3] / "languages/fr/combined_fr.txt"

_LINE_RE = re.compile(r"^(0x[0-9a-fA-F]+): (.*)$")

EXPECTED = {
    0x1BD898: (
        "Bonjour !\\nJe m’appelle Zadia.\\pC’est ta première fois ici.\\n"
        "Je vais te montrer comment marche\\ple Système de Communication Sans\\n"
        "Fil.\\pD’abord, je dois te montrer cet\\nétage de notre Centre Pokémon."
        "\\pPar ici, s’il te plaît."
    ),
    0x1BDB85: (
        "Bonjour, {PLAYER}!\\pJe suis Zadia, ton guide du premier\\nétage."
        "\\pAs-tu besoin d'aide pour la\\nconnexion Sans Fil?"
    ),
    0x1BDEDF: "Profite bien du Système de\\nCommunication Sans Fil.\\n",
}


def _load_last_wins(path: Path) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _LINE_RE.match(line)
        if not match:
            continue
        mapping[int(match.group(1), 16)] = match.group(2)
    return mapping


def test_pokecenter_teala_dialogue_is_persisted():
    data = _load_last_wins(COMBINED_FR)
    for offset, expected in EXPECTED.items():
        assert offset in data, f"0x{offset:06X} missing from combined_fr.txt"
        assert data[offset] == expected, (
            f"0x{offset:06X} regressed: expected {expected!r}, got {data[offset]!r}"
        )

    assert "Teala" not in data[0x1BDB85]
    assert "Zadia" in data[0x1BDB85]
