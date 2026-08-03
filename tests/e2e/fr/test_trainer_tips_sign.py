"""Régression ROM du panneau Astuces de Dresseurs (#162)."""

from __future__ import annotations

import struct

import pytest

from src.core.text_codec import POKEMON_TERMINATOR, TextDecoder

GBA_ROM_BASE = 0x08000000
SIGN_POINTER_OFFSET = 0x1E9368B
ENGLISH_SOURCE_OFFSET = 0x1F732BD
EXPECTED_DISPLAY_TEXT = (
    "Astuces de Dresseurs ! (L) et (SELECT) permettent de changer de Pokémon "
    "dans la liste ! (L) auto-sélectionne un Pokémon à permuter, et (SELECT) "
    "met le Pokémon actuel en tête d'équipe !"
)


def _decode_pointer_target(rom: bytes) -> tuple[int, str]:
    """Décode la chaîne visée par le pointeur du panneau."""
    (pointer,) = struct.unpack_from("<I", rom, SIGN_POINTER_OFFSET)
    target = pointer - GBA_ROM_BASE
    assert 0 <= target < len(rom), f"pointeur GBA invalide : 0x{pointer:08X}"

    end = rom.find(bytes((POKEMON_TERMINATOR,)), target)
    assert end != -1, f"terminateur absent après 0x{target:X}"
    decoded = TextDecoder.decode_pokemon(
        rom[target : end + 1],
        preserve_unknown=True,
    )
    return target, decoded


def _display_text(decoded: str) -> str:
    """Normalise les contrôles CFRU sans masquer leur ordre à l'écran."""
    normalized = (
        decoded.replace("<0xF8>Á", "(L)")
        .replace("<0xF8>È", "(SELECT)")
        .replace("<0xFA>", " ")
        .replace("<0xFB>", " ")
        .replace("\n", " ")
    )
    return " ".join(normalized.split())


@pytest.mark.rom
def test_trainer_tips_sign_uses_requested_wording_and_wrap(
    en_rom_path,
    fr_rom_path,
):
    """Le deuxième bouton L commence la ligne suivant la première phrase."""
    en_target, _ = _decode_pointer_target(en_rom_path.read_bytes())
    _, french = _decode_pointer_target(fr_rom_path.read_bytes())

    assert en_target == ENGLISH_SOURCE_OFFSET
    assert _display_text(french) == EXPECTED_DISPLAY_TEXT

    _, before_second_l, _ = french.split("<0xF8>Á")
    assert before_second_l.endswith("<0xFA>"), french
