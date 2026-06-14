import unittest

from scripts.patch_time_format_fr import PATCHES, apply_patches, encode


def _rom_with(offset: int, content: bytes, size: int = 0x100) -> bytearray:
    data = bytearray(size)
    data[offset : offset + len(content)] = content
    return data


class TestApplyPatches(unittest.TestCase):
    def test_applies_and_is_idempotent(self):
        patches = [(0x10, b"\x04\xd9", b"\x04\xe0")]
        data = _rom_with(0x10, b"\x04\xd9")
        self.assertEqual(apply_patches(data, patches), 1)
        self.assertEqual(bytes(data[0x10:0x12]), b"\x04\xe0")
        self.assertEqual(apply_patches(data, patches), 0)

    def test_rejects_unexpected_bytes(self):
        patches = [(0x10, b"\x04\xd9", b"\x04\xe0")]
        data = _rom_with(0x10, b"\xab\xcd")
        with self.assertRaises(ValueError):
            apply_patches(data, patches)

    def test_rejects_length_mismatch(self):
        patches = [(0x10, b"\x04\xd9", b"\x04")]
        data = _rom_with(0x10, b"\x04\xd9")
        with self.assertRaises(ValueError):
            apply_patches(data, patches)

    def test_real_patches_preserve_length(self):
        for offset, old, new in PATCHES:
            self.assertEqual(len(old), len(new), hex(offset))

    def test_real_patches_against_english_rom_layout(self):
        # Replay every patch on a synthetic ROM seeded with the expected
        # original bytes — all must apply, none may overlap.
        size = max(off + len(old) for off, old, _ in PATCHES) + 4
        data = bytearray(size)
        spans = []
        for offset, old, _ in PATCHES:
            for a, b in spans:
                self.assertFalse(a < offset + len(old) and offset < b,
                                 f"overlap at 0x{offset:X}")
            spans.append((offset, offset + len(old)))
            data[offset : offset + len(old)] = old
        self.assertEqual(apply_patches(data), len(PATCHES))

    def test_save_template_drops_ampm_token(self):
        save = next(p for p in PATCHES if p[0] == 0x1F11DAC)
        self.assertIn(b"\xfd\x0a", save[1])
        self.assertNotIn(b"\xfd\x0a", save[2])
        # day/month/year order: FD04 before FD03 before FD02
        new = save[2]
        self.assertLess(new.index(b"\xfd\x04"), new.index(b"\xfd\x03"))
        self.assertLess(new.index(b"\xfd\x03"), new.index(b"\xfd\x02"))
        self.assertIn(encode("Jamais"), new)
        # the re-aimed template pointer must land on the byte after Jamais's
        # terminator inside the rewritten region
        jamais_end = new.index(b"\xff", new.index(encode("Jamais")))
        self.assertEqual(0x1F11DAC + jamais_end + 1, 0x1F11DB9)
        ptr = next(p for p in PATCHES if p[0] == 0x1EB6260)
        self.assertEqual(ptr[2], (0x09F11DB9).to_bytes(4, "little"))

    def test_weekdays_translated(self):
        wd = next(p for p in PATCHES if p[0] == 0xA4E554)
        self.assertEqual(len(wd[1]), 7 * 4)
        self.assertIn(encode("Sam"), wd[2])
        self.assertIn(encode("Dim"), wd[2])

    def test_bag_use_repoint(self):
        # String patch: 9 bytes of free space → "Utiliser\xFF"
        str_patch = next(p for p in PATCHES if p[0] == 0x284EAB)
        self.assertEqual(str_patch[1], b"\xff" * 9)
        self.assertEqual(str_patch[2], encode("Utiliser") + b"\xff")
        # Six pointer patches: old address 0x084161A0 → new 0x08284EAB
        old_ptr = b"\xa0\x61\x41\x08"
        new_ptr = b"\xab\x4e\x28\x08"
        ptr_offsets = [0x452EB8, 0x452EE0, 0x463150, 0x46437C, 0xA6BA64, 0xA6BA8C]
        for poff in ptr_offsets:
            patch = next((p for p in PATCHES if p[0] == poff), None)
            self.assertIsNotNone(patch, f"missing pointer patch at 0x{poff:X}")
            self.assertEqual(patch[1], old_ptr)
            self.assertEqual(patch[2], new_ptr)


if __name__ == "__main__":
    unittest.main()
