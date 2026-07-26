"""Gardes unitaires du patch des descriptions d'objets CT/CS."""

from __future__ import annotations

import struct

from languages.fr.patches import tm_item_descriptions as mod
from src.core.text_codec import TextDecoder, TextEncoder

ROM_SIZE = 0xA50000
FREE_RUN_START = 0x600000
FREE_RUN_SIZE = 0x4000
CT108_INDEX = 0x1B1
CT108_DESCRIPTION_OFFSET = 0xA38FF2
CT112_INDEX = 0x1B5
CT112_DESCRIPTION_OFFSET = 0xA3A77D
CT108_DESCRIPTION = (
    "Aboie menaçant.\n"
    "Baisse aussi\n"
    "l'Att. Spé\n"
    "ennemie."
)


def _put_item(rom: bytearray, index: int, name: str, desc_offset: int) -> None:
    """Écrit une entrée objet minimale avec son pointeur de description."""
    base = mod.ITEM_TABLE_BASE + index * mod.ITEM_STRIDE
    encoded_name = TextEncoder.encode_pokemon(name)
    rom[base:base + len(encoded_name)] = encoded_name
    rom[base + mod.DESC_PTR_OFFSET:base + mod.DESC_PTR_OFFSET + 4] = struct.pack(
        "<I", desc_offset + mod.ROM_POINTER_BASE
    )


def _decode_live_description(rom: bytes, index: int) -> tuple[int, str]:
    """Suit puis décode le pointeur de description vivant d'un objet."""
    base = mod.ITEM_TABLE_BASE + index * mod.ITEM_STRIDE
    pointer = struct.unpack_from("<I", rom, base + mod.DESC_PTR_OFFSET)[0]
    offset = pointer - mod.ROM_POINTER_BASE
    end = rom.index(b"\xff", offset)
    return offset, TextDecoder.decode_pokemon(rom[offset:end])


def test_short_terminated_fragment_is_relocated_to_canonical_text() -> None:
    # Arrange : le fragment de CT108 est court et possède un terminateur,
    # mais il ne correspond pas à sa valeur canonique.
    rom = bytearray(b"\x00" * ROM_SIZE)
    rom[FREE_RUN_START:FREE_RUN_START + FREE_RUN_SIZE] = b"\xff" * FREE_RUN_SIZE
    fragment = TextEncoder.encode_pokemon("nsi sa\nstatistique de vitesse.\n")
    rom[
        CT108_DESCRIPTION_OFFSET:CT108_DESCRIPTION_OFFSET + len(fragment)
    ] = fragment
    _put_item(rom, CT108_INDEX, "CT108", CT108_DESCRIPTION_OFFSET)

    # Act
    stats = mod.apply(rom, {CT108_DESCRIPTION_OFFSET: CT108_DESCRIPTION})

    # Assert
    live_offset, live_text = _decode_live_description(rom, CT108_INDEX)
    assert stats["relocated"] == 1
    assert live_offset != CT108_DESCRIPTION_OFFSET
    assert FREE_RUN_START <= live_offset < FREE_RUN_START + FREE_RUN_SIZE
    assert live_text == CT108_DESCRIPTION


def test_protected_gift_item_is_left_for_its_struct_guard() -> None:
    # CT112 est un objet cadeau dont le pointeur doit rester identique à
    # l'anglais. Sa description partagée n'est jamais rendue par ce chemin.
    rom = bytearray(b"\x00" * ROM_SIZE)
    rom[FREE_RUN_START:FREE_RUN_START + FREE_RUN_SIZE] = b"\xff" * FREE_RUN_SIZE
    fragment = TextEncoder.encode_pokemon("Texte voisin débordé")
    rom[CT112_DESCRIPTION_OFFSET:CT112_DESCRIPTION_OFFSET + len(fragment)] = fragment
    _put_item(rom, CT112_INDEX, "CT112", CT112_DESCRIPTION_OFFSET)

    stats = mod.apply(
        rom,
        {CT112_DESCRIPTION_OFFSET: "Canonique mais non utilisé"},
    )

    base = mod.ITEM_TABLE_BASE + CT112_INDEX * mod.ITEM_STRIDE
    live_pointer = struct.unpack_from("<I", rom, base + mod.DESC_PTR_OFFSET)[0]
    assert stats["machines"] == 1
    assert stats["relocated"] == 0
    assert stats["skipped_protected"] == 1
    assert stats["failed"] == 0
    assert live_pointer == CT112_DESCRIPTION_OFFSET + mod.ROM_POINTER_BASE
    assert rom[FREE_RUN_START:FREE_RUN_START + FREE_RUN_SIZE] == (
        b"\xff" * FREE_RUN_SIZE
    )
