import struct
import tempfile
import unittest
from pathlib import Path

from src.core.rom_reader import ROMReader, ROMError


def _make_rom(size: int = 16 * 1024 * 1024, title: str = "POKEMON_FIRE") -> bytes:
    """Create a minimal valid GBA ROM of the given size."""
    data = bytearray(size)
    # Write title at 0xA0
    title_bytes = title.encode("ascii")[:12]
    data[0xA0:0xA0 + len(title_bytes)] = title_bytes
    # Write game code at 0xAC
    data[0xAC:0xB0] = b"BPRE"
    # Write maker code at 0xB0
    data[0xB0:0xB2] = b"01"
    return bytes(data)


class TestROMReader(unittest.TestCase):

    def test_load_valid_rom(self):
        rom_bytes = _make_rom()
        with tempfile.NamedTemporaryFile(suffix=".gba", delete=False) as f:
            f.write(rom_bytes)
            f.flush()
            reader = ROMReader(f.name)
            reader.load()
        self.assertEqual(reader.rom_size, len(rom_bytes))
        self.assertIsNotNone(reader.rom_data)

    def test_load_nonexistent_raises(self):
        reader = ROMReader("/nonexistent/path/rom.gba")
        with self.assertRaises(FileNotFoundError):
            reader.load()

    def test_load_empty_rom_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".gba", delete=False) as f:
            path = f.name
        reader = ROMReader(path)
        with self.assertRaises(ROMError):
            reader.load()

    def test_load_too_small_rom_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".gba", delete=False) as f:
            f.write(b"\x00" * 1024)
            f.flush()
            reader = ROMReader(f.name)
        with self.assertRaises(ROMError):
            reader.load()

    def test_read_bytes(self):
        rom_bytes = bytearray(_make_rom())
        rom_bytes[0x100:0x105] = b"HELLO"
        with tempfile.NamedTemporaryFile(suffix=".gba", delete=False) as f:
            f.write(rom_bytes)
            f.flush()
            reader = ROMReader(f.name)
            reader.load()
        result = reader.read_bytes(0x100, 5)
        self.assertEqual(result, b"HELLO")

    def test_read_bytes_not_loaded_raises(self):
        reader = ROMReader("/tmp/dummy.gba")
        with self.assertRaises(ROMError):
            reader.read_bytes(0, 1)

    def test_read_bytes_invalid_offset_raises(self):
        rom_bytes = _make_rom()
        with tempfile.NamedTemporaryFile(suffix=".gba", delete=False) as f:
            f.write(rom_bytes)
            f.flush()
            reader = ROMReader(f.name)
            reader.load()
        with self.assertRaises(ValueError):
            reader.read_bytes(-1, 1)
        with self.assertRaises(ValueError):
            reader.read_bytes(reader.rom_size, 1)

    def test_read_pointer_valid(self):
        rom_bytes = bytearray(_make_rom())
        ptr = 0x08001000
        struct.pack_into("<I", rom_bytes, 0x200, ptr)
        with tempfile.NamedTemporaryFile(suffix=".gba", delete=False) as f:
            f.write(rom_bytes)
            f.flush()
            reader = ROMReader(f.name)
            reader.load()
        result = reader.read_pointer(0x200)
        self.assertEqual(result, 0x1000)

    def test_read_pointer_invalid_returns_none(self):
        rom_bytes = bytearray(_make_rom())
        struct.pack_into("<I", rom_bytes, 0x200, 0x00000001)
        with tempfile.NamedTemporaryFile(suffix=".gba", delete=False) as f:
            f.write(rom_bytes)
            f.flush()
            reader = ROMReader(f.name)
            reader.load()
        result = reader.read_pointer(0x200)
        self.assertIsNone(result)

    def test_is_valid_pointer(self):
        reader = ROMReader("/tmp/dummy.gba")
        reader.rom_size = 16 * 1024 * 1024
        self.assertTrue(reader.is_valid_pointer(0x08000000))
        self.assertTrue(reader.is_valid_pointer(0x08FFFFFF))
        self.assertFalse(reader.is_valid_pointer(0x07FFFFFF))
        self.assertFalse(reader.is_valid_pointer(0x0A000000))
        self.assertFalse(reader.is_valid_pointer(0x00000000))

    def test_write_bytes(self):
        rom_bytes = _make_rom()
        with tempfile.NamedTemporaryFile(suffix=".gba", delete=False) as f:
            f.write(rom_bytes)
            f.flush()
            reader = ROMReader(f.name)
            reader.load()
        self.assertFalse(reader.is_modified())
        reader.write_bytes(0x300, b"TEST")
        self.assertTrue(reader.is_modified())
        self.assertEqual(reader.read_bytes(0x300, 4), b"TEST")

    def test_write_bytes_out_of_bounds_raises(self):
        rom_bytes = _make_rom()
        with tempfile.NamedTemporaryFile(suffix=".gba", delete=False) as f:
            f.write(rom_bytes)
            f.flush()
            reader = ROMReader(f.name)
            reader.load()
        with self.assertRaises(ValueError):
            reader.write_bytes(reader.rom_size, b"\x00")

    def test_save_and_reload(self):
        rom_bytes = _make_rom()
        with tempfile.NamedTemporaryFile(suffix=".gba", delete=False) as f:
            f.write(rom_bytes)
            f.flush()
            reader = ROMReader(f.name)
            reader.load()
        reader.write_bytes(0x400, b"SAVE")
        out_path = Path(tempfile.mktemp(suffix=".gba"))
        reader.save(str(out_path), create_backup=False)
        self.assertFalse(reader.is_modified())

        reader2 = ROMReader(str(out_path))
        reader2.load()
        self.assertEqual(reader2.read_bytes(0x400, 4), b"SAVE")
        out_path.unlink(missing_ok=True)

    def test_get_rom_info(self):
        rom_bytes = _make_rom(title="POKEMON_FIRE")
        with tempfile.NamedTemporaryFile(suffix=".gba", delete=False) as f:
            f.write(rom_bytes)
            f.flush()
            reader = ROMReader(f.name)
            reader.load()
        info = reader.get_rom_info()
        self.assertEqual(info["game_code"], "BPRE")
        self.assertEqual(info["maker_code"], "01")
        self.assertIn("POKEMON", info["title"])
        self.assertEqual(info["size"], 16 * 1024 * 1024)

    def test_repr(self):
        reader = ROMReader("/tmp/test.gba")
        self.assertIn("not loaded", repr(reader))


if __name__ == "__main__":
    unittest.main()
