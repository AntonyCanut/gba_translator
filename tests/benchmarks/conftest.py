"""Benchmark fixtures — in-memory ROM, sample translations, timer helper."""

import time
from contextlib import contextmanager

import pytest

ROM_SIZE = 32 * 1024 * 1024  # 32 MB — standard GBA ROM size
SLOT_SIZE = 64  # bytes per text slot (data + padding + sentinel)


@contextmanager
def perf_timer(label: str = ""):
    """Context manager that measures elapsed wall-clock time."""
    start = time.perf_counter()
    result = {"elapsed": 0.0}
    yield result
    result["elapsed"] = time.perf_counter() - start
    if label:
        print(f"  [{label}] {result['elapsed']:.4f}s")


@pytest.fixture()
def timer():
    """Expose perf_timer as a fixture for test functions."""
    return perf_timer


FREE_REGION_START = 0x1FE0000  # last 128 KB: genuine, non-excluded free space


def _build_rom_with_slots(slot_size: int = SLOT_SIZE) -> bytearray:
    """Build a 32 MB ROM with sentinel bytes bounding each slot.

    Every *slot_size* bytes, a non-padding sentinel (0xAB) is placed so
    that SmartReinserter._detect_padding() terminates quickly instead of
    scanning millions of consecutive 0xFF bytes. The last 8 MB is left as
    one pure 0xFF run: the allocator only treats large runs as free space,
    short inter-sentinel runs are considered live data.
    """
    data = bytearray(b"\xFF" * ROM_SIZE)
    for offset in range(0, FREE_REGION_START, slot_size):
        data[offset] = 0xAB
    return data


@pytest.fixture(scope="module")
def rom_32mb():
    """32 MB ROM with slot sentinels for bounded padding scans."""
    return _build_rom_with_slots()


@pytest.fixture(scope="module")
def rom_with_data():
    """32 MB ROM with realistic occupied regions in the first 1 MB."""
    data = _build_rom_with_slots()
    for offset in range(0, 1024 * 1024, 4096):
        for i in range(256):
            data[offset + i] = i & 0xFE
    return data


def _make_translations(count: int, encoding: str = "pokemon") -> list:
    """Generate *count* translation entries spaced one slot apart."""
    translations = []
    base_offset = 0x100000
    for i in range(count):
        text = f"Translation entry number {i}"
        offset = base_offset + i * SLOT_SIZE
        translations.append(
            {
                "offset": offset,
                "translation": text,
                "encoding": encoding,
                "original_length": 40,
                "max_length": 60,
            }
        )
    return translations


@pytest.fixture(scope="module")
def sample_translations_small():
    """50 translation entries."""
    return _make_translations(50)


@pytest.fixture(scope="module")
def sample_translations_medium():
    """500 translation entries."""
    return _make_translations(500)


@pytest.fixture(scope="module")
def sample_translations_large():
    """5000 translation entries."""
    return _make_translations(5000)


@pytest.fixture(scope="module")
def large_texts():
    """Top-10 style large text entries (long strings)."""
    entries = []
    base_offset = 0x800000
    for i in range(10):
        text = (
            f"This is a very long translated text entry for stress testing. "
            f"Entry {i}. "
        ) * 5
        entries.append(
            {
                "offset": base_offset + i * 512,
                "translation": text,
                "encoding": "pokemon",
                "original_length": 400,
                "max_length": 500,
            }
        )
    return entries
