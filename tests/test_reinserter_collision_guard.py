"""Collision guard for SmartReinserter's in-place writes.

Root-cause fix for the inter-cell fusion / freeze collisions audited by
``scripts/audit_translation_collisions.py``: in the packed description tables
the 0x00/0xFF run after a terminator spills into the next cell, so the padding
heuristic over-counts and a longer translation would overrun its neighbour.
With ``collision_guard`` on and the cell boundaries supplied, a write that
cannot terminate before the next cell must relocate (or be left English) rather
than overwrite the neighbour.
"""

import struct
import unittest

from src.core.text_codec import TextEncoder
from src.core.text_reinserter import SmartReinserter


def _rom_with_cell(size=0x4000, offset=0x20, pointer_site=0):
    # A long 0xFF run after the 2-byte cell makes detect_padding over-count.
    rom = bytearray([0xFF] * size)
    rom[pointer_site:pointer_site + 4] = struct.pack('<I', 0x08000000 + offset)
    rom[offset:offset + len(TextEncoder.encode_pokemon('Hi'))] = \
        TextEncoder.encode_pokemon('Hi')
    return rom


BASE_TL = {
    'translation': 'Hello world',   # 11 glyphs — far past the 7-byte gap
    'encoding': 'pokemon',
    'original_length': 2,
}


class CollisionGuardTests(unittest.TestCase):
    def test_guard_relocates_overrunning_write(self):
        offset = 0x20
        rom = _rom_with_cell(offset=offset)
        tl = {**BASE_TL, 'offset': offset, 'pointer_offsets': [0]}
        # Next cell only 8 bytes away: the 11-glyph string cannot fit, so with
        # a live pointer it must relocate instead of overrunning.
        reinserter = SmartReinserter(
            rom, allow_relocate=True,
            collision_guard=True, cell_boundaries=[offset, offset + 8],
        )
        self.assertTrue(reinserter.reinsert_text(tl))
        reinserter.flush_relocations()
        new_ptr = struct.unpack('<I', rom[0:4])[0] - 0x08000000
        self.assertNotEqual(new_ptr, offset)  # repointed away → relocated
        # Nothing was written into the 8-byte in-place gap beyond a terminator.
        self.assertEqual(rom[offset + 7], 0xFF)

    def test_guard_skips_when_no_pointer_and_no_relocate(self):
        offset = 0x20
        rom = _rom_with_cell(offset=offset)
        before = bytes(rom[offset:offset + 8])
        tl = {**BASE_TL, 'offset': offset}  # phantom: no pointer_offsets
        reinserter = SmartReinserter(
            rom, allow_relocate=True,
            collision_guard=True, cell_boundaries=[offset, offset + 8],
        )
        # Too long for the gap, no pointer to relocate → left English, and
        # crucially the neighbour bytes are untouched.
        self.assertFalse(reinserter.reinsert_text(tl))
        self.assertEqual(bytes(rom[offset:offset + 8]), before)

    def test_guard_allows_write_when_it_fits_before_boundary(self):
        offset = 0x20
        rom = _rom_with_cell(offset=offset)
        tl = {**BASE_TL, 'offset': offset, 'translation': 'Yo',
              'pointer_offsets': [0]}
        reinserter = SmartReinserter(
            rom, allow_relocate=True,
            collision_guard=True, cell_boundaries=[offset, offset + 8],
        )
        self.assertTrue(reinserter.reinsert_text(tl))
        reinserter.flush_relocations()
        # Written in place (pointer unchanged) and terminated before boundary.
        self.assertEqual(struct.unpack('<I', rom[0:4])[0] - 0x08000000, offset)
        encoded = TextEncoder.encode_pokemon('Yo')
        self.assertEqual(bytes(rom[offset:offset + len(encoded)]), encoded)
        self.assertLess(offset + len(encoded) - 1, offset + 8)

    def test_no_guard_writes_in_place_using_overcounted_padding(self):
        # Without the guard the inflated padding lets the long string overrun —
        # the exact collision the guard prevents.
        offset = 0x20
        rom = _rom_with_cell(offset=offset)
        tl = {**BASE_TL, 'offset': offset, 'pointer_offsets': [0]}
        reinserter = SmartReinserter(rom, allow_relocate=True)
        self.assertTrue(reinserter.reinsert_text(tl))
        reinserter.flush_relocations()
        # Pointer unchanged (in-place) and the string ran past the 8-byte gap.
        self.assertEqual(struct.unpack('<I', rom[0:4])[0] - 0x08000000, offset)
        encoded = TextEncoder.encode_pokemon('Hello world')
        self.assertEqual(bytes(rom[offset:offset + len(encoded)]), encoded)


if __name__ == '__main__':
    unittest.main()
