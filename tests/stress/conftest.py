"""Shared fixtures for stress tests."""

import json
import pathlib
import shutil
import struct

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

EN_ROM_PATH = PROJECT_ROOT / "input" / "roms" / "englishrom.gba"
TRANSLATION_READY = PROJECT_ROOT / "output" / "translation" / "2026-01-16_translation_ready.json"

ROM_AVAILABLE = EN_ROM_PATH.exists()
TRANSLATION_AVAILABLE = TRANSLATION_READY.exists()

try:
    import subprocess
    _mgba_check = subprocess.run(
        ["mgba", "--version"],
        capture_output=True, timeout=5,
    )
    MGBA_AVAILABLE = _mgba_check.returncode == 0
except Exception:
    MGBA_AVAILABLE = False


GBA_ROM_BASE = 0x08000000
ROM_SIZE = 0x2000000  # 32 MB


def pytest_configure(config):
    config.addinivalue_line("markers", "stress: stress / long-running test")
    config.addinivalue_line("markers", "slow: test that takes more than a few seconds")


@pytest.fixture
def en_rom_path():
    if not EN_ROM_PATH.exists():
        pytest.skip("englishrom.gba not found in input/roms/")
    return EN_ROM_PATH


@pytest.fixture
def translation_ready_path():
    if not TRANSLATION_READY.exists():
        pytest.skip("2026-01-16_translation_ready.json not found")
    return TRANSLATION_READY


@pytest.fixture
def en_rom_data(en_rom_path):
    with open(en_rom_path, "rb") as f:
        return bytearray(f.read())


@pytest.fixture
def translation_entries(translation_ready_path):
    with open(translation_ready_path) as f:
        data = json.load(f)
    return data.get("translations", [])


@pytest.fixture
def rom_copy(tmp_path, en_rom_path):
    dst = tmp_path / "stress_test.gba"
    shutil.copy2(en_rom_path, dst)
    with open(dst, "rb") as f:
        rom_data = bytearray(f.read())
    return rom_data, dst


def make_fake_rom(size=ROM_SIZE, fill=0x42):
    rom = bytearray([fill] * size)
    rom[0xA0:0xAC] = b"POKEMON_UNB\x00"
    rom[0xAC:0xB0] = b"BPRE"
    rom[0xB0:0xB2] = b"01"
    return rom


def write_pointer(rom_data, pointer_offset, target_offset):
    struct.pack_into("<I", rom_data, pointer_offset, GBA_ROM_BASE + target_offset)


def read_pointer(rom_data, pointer_offset):
    val = struct.unpack_from("<I", rom_data, pointer_offset)[0]
    if GBA_ROM_BASE <= val < GBA_ROM_BASE + len(rom_data):
        return val - GBA_ROM_BASE
    return None


@pytest.fixture
def fake_rom():
    return make_fake_rom()
