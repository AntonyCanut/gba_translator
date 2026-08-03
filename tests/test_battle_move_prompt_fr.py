"""Régression FR du prompt de déplacement d’une capacité (issue #159)."""

from pathlib import Path

import pytest

from scripts.check_translation_integrity import load_last_wins
from src.core.text_codec import TextDecoder


ROOT = Path(__file__).resolve().parent.parent
COMBINED_FR = ROOT / "languages" / "fr" / "combined_fr.txt"
BUILT_FR_ROM = ROOT / "output" / "roms" / "GenedRom-fr.gba"

PROMPT_OFFSET = 0x3FE7A0
CONTROL_PREFIX = bytes.fromhex("fc0505fc040d0e0f")
EXPECTED_SOURCE = (
    "<0xFC><0x05><0x05><0xFC><0x04><0x0D><0x0E><0x0F>Déplacer\\noù ?"
)
EXPECTED_RENDERED = "Déplacer\noù ?"


def test_active_translation_asks_where_to_move_the_move() -> None:
    """Un retour à « Envoyer qui ? » doit être détecté avant le build."""
    translations, _ = load_last_wins(COMBINED_FR)

    assert translations[PROMPT_OFFSET] == EXPECTED_SOURCE


@pytest.mark.rom
@pytest.mark.skipif(not BUILT_FR_ROM.exists(), reason="built FR ROM not present")
def test_built_rom_renders_where_to_move_the_move() -> None:
    """La cellule livrée garde ses contrôles et affiche le prompt demandé."""
    raw = BUILT_FR_ROM.read_bytes()[PROMPT_OFFSET:PROMPT_OFFSET + 64]
    assert raw.startswith(CONTROL_PREFIX)
    payload = raw[len(CONTROL_PREFIX):]
    terminator = payload.index(0xFF)

    assert TextDecoder.decode_pokemon(payload[:terminator]) == EXPECTED_RENDERED
