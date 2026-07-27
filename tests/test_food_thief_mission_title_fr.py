"""Garde ROM du titre de mission « Voleur de vivres » (#151).

L'offset historique 0x1FA4E0E inclut un préfixe interne de deux octets, tandis
que les trois pointeurs du moteur visent la chaîne à 0x1FA4E10. Le test suit
ces pointeurs depuis la ROM source afin de contrôler les octets réellement lus
dans la ROM française construite.
"""

import struct
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder

SOURCE_ROM = Path("input/roms/patchedfrenchrom.gba")
FR_ROM = Path("output/roms/GenedRom-fr.gba")
GBA_BASE = 0x08000000
TITLE_OFFSET = 0x1FA4E10
EXPECTED_TITLE = "Voleur de vivres"


def _decode_at(rom: bytes, offset: int, limit: int = 64) -> str:
    raw = rom[offset : offset + limit]
    end = raw.find(b"\xff")
    assert end >= 0, f"chaîne non terminée à 0x{offset:X}"
    return TextDecoder.decode_pokemon(raw[: end + 1], preserve_unknown=True)


def _pointer_sites(rom: bytes, target_offset: int) -> list[int]:
    needle = struct.pack("<I", GBA_BASE + target_offset)
    sites: list[int] = []
    start = 0
    while (site := rom.find(needle, start)) != -1:
        sites.append(site)
        start = site + 1
    return sites


@pytest.mark.rom
def test_food_thief_title_is_french_at_every_live_pointer() -> None:
    source = SOURCE_ROM.read_bytes()
    french = FR_ROM.read_bytes()
    sites = _pointer_sites(source, TITLE_OFFSET)

    assert sites == [0x1EAA360, 0x1EAA591, 0x1EAABA4]
    for site in sites:
        (target,) = struct.unpack_from("<I", french, site)
        assert target - GBA_BASE == TITLE_OFFSET, (
            f"le site 0x{site:X} ne doit pas être repointé"
        )
        assert _decode_at(french, target - GBA_BASE) == EXPECTED_TITLE, (
            f"pointeur 0x{site:X} → 0x{target - GBA_BASE:X}"
        )
