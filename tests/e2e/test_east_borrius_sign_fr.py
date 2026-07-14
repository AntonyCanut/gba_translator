"""Régression E2E du panneau d'entrée de Borrius Est.

Le panneau est une chaîne de dialogue standard atteinte par un pointeur de
script. Le test suit le slot vivant de la ROM anglaise dans la ROM française,
afin de rester valable lorsque l'injection déplace le texte traduit.
"""

from __future__ import annotations

import struct

from src.core.text_codec import TextDecoder


SOURCE_TEXT_OFFSET = 0x1F52A9C
POINTER_BASE = 0x08000000
POINTER_END = 0x0A000000
POKEMON_TERMINATOR = 0xFF
EXPECTED_FRENCH_TEXT = (
    "Bienvenue à Borrius Est !<0xFB>"
    "Polderive est bien différente\n"
    "de Borrius Ouest, tu ne trouves<0xFA>"
    "pas ?<0xFB>"
    "Je doute que les gens de<0xFA>"
    "Borrius Ouest veuillent vivre<0xFA>"
    "dans un marais."
)


def _pointer_slots(rom: bytes, target: int) -> list[int]:
    """Retourne tous les slots pointant vers l'offset ROM demandé."""
    needle = struct.pack("<I", POINTER_BASE + target)
    slots: list[int] = []
    cursor = 0
    while True:
        slot = rom.find(needle, cursor)
        if slot < 0:
            return slots
        slots.append(slot)
        cursor = slot + 1


def _decode_pointer_target(rom: bytes, slot: int, limit: int = 500) -> str:
    """Décode la chaîne terminée ciblée par un slot de pointeur GBA."""
    pointer = struct.unpack_from("<I", rom, slot)[0]
    assert POINTER_BASE <= pointer < POINTER_END, (
        f"pointeur GBA invalide 0x{pointer:08X} au slot 0x{slot:X}"
    )
    offset = pointer - POINTER_BASE
    raw = rom[offset : min(offset + limit, len(rom))]
    terminator = raw.find(bytes([POKEMON_TERMINATOR]))
    assert terminator >= 0, f"chaîne non terminée ciblée depuis 0x{slot:X}"
    return TextDecoder.decode_pokemon(raw[: terminator + 1], preserve_unknown=True)


def test_east_borrius_sign_decodes_in_french(en_rom_path, fr_rom_path):
    """Le pointeur vivant du panneau doit résoudre le texte français canonique."""
    en_rom = en_rom_path.read_bytes()
    fr_rom = fr_rom_path.read_bytes()

    slots = _pointer_slots(en_rom, SOURCE_TEXT_OFFSET)
    assert slots, f"aucun pointeur vivant trouvé pour 0x{SOURCE_TEXT_OFFSET:X}"

    decoded = [_decode_pointer_target(fr_rom, slot) for slot in slots]
    assert decoded == [EXPECTED_FRENCH_TEXT]
    assert all("Welcome to East Borrius!" not in text for text in decoded)
