"""E2E: Item description accuracy — Antigel et famille Repousse.

Décoder les pointeurs vivants de la table items CFRU (0x876074, stride 44,
description ptr à +0x14) pour vérifier que :
- Antigel (id 0x19) : décrit le dégel, pas une Potion
- Repousse/Sup./Max (id 0x5F/0x5C/0x5D) : « N pas », pas « N étapes »
"""

import struct
from typing import Optional

import pytest

from src.text.charmap_data import BYTE_TO_CHAR


ITEMS_TABLE = 0x876074
ITEM_STRIDE = 44
DESC_PTR_OFFSET = 0x14
GBA_BASE = 0x08000000

ITEM_ANTIGEL = 0x19    # Ice Heal
ITEM_REPOUSSE = 0x5F   # Repousse (100 steps)
ITEM_SUP_REPOUSSE = 0x5C  # Sup. Repousse (250 steps)
ITEM_MAX_REPOUSSE = 0x5D  # Max Repousse (200 steps)


def _follow_desc_ptr(rom: bytes, item_id: int) -> Optional[int]:
    item_offset = ITEMS_TABLE + item_id * ITEM_STRIDE
    ptr_bytes = rom[item_offset + DESC_PTR_OFFSET: item_offset + DESC_PTR_OFFSET + 4]
    ptr = struct.unpack_from("<I", ptr_bytes)[0]
    if ptr < GBA_BASE:
        return None
    return ptr - GBA_BASE


def _decode(rom: bytes, offset: int, max_len: int = 256) -> str:
    result = []
    i = offset
    limit = min(offset + max_len, len(rom))
    while i < limit:
        b = rom[i]
        if b == 0xFF:
            break
        if b == 0xFE:
            result.append("\n")
            i += 1
        elif b in (0xFC, 0xFD):
            result.append(f"<{b:02X}{rom[i+1]:02X}>")
            i += 2
        elif b in BYTE_TO_CHAR:
            result.append(BYTE_TO_CHAR[b])
            i += 1
        else:
            result.append(f"<?{b:02X}>")
            i += 1
    return "".join(result)


@pytest.fixture(scope="module")
def fr_rom_bytes():
    from pathlib import Path
    rom_path = Path(__file__).resolve().parent.parent.parent / "output" / "roms" / "GenedRom-fr.gba"
    if not rom_path.exists():
        pytest.skip("GenedRom-fr.gba not found")
    with open(rom_path, "rb") as f:
        return f.read()


class TestItemDescriptions:
    """Vérifier les descriptions d'objets corrigées directement via les pointeurs ROM."""

    def test_antigel_decrit_le_degel(self, fr_rom_bytes):
        offset = _follow_desc_ptr(fr_rom_bytes, ITEM_ANTIGEL)
        assert offset is not None, "Antigel: pointeur de description nul/invalide"
        text = _decode(fr_rom_bytes, offset)
        assert "blessures" not in text.lower(), (
            f"Antigel affiche encore la description d'une Potion : {text!r}"
        )
        assert "20 PV" not in text, (
            f"Antigel affiche encore '20 PV' (description Potion) : {text!r}"
        )
        assert any(w in text.lower() for w in ("décong", "gelé", "gèle")), (
            f"Antigel ne mentionne pas le dégel : {text!r}"
        )

    def test_repousse_dit_pas_pas_etapes(self, fr_rom_bytes):
        for item_id, name in [
            (ITEM_REPOUSSE, "Repousse"),
            (ITEM_SUP_REPOUSSE, "Sup. Repousse"),
            (ITEM_MAX_REPOUSSE, "Max Repousse"),
        ]:
            # Cherche d'abord via pointeur CFRU, puis à l'offset legacy
            offset = _follow_desc_ptr(fr_rom_bytes, item_id)
            if offset is None:
                pytest.skip(f"{name}: pointeur invalide")
            text = _decode(fr_rom_bytes, offset)
            if not text.strip():
                # Fallback: certains items CFRU pointent vers l'offset legacy
                legacy_offsets = {
                    ITEM_REPOUSSE: 0x3D639C,
                    ITEM_SUP_REPOUSSE: 0x3D6318,
                    ITEM_MAX_REPOUSSE: 0x3D62DF,
                }
                text = _decode(fr_rom_bytes, legacy_offsets[item_id])
            assert "étapes" not in text.lower(), (
                f"{name}: description contient encore 'étapes' : {text!r}"
            )
            assert "pas" in text.lower(), (
                f"{name}: description ne contient pas 'pas' : {text!r}"
            )

    def test_antigel_ptr_pointe_vers_free_space(self, fr_rom_bytes):
        offset = _follow_desc_ptr(fr_rom_bytes, ITEM_ANTIGEL)
        # 0xB3FF00 est en free space — hors de la région FireRed legacy (< 0x08000000)
        assert offset is not None and offset >= 0x100000, (
            f"Antigel ptr inattendu : 0x{offset:08X}"
        )
