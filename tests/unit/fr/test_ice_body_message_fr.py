"""Garde de régression du message Corps Gel (issue #188)."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from src.core.text_codec import TextEncoder

ROOT = Path(__file__).resolve().parents[3]
COMBINED = ROOT / "languages/fr/combined_fr.txt"
EN_ROM = ROOT / "input/roms/englishrom.gba"
FR_ROM = ROOT / "output/roms/GenedRom-fr.gba"
PATCH_MANIFEST = ROOT / "patches/RELEASE_MANIFEST.json"

MESSAGE_OFFSET = 0x3FC913
PHANTOM_OFFSET = 0x3FC92C
POINTER_SITE = 0x3FE3D8
GBA_ROM_BASE = 0x08000000
EXPECTED_SOURCE = (
    "{B_ATK_ABILITY} de {B_ATK_NAME_WITH_PREFIX}\\nrestaure ses PV !"
)


def _last_entries() -> dict[int, str]:
    """Charge les traductions en appliquant la règle de la dernière occurrence."""
    entries: dict[int, str] = {}
    line_re = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")
    for raw in COMBINED.read_text(encoding="utf-8").splitlines():
        match = line_re.match(raw)
        if match:
            entries[int(match.group(1), 16)] = match.group(2)
    return entries


def _encoded_message() -> bytes:
    """Encode le modèle avec ses deux variables de combat CFRU."""
    middle = TextEncoder.encode(" de ", "pokemon")[:-1]
    suffix = TextEncoder.encode("restaure ses PV !", "pokemon")
    return b"\xfd\x18" + middle + b"\xfd\x0f\xfe" + suffix


def test_ice_body_source_uses_french_order_without_phantom_tail() -> None:
    """Le talent précède le Pokémon et aucun fragment ne détruit le terminateur."""
    entries = _last_entries()

    assert entries[MESSAGE_OFFSET] == EXPECTED_SOURCE
    assert PHANTOM_OFFSET not in entries


@pytest.mark.rom
def test_ice_body_phantom_offset_has_no_pointer_referrer() -> None:
    """L'offset « little! » est un artefact d'extraction sans consommateur."""
    rom = EN_ROM.read_bytes()
    pointer = (PHANTOM_OFFSET + GBA_ROM_BASE).to_bytes(4, "little")

    assert rom.count(pointer) == 0


@pytest.mark.rom
def test_built_rom_ice_body_pointer_renders_expected_message() -> None:
    """Le pointeur vivant doit viser le modèle FR terminé, sans « petit! »."""
    rom = FR_ROM.read_bytes()
    manifest = json.loads(PATCH_MANIFEST.read_text(encoding="utf-8"))
    french = next(entry for entry in manifest["languages"] if entry["code"] == "fr")
    target = int.from_bytes(rom[POINTER_SITE : POINTER_SITE + 4], "little") - GBA_ROM_BASE
    end = rom.index(0xFF, target) + 1

    assert hashlib.sha256(rom).hexdigest() == french["target"]["sha256"]
    assert rom[target:end] == _encoded_message()
    assert TextEncoder.encode("petit!", "pokemon")[:-1] not in rom[target:end]
