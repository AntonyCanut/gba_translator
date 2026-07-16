"""E2E : le PNJ du Centre Pokémon emploie le toponyme IT court « Cootes »."""

from __future__ import annotations

import os
import struct
from pathlib import Path

import pytest

pytestmark = pytest.mark.rom

from src.core.text_codec import TextDecoder


GBA_BASE = 0x08000000
LIVE_POINTER_OFFSET = 0x1E80AE6
SOURCE_DIALOGUE_OFFSET = 0x1F53F7C
PROJECT_ROOT = Path(
    os.environ.get("GBA_PROJECT_ROOT", Path(__file__).resolve().parents[3])
)
IT_ROM = PROJECT_ROOT / "output" / "roms" / "GenedRom-it.gba"
EXPECTED_DIALOGUE = (
    "Per essere una palude, {FC:0106}Cootes{FC:0108}\n"
    "sorprendentemente non ospita molti{SCROLL}Pokémon di tipo Coleottero."
)


def _decode_live_dialogue(rom: bytes) -> tuple[int, str]:
    """Suit le pointeur vivant et rend visibles les contrôles du dialogue."""
    pointer = struct.unpack_from("<I", rom, LIVE_POINTER_OFFSET)[0]
    body_offset = pointer - GBA_BASE
    assert 0 <= body_offset < len(rom), (
        f"pointeur @{LIVE_POINTER_OFFSET:#x} hors ROM : {pointer:#x}"
    )

    decoded: list[str] = []
    index = body_offset
    while index < len(rom):
        byte = rom[index]
        if byte == 0xFF:
            return body_offset, "".join(decoded)
        if byte == 0xFC:
            assert index + 2 < len(rom), "séquence FC tronquée"
            decoded.append(f"{{FC:{rom[index + 1]:02X}{rom[index + 2]:02X}}}")
            index += 3
            continue
        if byte == 0xFE:
            decoded.append("\n")
            index += 1
            continue
        if byte == 0xFA:
            decoded.append("{SCROLL}")
            index += 1
            continue
        decoded.append(TextDecoder.decode_pokemon(bytes((byte,)), preserve_unknown=True))
        index += 1
    raise AssertionError(f"dialogue non terminé depuis @{LIVE_POINTER_OFFSET:#x}")


@pytest.fixture(scope="module")
def it_rom() -> bytes:
    if not IT_ROM.exists():
        pytest.skip("GenedRom-it.gba absente — lancer : make build-it")
    return IT_ROM.read_bytes()


def test_cootes_bog_npc_dialogue_is_decoded_in_italian(it_rom: bytes) -> None:
    body_offset, dialogue = _decode_live_dialogue(it_rom)

    assert body_offset != SOURCE_DIALOGUE_OFFSET, (
        f"le pointeur @{LIVE_POINTER_OFFSET:#x} cible encore le corps EN d'origine"
    )
    assert dialogue == EXPECTED_DIALOGUE, (
        f"dialogue IT inattendu via @{LIVE_POINTER_OFFSET:#x} -> {body_offset:#x}"
    )
    assert "Cootes Bog" not in dialogue
