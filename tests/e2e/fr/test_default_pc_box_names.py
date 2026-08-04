"""Régression : les noms par défaut du PC utilisent « Boîte » (#164)."""

import struct
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder


SOURCE_ROM = Path("input/roms/englishrom.gba")
FR_ROM = Path("output/roms/GenedRom-fr.gba")
GBA_BASE = 0x08000000

# ClearPokemonStorageSystem charge ce littéral, copie le préfixe dans chaque
# nom de boîte, puis lui ajoute son numéro (1 à 25).
DEFAULT_BOX_PREFIX_POINTER = 0x8C850
EN_DEFAULT_BOX_PREFIX_OFFSET = 0x4186CD


def _decode_at(rom: bytes, offset: int, limit: int = 16) -> str:
    """Décode une chaîne CFRU terminée à l'offset indiqué."""
    chunk = rom[offset : offset + limit]
    end = chunk.find(b"\xff")
    assert end != -1, f"Chaîne non terminée à 0x{offset:X}"
    return TextDecoder.decode_pokemon(chunk[: end + 1], preserve_unknown=True)


@pytest.mark.rom
def test_default_pc_box_prefix_is_french() -> None:
    """Le préfixe vivant de Box1…Box25 doit produire Boîte1…Boîte25."""
    source = SOURCE_ROM.read_bytes()
    built = FR_ROM.read_bytes()

    (source_pointer,) = struct.unpack_from("<I", source, DEFAULT_BOX_PREFIX_POINTER)
    assert source_pointer == GBA_BASE + EN_DEFAULT_BOX_PREFIX_OFFSET
    assert _decode_at(source, EN_DEFAULT_BOX_PREFIX_OFFSET) == "Box"

    (built_pointer,) = struct.unpack_from("<I", built, DEFAULT_BOX_PREFIX_POINTER)
    built_offset = built_pointer - GBA_BASE
    assert 0 <= built_offset < len(built)
    assert _decode_at(built, built_offset) == "Boîte"
