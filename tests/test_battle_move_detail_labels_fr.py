"""Gardes de traduction de la fiche d'une capacité en combat (#158)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder

ROOT = Path(__file__).resolve().parent.parent
COMBINED_FR = ROOT / "languages/fr/combined_fr.txt"
FR_ROM = ROOT / "output/roms/GenedRom-fr.gba"
GBA_ROM_BASE = 0x08000000

EXPECTED_LABELS = {
    0xA4CAF9: "Pouvoir :",
    0xA4CB06: "Précis. :",
    0xA4CB0C: "-",
    0xA4CB14: "Physique",
    0xA4CB1C: "Spécial",
}

POINTER_SITES = {
    0x9F9FBC: "Pouvoir :",
    0x9FA358: "Pouvoir :",
    0x9FA42C: "Précis. :",
    0x9FA434: "-",
    0x9FA420: "Physique",
    0x9FA41C: "Spécial",
}


def _last_entries() -> dict[int, str]:
    """Résout les doublons comme le build : la dernière occurrence gagne."""
    entries: dict[int, str] = {}
    line_re = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")
    for raw_line in COMBINED_FR.read_text(encoding="utf-8").splitlines():
        if match := line_re.match(raw_line):
            entries[int(match.group(1), 16)] = match.group(2)
    return entries


def _decode_pointer(rom: bytes, pointer_site: int) -> str:
    pointer = int.from_bytes(rom[pointer_site : pointer_site + 4], "little")
    target = pointer - GBA_ROM_BASE
    assert 0 <= target < len(rom), f"pointeur hors ROM à {pointer_site:#x}: {pointer:#x}"
    end = rom.index(0xFF, target) + 1
    return TextDecoder.decode_pokemon(rom[target:end])


def test_move_detail_labels_match_issue_158_wording():
    entries = _last_entries()

    assert {offset: entries.get(offset) for offset in EXPECTED_LABELS} == EXPECTED_LABELS


@pytest.mark.rom
def test_built_rom_move_detail_pointers_render_issue_158_wording():
    rom = FR_ROM.read_bytes()

    for pointer_site, expected in POINTER_SITES.items():
        assert _decode_pointer(rom, pointer_site) == expected
