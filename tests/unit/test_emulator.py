import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from src.cooker.emulator import EmulatorBridge, EmulatorState, ConnectionError


class TestEmulatorState(unittest.TestCase):

    def test_defaults(self):
        state = EmulatorState()
        self.assertEqual(state.frame_count, 0)
        self.assertEqual(state.map_id, -1)
        self.assertFalse(state.in_battle)
        self.assertFalse(state.text_active)
        self.assertFalse(state.crashed)


class TestEmulatorBridgeInit(unittest.TestCase):

    def test_default_properties(self):
        bridge = EmulatorBridge()
        self.assertFalse(bridge.connected)
        self.assertEqual(bridge.frame_count, 0)
        self.assertEqual(bridge.crash_count, 0)
        self.assertEqual(bridge.reboot_count, 0)

    def test_custom_host_port(self):
        bridge = EmulatorBridge(host="192.168.1.1", port=9999)
        self.assertEqual(bridge._host, "192.168.1.1")
        self.assertEqual(bridge._port, 9999)


class TestPressKey(unittest.TestCase):

    def test_valid_key(self):
        bridge = EmulatorBridge()
        bridge._connected = True
        bridge._sock = MagicMock()
        bridge._sock.recv.return_value = b"OK\n"
        bridge.press_key("A", frames=4)
        self.assertEqual(bridge.frame_count, 4)

    def test_invalid_key_raises(self):
        bridge = EmulatorBridge()
        bridge._connected = True
        bridge._sock = MagicMock()
        with self.assertRaises(ValueError):
            bridge.press_key("INVALID")

    def test_all_valid_buttons(self):
        for button in EmulatorBridge.GBA_BUTTONS:
            bridge = EmulatorBridge()
            bridge._connected = True
            bridge._sock = MagicMock()
            bridge._sock.recv.return_value = b"OK\n"
            bridge.press_key(button)


class TestAdvanceFrames(unittest.TestCase):

    def test_frame_count_increments(self):
        bridge = EmulatorBridge()
        bridge._connected = True
        bridge._sock = MagicMock()
        bridge._sock.recv.return_value = b"OK\n"
        bridge.advance_frames(10)
        self.assertEqual(bridge.frame_count, 10)
        bridge.advance_frames(5)
        self.assertEqual(bridge.frame_count, 15)


class TestSendCommandErrors(unittest.TestCase):

    def test_not_connected_raises(self):
        bridge = EmulatorBridge()
        with self.assertRaises(ConnectionError):
            bridge._send_command("test")


class TestReadTextBuffer(unittest.TestCase):

    def test_decode_simple_text(self):
        bridge = EmulatorBridge()
        bridge._connected = True
        bridge._sock = MagicMock()
        text_bytes = [0xBB, 0xBC, 0xBD, 0xFF]
        bridge._sock.recv.return_value = (str(text_bytes) + "\n").encode()
        result = bridge.read_text_buffer()
        self.assertEqual(result, "ABC")

    def test_decode_with_newline(self):
        bridge = EmulatorBridge()
        bridge._connected = True
        bridge._sock = MagicMock()
        text_bytes = [0xBB, 0xFE, 0xBC, 0xFF]
        bridge._sock.recv.return_value = (str(text_bytes) + "\n").encode()
        result = bridge.read_text_buffer()
        self.assertEqual(result, "A\nB")

    def test_decode_digits(self):
        bridge = EmulatorBridge()
        bridge._connected = True
        bridge._sock = MagicMock()
        text_bytes = [0xA1, 0xA2, 0xA3, 0xFF]
        bridge._sock.recv.return_value = (str(text_bytes) + "\n").encode()
        result = bridge.read_text_buffer()
        self.assertEqual(result, "012")

    def test_decode_punctuation(self):
        bridge = EmulatorBridge()
        bridge._connected = True
        bridge._sock = MagicMock()
        text_bytes = [0xAB, 0xAC, 0xB0, 0xFF]
        bridge._sock.recv.return_value = (str(text_bytes) + "\n").encode()
        result = bridge.read_text_buffer()
        self.assertEqual(result, "!?.")


class TestDetectCrash(unittest.TestCase):

    def test_no_crash_initially(self):
        bridge = EmulatorBridge()
        bridge._connected = True
        bridge._sock = MagicMock()
        bridge._sock.recv.return_value = b"[1, 0, 0, 0]\n"
        bridge._frame_count = 200
        bridge._last_callback1 = 1
        self.assertFalse(bridge.detect_crash())

    def test_crash_on_stuck_callback(self):
        bridge = EmulatorBridge()
        bridge._connected = True
        bridge._sock = MagicMock()
        bridge._sock.recv.return_value = b"[0, 0, 0, 0]\n"
        bridge._frame_count = 200
        bridge._last_callback1 = 0
        self.assertTrue(bridge.detect_crash())
        self.assertEqual(bridge.crash_count, 1)


class TestDetectReboot(unittest.TestCase):

    def test_no_reboot_same_map(self):
        bridge = EmulatorBridge()
        bridge._connected = True
        bridge._sock = MagicMock()
        bridge._sock.recv.return_value = b"[5]\n"
        bridge._frame_count = 500
        self.assertFalse(bridge.detect_reboot(initial_map=5))

    def test_reboot_to_title(self):
        bridge = EmulatorBridge()
        bridge._connected = True
        bridge._sock = MagicMock()
        bridge._sock.recv.return_value = b"[0]\n"
        bridge._frame_count = 500
        self.assertTrue(bridge.detect_reboot(initial_map=5))
        self.assertEqual(bridge.reboot_count, 1)


class TestDisconnect(unittest.TestCase):

    def test_disconnect_clears_state(self):
        bridge = EmulatorBridge()
        bridge._connected = True
        bridge._sock = MagicMock()
        bridge.disconnect()
        self.assertFalse(bridge.connected)
        self.assertIsNone(bridge._sock)

    def test_disconnect_handles_no_socket(self):
        bridge = EmulatorBridge()
        bridge.disconnect()
        self.assertFalse(bridge.connected)


class TestReset(unittest.TestCase):

    def test_reset_clears_counters(self):
        bridge = EmulatorBridge()
        bridge._connected = True
        bridge._sock = MagicMock()
        bridge._sock.recv.return_value = b"OK\n"
        bridge._frame_count = 100
        bridge._crash_count = 3
        bridge._reboot_count = 1
        bridge.reset()
        self.assertEqual(bridge.frame_count, 0)
        self.assertEqual(bridge.crash_count, 0)
        self.assertEqual(bridge.reboot_count, 0)


if __name__ == "__main__":
    unittest.main()
