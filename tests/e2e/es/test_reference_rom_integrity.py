"""E2E: the ES reference ROM (spanishrom.gba) is a valid, unmodified GBA image.

Unlike FR/IT/DE, ES has no build step (``languages/es/lang.yaml`` declares
``build: none``) — ``spanishrom.gba`` is the community translation used as a
comparison reference by the pointer-based pipeline, not an artifact this repo
produces. These tests guard the reference ROM itself, not a build output.
"""

import pathlib
import struct

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
ES_ROM_PATH = REPO_ROOT / "input" / "roms" / "spanishrom.gba"
EN_ROM_PATH = REPO_ROOT / "input" / "roms" / "englishrom.gba"

GBA_ROM_SIZE = 0x2000000
GAME_CODE = b"BPRE"


@pytest.fixture(scope="module")
def es_rom_data():
    if not ES_ROM_PATH.exists():
        pytest.skip(f"{ES_ROM_PATH} not found")
    return ES_ROM_PATH.read_bytes()


@pytest.fixture(scope="module")
def en_rom_data():
    if not EN_ROM_PATH.exists():
        pytest.skip(f"{EN_ROM_PATH} not found")
    return EN_ROM_PATH.read_bytes()


class TestReferenceRomIntegrity:
    def test_rom_size(self, es_rom_data):
        assert len(es_rom_data) == GBA_ROM_SIZE, (
            f"ROM size {len(es_rom_data)} != {GBA_ROM_SIZE}"
        )

    def test_game_code_bpre(self, es_rom_data):
        code = es_rom_data[0xAC:0xB0]
        assert code == GAME_CODE, f"Game code corrupted: {code!r}"

    def test_entry_point_valid(self, es_rom_data):
        entry = struct.unpack_from("<I", es_rom_data, 0)[0]
        assert entry != 0, "Entry point is zero — ROM may be corrupted"

    def test_differs_from_english(self, es_rom_data, en_rom_data):
        """Sanity-check the known EN/ES divergence (~3.45%, see CLAUDE.md).

        Bounded on both sides: near 0% would mean the file is actually a copy
        of englishrom.gba, and a very high percentage would mean either ROM
        is corrupted or the wrong file was committed.
        """
        diff_count = sum(1 for a, b in zip(es_rom_data, en_rom_data) if a != b)
        diff_pct = diff_count / len(en_rom_data) * 100
        assert 1.0 < diff_pct < 10.0, (
            f"EN/ES ROM diff {diff_pct:.3f}% outside the expected ~3.45% baseline"
        )
