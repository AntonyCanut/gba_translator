"""Global pytest configuration — markers, fixtures, and test pyramid."""

import os
import shutil

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "benchmark: benchmarks de performance")
    config.addinivalue_line("markers", "stress: tests de stress (long)")
    config.addinivalue_line("markers", "slow: tests lents (>30s)")
    config.addinivalue_line("markers", "emulator: necessite mGBA")
    config.addinivalue_line("markers", "rom: necessite une ROM GBA")


ROM_ENV_VAR = "GBA_TEST_ROM"


@pytest.fixture(scope="session")
def rom_path():
    """Return the path to the test ROM, or skip if unavailable."""
    path = os.environ.get(ROM_ENV_VAR)
    if not path or not os.path.isfile(path):
        pytest.skip(f"ROM not available (set {ROM_ENV_VAR})")
    return path


@pytest.fixture(scope="session")
def rom_data(rom_path):
    """Load the test ROM as a bytearray."""
    with open(rom_path, "rb") as f:
        return bytearray(f.read())


@pytest.fixture(scope="session")
def mgba_available():
    """Check whether mGBA is on PATH."""
    if shutil.which("mgba") is None and shutil.which("mgba-sdl") is None:
        pytest.skip("mGBA not found on PATH")
    return True
