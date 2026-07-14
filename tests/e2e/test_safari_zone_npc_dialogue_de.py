"""E2E guard: the two Safari-Zone NPC dialogues are German in the built ROM."""

from __future__ import annotations

import os
import struct
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder


GBA_BASE = 0x08000000
PROJECT_ROOT = Path(os.environ.get("GBA_PROJECT_ROOT", Path(__file__).resolve().parents[2]))
DE_ROM = PROJECT_ROOT / "output" / "roms" / "GenedRom-de.gba"

# (live pointer offset, original EN body offset, expected decoded dialogue)
DIALOGUES = (
    (
        0x1E80AB6,
        0x1F53C21,
        "Ich habe meinen geliebten Partner\nin der {FC:0106}Safari-Zone{FC:0108} gefangen."
        "{PAGE}Sie liegt gleich {FC:0106}östlich{FC:0108} der Stadt.",
    ),
    (
        0x1E80AC4,
        0x1F53C7D,
        "Wir können unverändert leben,\nweil wir uns immer verändern."
        "{PAGE}Ich meine, auch Pokémon entwickeln sich,\naber ihre Wesen bleiben gleich."
        "{PAGE}Zumindest sollte es so sein...",
    ),
)


@pytest.fixture(scope="module")
def de_rom() -> bytes:
    if not DE_ROM.exists():
        pytest.skip("GenedRom-de.gba not built — run: make build-de")
    return DE_ROM.read_bytes()


def _decode_live_dialogue(rom: bytes, pointer_offset: int) -> tuple[int, str]:
    """Follow a live GBA pointer and render dialogue control bytes visibly."""
    pointer = struct.unpack_from("<I", rom, pointer_offset)[0]
    body_offset = pointer - GBA_BASE
    assert 0 <= body_offset < len(rom), f"pointer @ {pointer_offset:#x} is outside the ROM"

    decoded: list[str] = []
    index = body_offset
    while index < len(rom):
        byte = rom[index]
        if byte == 0xFF:
            return body_offset, "".join(decoded)
        if byte == 0xFC:
            assert index + 2 < len(rom), "truncated FC control sequence"
            decoded.append(f"{{FC:{rom[index + 1]:02X}{rom[index + 2]:02X}}}")
            index += 3
            continue
        if byte == 0xFB:
            decoded.append("{PAGE}")
            index += 1
            continue
        if byte == 0xFA:
            decoded.append("\n")
            index += 1
            continue
        decoded.append(TextDecoder.decode_pokemon(bytes((byte,)), preserve_unknown=True))
        index += 1
    raise AssertionError(f"unterminated dialogue reached from pointer @ {pointer_offset:#x}")


def _normalise_line_breaks(text: str) -> str:
    """The builder may rewrap a dialogue; its wording and page breaks must not drift."""
    return " ".join(part.strip() for part in text.splitlines())


@pytest.mark.parametrize("pointer_offset,old_body_offset,expected", DIALOGUES)
def test_safari_zone_dialogue_is_decoded_german(
    de_rom: bytes, pointer_offset: int, old_body_offset: int, expected: str
) -> None:
    body_offset, actual = _decode_live_dialogue(de_rom, pointer_offset)
    assert body_offset != old_body_offset, (
        f"live pointer @ {pointer_offset:#x} still targets untranslated EN body "
        f"@ {old_body_offset:#x}"
    )
    assert _normalise_line_breaks(actual) == _normalise_line_breaks(expected)
