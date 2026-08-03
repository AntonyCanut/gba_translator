"""Régression ROM de la question affichée après un K.O. en combat (#160)."""

from __future__ import annotations

import struct

from src.core.text_codec import POKEMON_TERMINATOR, TextDecoder

GBA_ROM_BASE = 0x08000000
PROMPT_POINTER_OFFSET = 0x3FE450
ENGLISH_SOURCE_OFFSET = 0x3FB359
EXPECTED_FRENCH = "Envoyer un autre Pokémon ?"
FORBIDDEN_FRENCH = "Utiliser le Pokémon suivant ?"


def _decode_pointer_target(rom: bytes, pointer_offset: int) -> tuple[int, str]:
    pointer = struct.unpack_from("<I", rom, pointer_offset)[0]
    target = pointer - GBA_ROM_BASE
    assert 0 <= target < len(rom), f"pointeur GBA invalide : 0x{pointer:08X}"

    end = rom.find(bytes((POKEMON_TERMINATOR,)), target)
    assert end != -1, f"terminateur absent après 0x{target:X}"
    decoded = TextDecoder.decode_pokemon(
        rom[target : end + 1],
        preserve_unknown=True,
    )
    return target, decoded


def test_next_pokemon_prompt_uses_requested_french_wording(
    en_rom_path,
    fr_rom_path,
):
    """Le pointeur chargé en combat doit viser exactement la formulation demandée."""
    en_target, english = _decode_pointer_target(
        en_rom_path.read_bytes(),
        PROMPT_POINTER_OFFSET,
    )
    fr_target, french = _decode_pointer_target(
        fr_rom_path.read_bytes(),
        PROMPT_POINTER_OFFSET,
    )

    assert en_target == ENGLISH_SOURCE_OFFSET
    assert english == "Use next Pokémon?"
    assert french == EXPECTED_FRENCH, (
        f"0x{PROMPT_POINTER_OFFSET:X} -> 0x{fr_target:X} : {french!r}"
    )
    assert FORBIDDEN_FRENCH not in french
