"""Régression DE : les deux textes d'Ace sont traduits dans la ROM construite."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder


GBA_BASE = 0x08000000
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DE_ROM = PROJECT_ROOT / "output" / "roms" / "GenedRom-de.gba"

# (pointeur vivant, marqueurs DE, résidus EN interdits)
SAMPLES = (
    (
        0x1E5A503,
        ("Lass uns so schnell wie möglich", "Unterwegs heile ich"),
        ("Let's make our way", "quick as possible", "healed up"),
    ),
    (
        0x1E5A52B,
        ("Solange du mit", "kampffähigen Pokémon", "Kraxler"),
        ("While teamed up", "viable", "Rock Climb"),
    ),
)


@pytest.fixture(scope="module")
def de_rom() -> bytes:
    """Charge la ROM DE construite à la demande."""
    if not DE_ROM.exists():
        pytest.skip("GenedRom-de.gba absente — lancer : make build-de")
    return DE_ROM.read_bytes()


def _decode_live_text(rom: bytes, pointer_slot: int) -> tuple[int, str]:
    """Suit un pointeur GBA vivant et décode sa chaîne terminée."""
    pointer = struct.unpack_from("<I", rom, pointer_slot)[0]
    body_offset = pointer - GBA_BASE
    assert 0 <= body_offset < len(rom), (
        f"pointeur @0x{pointer_slot:X} hors ROM : 0x{pointer:08X}"
    )

    end = rom.find(b"\xff", body_offset, min(body_offset + 1200, len(rom)))
    assert end >= 0, f"chaîne non terminée via le pointeur @0x{pointer_slot:X}"
    decoded = TextDecoder.decode_pokemon(
        rom[body_offset : end + 1], preserve_unknown=True
    )
    return body_offset, decoded


@pytest.mark.parametrize(
    "pointer_slot,german_markers,english_markers", SAMPLES
)
def test_ace_text_is_german_through_live_pointer(
    de_rom: bytes,
    pointer_slot: int,
    german_markers: tuple[str, ...],
    english_markers: tuple[str, ...],
) -> None:
    """Chaque pointeur doit viser le texte DE injecté, sans résidu anglais."""
    _, decoded = _decode_live_text(de_rom, pointer_slot)
    lowered = decoded.lower()

    for marker in german_markers:
        assert marker in decoded
    for marker in english_markers:
        assert marker.lower() not in lowered
