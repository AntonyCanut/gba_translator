import unittest

from scripts.patch_pokedex_metrics_fr import PATCHES, apply_patches


def _rom_with(offset: int, content: bytes, size: int = 0x100) -> bytearray:
    data = bytearray(size)
    data[offset: offset + len(content)] = content
    return data


class TestApplyPatches(unittest.TestCase):
    def test_applies_single_patch(self):
        patches = [(0x10, b"\xfe\x21", b"\x0a\x21")]
        data = _rom_with(0x10, b"\xfe\x21")
        self.assertEqual(apply_patches(data, patches), 1)
        self.assertEqual(bytes(data[0x10:0x12]), b"\x0a\x21")

    def test_idempotent_when_already_patched(self):
        patches = [(0x10, b"\xfe\x21", b"\x0a\x21")]
        data = _rom_with(0x10, b"\x0a\x21")
        self.assertEqual(apply_patches(data, patches), 0)
        self.assertEqual(bytes(data[0x10:0x12]), b"\x0a\x21")

    def test_raises_on_unexpected_bytes(self):
        patches = [(0x10, b"\xfe\x21", b"\x0a\x21")]
        data = _rom_with(0x10, b"\xab\xcd")
        with self.assertRaises(ValueError):
            apply_patches(data, patches)

    def test_raises_on_length_mismatch(self):
        patches = [(0x10, b"\xfe\x21", b"\x0a")]
        data = _rom_with(0x10, b"\xfe\x21")
        with self.assertRaises(ValueError):
            apply_patches(data, patches)


class TestRealPatches(unittest.TestCase):
    def test_all_patches_same_length(self):
        for offset, old, new in PATCHES:
            self.assertEqual(len(old), len(new), f"length mismatch at 0x{offset:X}")

    def test_no_overlapping_patches(self):
        spans = []
        for offset, old, _ in PATCHES:
            end = offset + len(old)
            for a, b in spans:
                self.assertFalse(
                    a < end and offset < b,
                    f"patch at 0x{offset:X} overlaps with 0x{a:X}-0x{b:X}",
                )
            spans.append((offset, end))

    def test_all_patches_apply_on_synthetic_rom(self):
        size = max(off + len(old) for off, old, _ in PATCHES) + 4
        data = bytearray(size)
        for offset, old, _ in PATCHES:
            data[offset: offset + len(old)] = old
        self.assertEqual(apply_patches(data), len(PATCHES))

    def test_all_patches_idempotent_on_synthetic_rom(self):
        size = max(off + len(old) for off, old, _ in PATCHES) + 4
        data = bytearray(size)
        for offset, old, _ in PATCHES:
            data[offset: offset + len(old)] = old
        apply_patches(data)
        self.assertEqual(apply_patches(data), 0)  # second pass: 0 applied


class TestHeightPatches(unittest.TestCase):
    def test_multiplier_patch_changes_10000_to_1(self):
        p = next(p for p in PATCHES if p[0] == 0x10597C)
        # old: 0x2710 = 10000 little-endian
        self.assertEqual(int.from_bytes(p[1], "little"), 10000)
        self.assertEqual(int.from_bytes(p[2], "little"), 1)

    def test_divisor_patches_change_to_10(self):
        for off in (0x105926, 0x10593C):
            p = next(p for p in PATCHES if p[0] == off)
            # old: MOVS r1,#N — byte 0 is N, byte 1 is 0x21
            self.assertEqual(p[1][1], 0x21, f"0x{off:X}: not a MOVS r1,#imm8")
            self.assertEqual(p[2][1], 0x21, f"0x{off:X}: replacement not MOVS r1,#imm8")
            self.assertEqual(p[2][0], 0x0A, f"0x{off:X}: new divisor should be 10")

    def test_feet_mark_replaced_by_period(self):
        p = next(p for p in PATCHES if p[0] == 0x10599C)
        self.assertEqual(p[1], b"\xb4\x20")  # MOVS r0,#0xB4 (foot mark)
        self.assertEqual(p[2], b"\xad\x20")  # MOVS r0,#0xAD (period)

    def test_inch_mark_replaced_by_blank(self):
        p = next(p for p in PATCHES if p[0] == 0x1059C2)
        self.assertEqual(p[1], b"\xb2\x20")  # MOVS r0,#0xB2 (inch mark)
        self.assertEqual(p[2], b"\x00\x20")  # MOVS r0,#0x00 (space/blank)

    def test_decimal_digit_patch_writes_digit_plus_0xa1(self):
        # New code: ADDS r0,r5,#0 / ADDS r0,#0xA1 / STRB r0,[r4] / NOPs
        p = next(p for p in PATCHES if p[0] == 0x1059A4)
        new = p[2]
        # MOV r0,r5 preserved
        self.assertEqual(new[0:2], b"\x28\x1c")
        # ADDS r0,#0xA1 = 0x30A1
        self.assertEqual(new[2:4], b"\xa1\x30")
        # STRB r0,[r4,#0] = 0x7020
        self.assertEqual(new[4:6], b"\x20\x70")
        # rest NOPs
        self.assertEqual(new[6:], b"\xc0\x46" * 3)

    def test_m_unit_write_patch(self):
        # 0xE1 is 'm' in CFRU charmap (a=0xD5, m=0xD5+12=0xE1)
        p = next(p for p in PATCHES if p[0] == 0x1059B0)
        new = p[2]
        # ADD r4,SP,#0x10 preserved
        self.assertEqual(new[0:2], b"\x04\xac")
        # MOVS r0,#0xE1 = 0x20E1
        self.assertEqual(new[2:4], b"\xe1\x20")
        # STRB r0,[r4,#0] = 0x7020
        self.assertEqual(new[4:6], b"\x20\x70")
        # remaining 8 bytes: 4 NOPs (14-byte total slot)
        self.assertEqual(len(new), 14)
        self.assertEqual(new[6:], b"\xc0\x46" * 4)


class TestStringTablePatches(unittest.TestCase):
    def test_ht_renamed_to_ta(self):
        p = next(p for p in PATCHES if p[0] == 0x415F98)
        # CFRU: H=0xC2 t=0xE8 → T=0xCE a=0xD5
        self.assertEqual(p[1], b"\xc2\xe8\xff")
        self.assertEqual(p[2], b"\xce\xd5\xff")

    def test_wt_renamed_to_po(self):
        p = next(p for p in PATCHES if p[0] == 0x415F9B)
        # CFRU: W=0xD1 t=0xE8 → P=0xCA o=0xE3
        self.assertEqual(p[1], b"\xd1\xe8\xff")
        self.assertEqual(p[2], b"\xca\xe3\xff")

    def test_lbs_replaced_by_kg(self):
        p = next(p for p in PATCHES if p[0] == 0x415FA0)
        # CFRU: l=0xE0 b=0xD6 s=0xE7 .=0xAD → k=0xDF g=0xDB \xFF \x00 \x00
        self.assertEqual(p[1], b"\xe0\xd6\xe7\xad\xff")
        self.assertEqual(p[2], b"\xdf\xdb\xff\x00\x00")
        # kg\xFF is a valid 2-char string in CFRU
        self.assertEqual(p[2][0], 0xDF)  # 'k'
        self.assertEqual(p[2][1], 0xDB)  # 'g'
        self.assertEqual(p[2][2], 0xFF)  # terminator


if __name__ == "__main__":
    unittest.main()
