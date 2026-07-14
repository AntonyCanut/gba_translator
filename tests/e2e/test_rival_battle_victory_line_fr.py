"""Régression E2E de la réplique de victoire du rival en français."""

from __future__ import annotations

import struct

from src.core.text_codec import POKEMON_TERMINATOR, TextDecoder

GBA_ROM_BASE = 0x08000000
RIVAL_VICTORY_POINTER_OFFSET = 0x1E5A488
ENGLISH_SOURCE_OFFSET = 0x1F478EE
EXPECTED_FRENCH = "Mince... pourquoi je m'en faisais ?\nBien sûr que tu es prêt !"
ENGLISH_RESIDUES = (
    "what was I even worried about",
    "Of course you're ready",
)


def _decode_pointer_target(rom: bytes, pointer_offset: int) -> tuple[int, str]:
    """Décode la chaîne terminée par FF actuellement visée par un pointeur ROM."""
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


def test_rival_battle_victory_line_is_french_at_live_pointer(
    en_rom_path,
    fr_rom_path,
):
    """La réplique chargée en combat doit être française, sans résidu anglais."""
    en_target, english = _decode_pointer_target(
        en_rom_path.read_bytes(),
        RIVAL_VICTORY_POINTER_OFFSET,
    )
    fr_target, french = _decode_pointer_target(
        fr_rom_path.read_bytes(),
        RIVAL_VICTORY_POINTER_OFFSET,
    )

    assert en_target == ENGLISH_SOURCE_OFFSET
    assert all(residue in english for residue in ENGLISH_RESIDUES)
    assert french == EXPECTED_FRENCH, (
        f"0x{RIVAL_VICTORY_POINTER_OFFSET:X} -> 0x{fr_target:X} : {french!r}"
    )
    assert all(residue not in french for residue in ENGLISH_RESIDUES)
