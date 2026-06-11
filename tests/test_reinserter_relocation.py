import struct
import unittest

from src.core.text_codec import TextEncoder
from src.core.text_reinserter import SmartReinserter


class ReinserterRelocationTests(unittest.TestCase):
    def test_relocate_updates_pointer(self):
        # Free space must be a large 0xFF run to qualify for relocation.
        rom = bytearray([0xFF] * 0x4000)
        original_offset = 0x20
        rom[0:4] = struct.pack('<I', 0x08000000 + original_offset)

        original = TextEncoder.encode_pokemon('Hi')
        rom[original_offset:original_offset + len(original)] = original

        translation = {
            'offset': original_offset,
            'translation': 'Hello world',
            'encoding': 'pokemon',
            'original_length': 2,
            'padding_available': 0,
            'pointer_offsets': [0],
        }

        reinserter = SmartReinserter(rom, allow_relocate=True)
        success = reinserter.reinsert_text(translation)
        self.assertTrue(success)
        reinserter.flush_relocations()

        new_pointer = struct.unpack('<I', rom[0:4])[0] - 0x08000000
        self.assertNotEqual(new_pointer, original_offset)

        expected = TextEncoder.encode_pokemon('Hello world')
        actual = bytes(rom[new_pointer:new_pointer + len(expected)])
        self.assertEqual(expected, actual)

    def test_short_padding_runs_are_never_allocated(self):
        """Short 0xFF/0x00 runs are live data (sentinel arrays, zero-valued
        struct fields); allocating from them corrupted the battle engine."""
        from src.core.text_reinserter import FreeSpaceAllocator

        rom = bytearray([0xAB] * 0x2000)  # 8KB of non-padding data
        rom[0x900:0xA00] = b'\xff' * 0x100   # 256B FF run (sentinel array)
        rom[0xC00:0xD00] = b'\x00' * 0x100   # 256B zero run (struct fields)

        allocator = FreeSpaceAllocator(rom)
        self.assertEqual(allocator.blocks, [])
        self.assertIsNone(allocator.allocate(16))

    def test_large_run_allocated_with_margins(self):
        from src.core.text_reinserter import FreeSpaceAllocator

        rom = bytearray([0xAB] * 0x1000)  # 4KB data (no 0xFF/0x00 bytes)
        rom += b'\xff' * 0x2000           # 8KB free run at 0x1000
        rom += bytearray([0xAB] * 0x1000)

        allocator = FreeSpaceAllocator(rom)
        self.assertEqual(len(allocator.blocks), 1)
        start, length = allocator.blocks[0]
        self.assertEqual(start, 0x1000 + FreeSpaceAllocator.RUN_MARGIN)
        self.assertEqual(length, 0x2000 - 2 * FreeSpaceAllocator.RUN_MARGIN)
        alloc = allocator.allocate(64)
        self.assertEqual(alloc, 0x1000 + FreeSpaceAllocator.RUN_MARGIN)


if __name__ == '__main__':
    unittest.main()
