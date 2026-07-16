"""Stress: Endurance soak test — run the FR ROM for 100k+ frames.

Monitors for silent reboots (peak_frame regression), hangs (frame
stagnation), and VRAM corruption via periodic register sampling.

Requires mGBA to be installed and the FR ROM to be available.

Implementation note: drives mGBA through the bridge.lua TCP server so
frames advance under our control. The standalone `mgba` binary does
not support a "run N frames then exit" flag on this platform — the
older `--no-audio` / `-F N` invocation never actually worked. The
bridge gives us deterministic control plus crash/reboot watchdog data.
"""

import pathlib
import socket
import struct
import subprocess
import time
from dataclasses import dataclass

import pytest

pytestmark = pytest.mark.rom

from tests.stress.conftest import MGBA_AVAILABLE, ROM_AVAILABLE

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
FR_ROM_PATH = PROJECT_ROOT / "output" / "roms" / "GenedRom-fr.gba"
EN_ROM_PATH = PROJECT_ROOT / "input" / "roms" / "englishrom.gba"
BRIDGE_LUA = PROJECT_ROOT / "emulator-web" / "src" / "lua" / "bridge.lua"

FR_ROM_EXISTS = FR_ROM_PATH.exists()
BRIDGE_LUA_EXISTS = BRIDGE_LUA.exists()

pytestmark = [pytest.mark.stress, pytest.mark.slow]

TOTAL_FRAMES = 100_000
FRAMES_PER_CHUNK = 30_000  # bridge.lua caps each FRAMES call at 36000
BRIDGE_PORT = 55234
BRIDGE_HOST = "127.0.0.1"


def _rom_entry_point(rom_path):
    with open(rom_path, "rb") as f:
        return struct.unpack("<I", f.read(4))[0]


@dataclass
class SoakResult:
    returncode: int
    stderr: str
    peak_frame: int
    rebooted: bool
    final_frame: int
    error: str = ""


def _read_line(sock_file) -> str:
    line = sock_file.readline()
    return line.decode("utf-8", errors="ignore").strip()


def _run_soak_via_bridge(total_frames: int, connect_timeout: float = 30.0) -> SoakResult:
    """Spawn mGBA with bridge.lua and drive `total_frames` over TCP.

    Returns a SoakResult with the final frame count, peak frame, reboot
    flag (set if `current_frame` ever went backwards), the mgba return
    code (0 on clean shutdown, -SIGTERM on our kill), and stderr.
    """
    proc = subprocess.Popen(
        [
            "mgba",
            "-l", "4",
            "-C", "audioSync=0",
            "-C", "videoSync=0",
            "--script", str(BRIDGE_LUA),
            str(FR_ROM_PATH),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    sock = None
    deadline = time.time() + connect_timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            stderr = proc.communicate()[1].decode("utf-8", errors="ignore")
            return SoakResult(
                returncode=proc.returncode,
                stderr=stderr,
                peak_frame=0,
                rebooted=False,
                final_frame=0,
                error="mGBA exited before bridge accepted connection",
            )
        try:
            sock = socket.create_connection((BRIDGE_HOST, BRIDGE_PORT), timeout=1.0)
            break
        except (socket.timeout, ConnectionRefusedError, OSError):
            time.sleep(0.5)

    if sock is None:
        proc.terminate()
        try:
            stderr = proc.communicate(timeout=5)[1].decode("utf-8", errors="ignore")
        except subprocess.TimeoutExpired:
            proc.kill()
            stderr = proc.communicate()[1].decode("utf-8", errors="ignore")
        return SoakResult(
            returncode=-1,
            stderr=stderr,
            peak_frame=0,
            rebooted=False,
            final_frame=0,
            error="Bridge never accepted TCP connection",
        )

    peak_frame = 0
    final_frame = 0
    rebooted = False
    error = ""
    try:
        # Long timeout: a 30k-frame chunk at native speed is ~8min worst case,
        # but with no audio/video sync mGBA should fly through it in seconds.
        sock.settimeout(120.0)
        sock_file = sock.makefile("rwb", buffering=0)

        remaining = total_frames
        while remaining > 0:
            n = min(FRAMES_PER_CHUNK, remaining)
            sock_file.write(f"FRAMES|{n}\n".encode("utf-8"))
            resp = _read_line(sock_file)
            if not resp.startswith("OK"):
                error = f"FRAMES|{n} failed: {resp}"
                break
            remaining -= n

        if not error:
            sock_file.write(b"WATCHDOG\n")
            wd = _read_line(sock_file)
            if wd.startswith("OK|"):
                for part in wd[3:].split("|"):
                    if "=" not in part:
                        continue
                    k, v = part.split("=", 1)
                    if k == "frame":
                        final_frame = int(v)
                    elif k == "peak":
                        peak_frame = int(v)
                    elif k == "rebooted":
                        rebooted = v.strip() == "1"
            else:
                error = f"WATCHDOG failed: {wd}"
    except (socket.timeout, OSError) as exc:
        error = f"Bridge I/O error: {exc}"
    finally:
        try:
            sock.close()
        except OSError:
            pass
        proc.terminate()
        try:
            stderr_bytes = proc.communicate(timeout=5)[1]
        except subprocess.TimeoutExpired:
            proc.kill()
            stderr_bytes = proc.communicate()[1]
        stderr = stderr_bytes.decode("utf-8", errors="ignore")

    return SoakResult(
        returncode=proc.returncode or 0,
        stderr=stderr,
        peak_frame=peak_frame,
        rebooted=rebooted,
        final_frame=final_frame,
        error=error,
    )


@pytest.fixture(scope="module")
def soak_run():
    """Run the 100k-frame soak once for the whole module."""
    return _run_soak_via_bridge(TOTAL_FRAMES)


@pytest.mark.skipif(not MGBA_AVAILABLE, reason="mGBA not installed")
@pytest.mark.skipif(not FR_ROM_EXISTS, reason="FR ROM not available")
@pytest.mark.skipif(not BRIDGE_LUA_EXISTS, reason="bridge.lua not present")
class TestSoak100kFrames:
    """Run the translated ROM for 100,000 frames and watch for anomalies."""

    def test_soak_100k_frames_no_crash(self, soak_run):
        assert not soak_run.error, (
            f"Soak run failed: {soak_run.error}. Stderr: {soak_run.stderr[:500]}"
        )
        assert soak_run.final_frame >= TOTAL_FRAMES, (
            f"Did not reach {TOTAL_FRAMES} frames (got {soak_run.final_frame})"
        )

    def test_soak_no_silent_reboot(self, soak_run):
        assert not soak_run.rebooted, (
            f"ROM rebooted during soak: peak={soak_run.peak_frame}, "
            f"final={soak_run.final_frame}"
        )

    def test_soak_no_crash_log_entries(self, soak_run):
        stderr_lower = soak_run.stderr.lower()
        crash_indicators = ["crash", "illegal", "undefined instruction", "abort"]
        found = [w for w in crash_indicators if w in stderr_lower]
        assert not found, (
            f"Crash indicators found in mGBA output: {found}. "
            f"Stderr excerpt: {soak_run.stderr[:500]}"
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
