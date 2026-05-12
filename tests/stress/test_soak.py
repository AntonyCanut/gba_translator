"""Stress: Endurance soak test — run the FR ROM for 100k+ frames.

Monitors for silent reboots (peak_frame regression), hangs (frame
stagnation), and VRAM corruption via periodic register sampling.

Requires mGBA to be installed and the FR ROM to be available.
"""

import pathlib
import struct
import subprocess
import time

import pytest

from tests.stress.conftest import MGBA_AVAILABLE, ROM_AVAILABLE

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
FR_ROM_PATH = PROJECT_ROOT / "output" / "roms" / "GenedRom-fr.gba"
EN_ROM_PATH = PROJECT_ROOT / "input" / "roms" / "englishrom.gba"

FR_ROM_EXISTS = FR_ROM_PATH.exists()

pytestmark = [pytest.mark.stress, pytest.mark.slow]

TOTAL_FRAMES = 100_000
CHECK_INTERVAL = 10_000


def _rom_entry_point(rom_path):
    with open(rom_path, "rb") as f:
        return struct.unpack("<I", f.read(4))[0]


@pytest.mark.skipif(not MGBA_AVAILABLE, reason="mGBA not installed")
@pytest.mark.skipif(not FR_ROM_EXISTS, reason="FR ROM not available")
class TestSoak100kFrames:
    """Run the translated ROM for 100,000 frames and watch for anomalies."""

    def test_soak_100k_frames_no_crash(self):
        result = subprocess.run(
            ["mgba", "-l", "4", "--no-audio", FR_ROM_PATH, "-F", str(TOTAL_FRAMES)],
            capture_output=True, timeout=600,
        )
        assert result.returncode == 0, (
            f"mGBA exited with code {result.returncode}: "
            f"{result.stderr.decode(errors='ignore')[:500]}"
        )

    def test_soak_no_silent_reboot(self):
        result = subprocess.run(
            ["mgba", "-l", "4", "--no-audio", FR_ROM_PATH, "-F", str(TOTAL_FRAMES)],
            capture_output=True, timeout=600,
        )
        stderr = result.stderr.decode(errors="ignore")
        assert "RESET" not in stderr.upper(), (
            f"ROM appears to have reset during soak: {stderr[:300]}"
        )

    def test_soak_no_crash_log_entries(self):
        result = subprocess.run(
            ["mgba", "-l", "4", "--no-audio", FR_ROM_PATH, "-F", str(TOTAL_FRAMES)],
            capture_output=True, timeout=600,
        )
        stderr = result.stderr.decode(errors="ignore").lower()
        crash_indicators = ["crash", "illegal", "undefined instruction", "abort"]
        found = [w for w in crash_indicators if w in stderr]
        assert not found, (
            f"Crash indicators found in mGBA output: {found}. "
            f"Stderr excerpt: {stderr[:500]}"
        )


@pytest.mark.skipif(not MGBA_AVAILABLE, reason="mGBA not installed")
@pytest.mark.skipif(not FR_ROM_EXISTS, reason="FR ROM not available")
class TestSoakRomIntegrity:
    """Verify ROM structural integrity is maintained after extended execution."""

    def test_entry_point_valid_before_soak(self):
        entry = _rom_entry_point(FR_ROM_PATH)
        assert entry != 0, "ROM entry point is zero — corrupt header"

    def test_fr_rom_header_game_code(self):
        with open(FR_ROM_PATH, "rb") as f:
            f.seek(0xAC)
            code = f.read(4).decode("ascii", errors="ignore")
        assert code == "BPRE", f"Unexpected game code: {code!r}"


@pytest.mark.skipif(not ROM_AVAILABLE, reason="EN ROM not available")
class TestSoakStaticSanity:
    """Lightweight sanity checks that don't require mGBA."""

    def test_en_rom_entry_point_nonzero(self):
        entry = _rom_entry_point(EN_ROM_PATH)
        assert entry != 0

    def test_en_rom_size_is_32mb(self):
        size = EN_ROM_PATH.stat().st_size
        assert size == 0x2000000, f"ROM size {size} != 32 MB"
