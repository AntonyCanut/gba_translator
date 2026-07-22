"""E2E : le menu de sélection du PC reste intégralement en français (#18)."""

import struct
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder


SOURCE_ROM = Path("input/roms/patchedfrenchrom.gba")
FR_ROM = Path("output/roms/GenedRom-fr.gba")
GBA_BASE = 0x08000000


def _decode_at(rom: bytes, offset: int, limit: int = 60) -> str:
    """Décode une chaîne CFRU terminée à l'offset indiqué."""
    chunk = rom[offset : offset + limit]
    end = chunk.find(b"\xff")
    raw = chunk if end == -1 else chunk[: end + 1]
    return TextDecoder.decode_pokemon(raw, preserve_unknown=True)


def _resolve_live_pointer(source_rom: bytes, built_rom: bytes, original_offset: int) -> int:
    """Suit dans la ROM construite le pointeur du texte source."""
    needle = struct.pack("<I", original_offset + GBA_BASE)
    slot = source_rom.find(needle)
    assert slot != -1, f"Aucun pointeur source vers 0x{original_offset:X}"
    (target,) = struct.unpack_from("<I", built_rom, slot)
    return target - GBA_BASE


@pytest.fixture(scope="module")
def source_rom_data() -> bytes:
    """Charge la ROM source qui conserve les offsets de pointeurs d'origine."""
    assert SOURCE_ROM.exists(), f"ROM source absente : {SOURCE_ROM}"
    return SOURCE_ROM.read_bytes()


@pytest.fixture(scope="module")
def fr_rom_data() -> bytes:
    """Charge la ROM française versionnée."""
    assert FR_ROM.exists(), f"ROM FR absente : {FR_ROM}"
    return FR_ROM.read_bytes()


@pytest.mark.rom
class TestPcSelectionMenuFrench:
    """Vérifie les trois textes signalés dans l'issue #18."""

    def test_which_pc_question_is_french(self, fr_rom_data: bytes) -> None:
        assert _decode_at(fr_rom_data, 0x1A508A) == "Accéder à quel PC ?"

    def test_player_pc_entry_is_translated(
        self, source_rom_data: bytes, fr_rom_data: bytes
    ) -> None:
        target = _resolve_live_pointer(source_rom_data, fr_rom_data, 0x417BB6)
        assert _decode_at(fr_rom_data, target) == "PC de <0xFD>À"

    def test_prof_log_pc_entry_has_du(
        self, source_rom_data: bytes, fr_rom_data: bytes
    ) -> None:
        target = _resolve_live_pointer(source_rom_data, fr_rom_data, 0x417BD3)
        assert _decode_at(fr_rom_data, target) == "PC du Prof. Log"
