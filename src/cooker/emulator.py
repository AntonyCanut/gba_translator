"""EmulatorBridge — mGBA automation via TCP/Lua.

Provides a Python interface to control mGBA through its Lua scripting
bridge over TCP. Used by the cooker scenarios to drive gameplay
and observe game state.
"""

from __future__ import annotations

import json
import socket
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


MGBA_DEFAULT_HOST = "127.0.0.1"
MGBA_DEFAULT_PORT = 8888
SOCKET_TIMEOUT = 5.0
FRAME_DURATION_MS = 16.74  # ~59.73 fps for GBA


@dataclass
class EmulatorState:
    """Snapshot of emulator state at a point in time."""

    frame_count: int = 0
    map_id: int = -1
    player_x: int = 0
    player_y: int = 0
    in_battle: bool = False
    text_active: bool = False
    crashed: bool = False
    rebooted: bool = False


class ConnectionError(Exception):
    """Raised when the TCP connection to mGBA fails."""


class EmulatorBridge:
    """Controls mGBA via TCP/Lua for automated gameplay testing.

    The bridge sends Lua commands over a TCP socket to a running mGBA
    instance with the companion Lua script loaded. It can press buttons,
    advance frames, read memory, and take screenshots.

    Args:
        host: mGBA TCP host address.
        port: mGBA TCP port.
        rom_path: Path to the ROM file loaded in the emulator.
    """

    GBA_BUTTONS = {
        "A", "B", "START", "SELECT",
        "UP", "DOWN", "LEFT", "RIGHT",
        "L", "R",
    }

    # Pokemon Unbound memory addresses (BPRE-based)
    ADDR_MAP_BANK = 0x02036DFC
    ADDR_MAP_ID = 0x02036DFE
    ADDR_PLAYER_X = 0x02037078
    ADDR_PLAYER_Y = 0x0203707A
    ADDR_BATTLE_FLAG = 0x02023E8A
    ADDR_TEXT_FLAG = 0x020375C0
    ADDR_CALLBACK1 = 0x030030F0

    def __init__(
        self,
        host: str = MGBA_DEFAULT_HOST,
        port: int = MGBA_DEFAULT_PORT,
        rom_path: Optional[Path] = None,
    ):
        self._host = host
        self._port = port
        self._rom_path = rom_path
        self._sock: Optional[socket.socket] = None
        self._connected = False
        self._frame_count = 0
        self._crash_count = 0
        self._reboot_count = 0
        self._last_callback1 = 0
        self._screenshots: list[Path] = []

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def crash_count(self) -> int:
        return self._crash_count

    @property
    def reboot_count(self) -> int:
        return self._reboot_count

    def connect(self) -> None:
        """Establish TCP connection to mGBA Lua bridge."""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(SOCKET_TIMEOUT)
            self._sock.connect((self._host, self._port))
            self._connected = True
        except (socket.error, OSError) as exc:
            self._connected = False
            raise ConnectionError(
                f"Cannot connect to mGBA at {self._host}:{self._port}: {exc}"
            ) from exc

    def disconnect(self) -> None:
        """Close the TCP connection."""
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
            self._connected = False

    def _send_command(self, cmd: str) -> str:
        """Send a Lua command and read the response."""
        if not self._connected or not self._sock:
            raise ConnectionError("Not connected to mGBA")
        try:
            payload = (cmd + "\n").encode("utf-8")
            self._sock.sendall(payload)
            chunks: list[bytes] = []
            while True:
                chunk = self._sock.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
                if b"\n" in chunk:
                    break
            return b"".join(chunks).decode("utf-8").strip()
        except socket.timeout:
            return ""
        except (socket.error, OSError) as exc:
            self._connected = False
            raise ConnectionError(f"Communication error: {exc}") from exc

    def advance_frames(self, count: int = 1) -> None:
        """Advance the emulator by the given number of frames."""
        self._send_command(f"emu:advance({count})")
        self._frame_count += count

    def press_key(self, key: str, frames: int = 2) -> None:
        """Press a button for the specified number of frames.

        Args:
            key: Button name (A, B, START, SELECT, UP, DOWN, LEFT, RIGHT, L, R).
            frames: How many frames to hold the button.
        """
        key = key.upper()
        if key not in self.GBA_BUTTONS:
            raise ValueError(f"Unknown button: {key}. Valid: {self.GBA_BUTTONS}")
        self._send_command(f"emu:press('{key}', {frames})")
        self._frame_count += frames

    def press_sequence(self, keys: list[str], gap_frames: int = 4) -> None:
        """Press a sequence of keys with gaps between them."""
        for key in keys:
            self.press_key(key)
            self.advance_frames(gap_frames)

    def wait_frames(self, count: int) -> None:
        """Wait (advance) for the given number of frames."""
        self.advance_frames(count)

    def read_memory(self, address: int, size: int = 1) -> bytes:
        """Read bytes from a memory address."""
        resp = self._send_command(f"emu:readRange({address}, {size})")
        if not resp:
            return b"\x00" * size
        try:
            return bytes(json.loads(resp))
        except (json.JSONDecodeError, ValueError):
            return b"\x00" * size

    def read_u8(self, address: int) -> int:
        """Read an unsigned 8-bit value from memory."""
        data = self.read_memory(address, 1)
        return data[0]

    def read_u16(self, address: int) -> int:
        """Read an unsigned 16-bit little-endian value from memory."""
        data = self.read_memory(address, 2)
        return struct.unpack_from("<H", data, 0)[0]

    def read_u32(self, address: int) -> int:
        """Read an unsigned 32-bit little-endian value from memory."""
        data = self.read_memory(address, 4)
        return struct.unpack_from("<I", data, 0)[0]

    def screenshot(self, path: Optional[Path] = None) -> Path:
        """Take a screenshot and save it."""
        if path is None:
            path = Path(f"/tmp/mgba_screenshot_{self._frame_count}.png")
        self._send_command(f"emu:screenshot('{path}')")
        self._screenshots.append(path)
        return path

    def get_map_id(self) -> int:
        """Read the current map bank + map ID as a combined value."""
        bank = self.read_u8(self.ADDR_MAP_BANK)
        map_id = self.read_u8(self.ADDR_MAP_ID)
        return (bank << 8) | map_id

    def get_player_position(self) -> tuple[int, int]:
        """Read the player's X, Y position on the current map."""
        x = self.read_u16(self.ADDR_PLAYER_X)
        y = self.read_u16(self.ADDR_PLAYER_Y)
        return x, y

    def is_in_battle(self) -> bool:
        """Check if the game is currently in a battle."""
        flag = self.read_u16(self.ADDR_BATTLE_FLAG)
        return flag != 0

    def is_text_active(self) -> bool:
        """Check if a text box is currently displayed."""
        flag = self.read_u8(self.ADDR_TEXT_FLAG)
        return flag != 0

    def detect_crash(self) -> bool:
        """Detect if the game has crashed or entered an infinite loop.

        Checks for common crash indicators:
        - Callback1 stuck at 0 for too long
        - PC pointing at invalid address
        """
        cb1 = self.read_u32(self.ADDR_CALLBACK1)
        if cb1 == 0 and self._last_callback1 == 0 and self._frame_count > 120:
            self._crash_count += 1
            return True
        self._last_callback1 = cb1
        return False

    def detect_reboot(self, initial_map: int) -> bool:
        """Detect if the game rebooted back to the title screen."""
        current_map = self.get_map_id()
        # Map 0x0000 is typically the title/intro area
        if current_map == 0 and initial_map != 0 and self._frame_count > 300:
            self._reboot_count += 1
            return True
        return False

    def read_text_buffer(self, address: int = 0x02021D18, max_len: int = 256) -> str:
        """Read the active text buffer and decode it as Pokemon text."""
        data = self.read_memory(address, max_len)
        # Decode using Pokemon charmap (0xFF = terminator)
        chars: list[str] = []
        for byte in data:
            if byte == 0xFF:
                break
            if byte == 0xFE:
                chars.append("\n")
            elif 0xBB <= byte <= 0xD4:
                chars.append(chr(ord("A") + (byte - 0xBB)))
            elif 0xD5 <= byte <= 0xEE:
                chars.append(chr(ord("a") + (byte - 0xD5)))
            elif 0xA1 <= byte <= 0xAA:
                chars.append(chr(ord("0") + (byte - 0xA1)))
            elif byte == 0xAB:
                chars.append("!")
            elif byte == 0xAC:
                chars.append("?")
            elif byte == 0xB0:
                chars.append(".")
            elif byte == 0x00:
                chars.append(" ")
            else:
                chars.append(f"[{byte:02X}]")
        return "".join(chars)

    def get_state(self) -> EmulatorState:
        """Get a snapshot of the current emulator state."""
        return EmulatorState(
            frame_count=self._frame_count,
            map_id=self.get_map_id(),
            player_x=self.get_player_position()[0],
            player_y=self.get_player_position()[1],
            in_battle=self.is_in_battle(),
            text_active=self.is_text_active(),
            crashed=self.detect_crash(),
            rebooted=False,
        )

    def load_savestate(self, slot: int = 1) -> None:
        """Load a savestate from the given slot."""
        self._send_command(f"emu:loadState({slot})")
        self.advance_frames(2)

    def save_savestate(self, slot: int = 1) -> None:
        """Save current state to the given slot."""
        self._send_command(f"emu:saveState({slot})")

    def reset(self) -> None:
        """Reset the emulator (soft reset)."""
        self._send_command("emu:reset()")
        self._frame_count = 0
        self._crash_count = 0
        self._reboot_count = 0
        self._last_callback1 = 0
