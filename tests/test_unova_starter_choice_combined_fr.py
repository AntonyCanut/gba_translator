"""Protège les noms français du choix des starters d'Unys."""

import re
from pathlib import Path

import pytest


COMBINED_FR = (
    Path(__file__).resolve().parent.parent / "languages" / "fr" / "combined_fr.txt"
)
_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")

CHOICE_OPTIONS = (
    (0x1F63D68, "{COLOR}ÉVipélierre", "Snivy"),
    (0x1F63D71, "{COLOR}ÊGruikui", "Tepig"),
    (0x1F63D7A, "{COLOR}ËMoustillon", "Oshawott"),
)
RECEIVED_MESSAGE_OFFSET = 0x7E6816
FRENCH_NAMES = ("Vipélierre", "Gruikui", "Moustillon")
ENGLISH_NAMES = ("Snivy", "Tepig", "Oshawott")


def _load_last_wins() -> dict[int, str]:
    """Charge les traductions actives selon la règle de la dernière entrée."""
    translations: dict[int, str] = {}
    with COMBINED_FR.open("r", encoding="utf-8", newline="") as source:
        for raw_line in source:
            match = _LINE_RE.match(raw_line.rstrip("\r\n"))
            if match:
                translations[int(match.group(1), 16)] = match.group(2)
    return translations


@pytest.fixture(scope="module")
def translations() -> dict[int, str]:
    """Retourne la traduction française active indexée par offset."""
    return _load_last_wins()


@pytest.mark.parametrize(
    ("offset", "expected", "english_name"),
    CHOICE_OPTIONS,
    ids=[english_name for _, _, english_name in CHOICE_OPTIONS],
)
def test_unova_starter_option_is_french(
    translations: dict[int, str],
    offset: int,
    expected: str,
    english_name: str,
) -> None:
    """Chaque option indépendante du multichoice conserve son nom français."""
    assert translations.get(offset) == expected, (
        f"0x{offset:X} ({english_name}) doit valoir {expected!r}"
    )


def test_unova_starter_received_message_is_french(
    translations: dict[int, str],
) -> None:
    """Le message de confirmation ne réintroduit aucun nom anglais."""
    message = translations[RECEIVED_MESSAGE_OFFSET]
    assert all(name in message for name in FRENCH_NAMES)
    assert all(name not in message for name in ENGLISH_NAMES)
