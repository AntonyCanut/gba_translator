import struct
import unittest

from scripts.repoint_stale_text_pointers import repoint, GBA_BASE


def _rom(size=0x200):
    return bytearray(size)


class RepointStalePointersTests(unittest.TestCase):
    def _entry(self, offset, raw, locations):
        return {
            'offset': offset,
            'raw_bytes': raw.hex(),
            'pointer_offsets': [f'0x{loc:08X}' for loc in locations],
        }

    def test_stale_pointer_is_retargeted(self):
        rom = _rom()
        original = 0x40
        relocated = 0x100
        english = b'\xbb\xbc\xff'           # untouched English bytes
        rom[original:original + 3] = english
        rom[relocated:relocated + 3] = b'\xbd\xbe\xff'
        # one pointer already re-targeted, one reverted by the repair pass
        struct.pack_into('<I', rom, 0x10, GBA_BASE + relocated)
        struct.pack_into('<I', rom, 0x20, GBA_BASE + original)

        fixed = repoint(rom, [self._entry(original, english, [0x10, 0x20])])

        self.assertEqual(fixed, 1)
        self.assertEqual(
            struct.unpack_from('<I', rom, 0x20)[0], GBA_BASE + relocated
        )

    def test_translated_in_place_is_left_alone(self):
        rom = _rom()
        original = 0x40
        english = b'\xbb\xbc\xff'
        rom[original:original + 3] = b'\xd5\xd6\xff'  # translated in place
        struct.pack_into('<I', rom, 0x10, GBA_BASE + 0x100)
        struct.pack_into('<I', rom, 0x20, GBA_BASE + original)

        fixed = repoint(rom, [self._entry(original, english, [0x10, 0x20])])

        self.assertEqual(fixed, 0)
        self.assertEqual(
            struct.unpack_from('<I', rom, 0x20)[0], GBA_BASE + original
        )

    def test_diverging_targets_are_left_alone(self):
        rom = _rom()
        original = 0x40
        english = b'\xbb\xbc\xff'
        rom[original:original + 3] = english
        struct.pack_into('<I', rom, 0x10, GBA_BASE + 0x100)
        struct.pack_into('<I', rom, 0x18, GBA_BASE + 0x140)
        struct.pack_into('<I', rom, 0x20, GBA_BASE + original)

        fixed = repoint(
            rom, [self._entry(original, english, [0x10, 0x18, 0x20])]
        )

        self.assertEqual(fixed, 0)

    def test_single_pointer_entry_is_skipped(self):
        rom = _rom()
        original = 0x40
        english = b'\xbb\xbc\xff'
        rom[original:original + 3] = english
        struct.pack_into('<I', rom, 0x20, GBA_BASE + original)

        fixed = repoint(rom, [self._entry(original, english, [0x20])])

        self.assertEqual(fixed, 0)


if __name__ == '__main__':
    unittest.main()
