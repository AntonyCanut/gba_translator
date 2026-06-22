import struct
import unittest

from scripts.repoint_stale_text_pointers import (
    repoint,
    GBA_BASE,
    _is_setflag_chain,
)


def _rom(size=0x200):
    return bytearray(size)


class RepointStalePointersTests(unittest.TestCase):
    def _entry(self, offset, raw, locations):
        return {
            'offset': offset,
            'raw_bytes': raw.hex(),
            'byte_length': len(raw),
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

        fixed = repoint(
            rom,
            [self._entry(original, english, [0x10, 0x20])],
            {original},
        )

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

        fixed = repoint(
            rom,
            [self._entry(original, english, [0x10, 0x20])],
            {original},
        )

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
            rom,
            [self._entry(original, english, [0x10, 0x18, 0x20])],
            {original},
        )

        self.assertEqual(fixed, 0)

    def test_single_pointer_entry_is_skipped(self):
        rom = _rom()
        original = 0x40
        english = b'\xbb\xbc\xff'
        rom[original:original + 3] = english
        struct.pack_into('<I', rom, 0x20, GBA_BASE + original)

        fixed = repoint(
            rom,
            [self._entry(original, english, [0x20])],
            {original},
        )

        self.assertEqual(fixed, 0)

    def test_untranslated_entry_is_skipped(self):
        # A junk extraction entry (text bytes that scan like pointers)
        # must never be "repointed": the builder only relocates strings
        # that have a translation.
        rom = _rom()
        original = 0x40
        english = b'\xbb\xbc\xff'
        rom[original:original + 3] = english
        struct.pack_into('<I', rom, 0x10, GBA_BASE + 0x100)
        struct.pack_into('<I', rom, 0x20, GBA_BASE + original)

        fixed = repoint(
            rom,
            [self._entry(original, english, [0x10, 0x20])],
            set(),
        )

        self.assertEqual(fixed, 0)
        self.assertEqual(
            struct.unpack_from('<I', rom, 0x20)[0], GBA_BASE + original
        )

    def test_setflag_chain_is_vetoed_without_allowlist(self):
        # A stale "pointer" location that is really a `setflag` chain
        # (29 LL HH 29 LL HH) must never be rewritten — even when it is NOT in
        # PROTECTED_SCRIPT_OFFSETS. This is the Groudon-summon regression: the
        # window's bytes == the original string address, so it looks stale, but
        # it is script bytecode. Overwriting it breaks the cutscene → loop.
        rom = _rom(0x4000)
        # A string whose GBA address has 0x29 as its 2nd byte, so the stale
        # window itself reads like `setflag`'s opcode in the middle.
        original = 0x2900                      # GBA 0x08002900 -> LE 00 29 00 08
        self.assertEqual((GBA_BASE + original) >> 8 & 0xFF, 0x29)
        relocated = 0x100
        rom[relocated:relocated + 3] = b'\xbd\xbe\xff'
        english = b'\xbb\xbc\xff'
        rom[original:original + 3] = english
        # The clobber-prone location: flanked by setflag opcodes
        # (loc-2 == 0x29, and the window's own 2nd byte loc+1 == 0x29).
        loc = 0x80
        rom[loc - 2] = 0x29                    # previous setflag opcode
        struct.pack_into('<I', rom, loc, GBA_BASE + original)
        self.assertTrue(_is_setflag_chain(rom, loc))
        # one already-retargeted pointer + the stale setflag-chain location
        struct.pack_into('<I', rom, 0x10, GBA_BASE + relocated)

        fixed = repoint(
            rom,
            [self._entry(original, english, [0x10, loc])],
            {original},
        )

        self.assertEqual(fixed, 0)
        self.assertEqual(
            struct.unpack_from('<I', rom, loc)[0], GBA_BASE + original
        )

    def test_location_inside_translated_text_is_vetoed(self):
        # A "pointer" window overlapping a translated string's bytes is
        # really text that coincidentally decodes to the address — writing
        # it would corrupt the translation (the 0x75CB12 regression).
        rom = _rom()
        original = 0x40
        relocated = 0x100
        english = b'\xbb\xbc\xff'
        rom[original:original + 3] = english
        rom[relocated:relocated + 3] = b'\xbd\xbe\xff'
        # other translated string occupying 0x80..0x8A; the stale
        # location 0x88 falls inside its bytes.
        other = self._entry(0x80, b'\xd5' * 10 + b'\xff', [])
        struct.pack_into('<I', rom, 0x10, GBA_BASE + relocated)
        struct.pack_into('<I', rom, 0x88, GBA_BASE + original)

        fixed = repoint(
            rom,
            [self._entry(original, english, [0x10, 0x88]), other],
            {original, 0x80},
        )

        self.assertEqual(fixed, 0)
        self.assertEqual(
            struct.unpack_from('<I', rom, 0x88)[0], GBA_BASE + original
        )


if __name__ == '__main__':
    unittest.main()
