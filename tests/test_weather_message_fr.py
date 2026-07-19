"""Garde anti-régression du message météo français de l'issue #129."""

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
COMBINED_FR = REPO_ROOT / "languages/fr/combined_fr.txt"
LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")

REAL_OFFSET = 0x3FD850
PHANTOM_OFFSET = 0x3FD851


def _load_last_wins() -> dict[int, str]:
    """Charge les traductions FR selon la règle de la dernière occurrence."""
    mapping: dict[int, str] = {}
    with COMBINED_FR.open("r", encoding="utf-8", newline="") as source:
        for raw_line in source:
            match = LINE_RE.match(raw_line.rstrip("\r\n"))
            if match:
                mapping[int(match.group(1), 16)] = match.group(2)
    return mapping


def test_weather_message_uses_the_real_offset():
    live = _load_last_wins()

    assert live[REAL_OFFSET] == "Il pleut."


def test_no_phantom_offset_one_byte_into_weather_message():
    """L'offset +1 chevauche la chaîne réelle et doublait son « I » initial."""
    live = _load_last_wins()

    assert PHANTOM_OFFSET not in live, (
        "0x3FD851 est un offset fantôme situé un octet après la vraie chaîne "
        "0x3FD850 ; sa réinjection transforme « Il pleut. » en « IIl pleut. »."
    )
