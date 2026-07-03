import os
import unittest

from languages.fr.patches.pokedex_metrics import (
    PATCHES,
    apply_patches,
    _HEIGHT_BLOCK_NEW,
    _HEIGHT_BLOCK_OLD,
)


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

    def test_wailord_branch_left_as_english_original(self):
        """The two-digit-metres branch (0x105994) must NOT be patched.

        The English original already writes the ones digit from the modulo
        helper's r0 result.  An earlier session "fixed" a non-bug here by
        reading r1 instead — which is wrong because the modulo helper returns
        the remainder in r0, not r1.  Guard against reintroducing it.
        """
        self.assertNotIn(
            0x105994, [off for off, _, _ in PATCHES],
            "0x105994 must stay English-original; do not reintroduce the r1 patch",
        )


class TestHeightPatches(unittest.TestCase):
    def test_multiplier_patch_changes_10000_to_1(self):
        p = next(p for p in PATCHES if p[0] == 0x10597C)
        self.assertEqual(int.from_bytes(p[1], "little"), 10000)
        self.assertEqual(int.from_bytes(p[2], "little"), 1)

    def test_divisor_patch_changes_to_10(self):
        # Only one divisor patch remains: 0x105926 (dm ÷ 10 = metres).  The
        # second English divisor (0x10593C) is now inside the clean block.
        p = next(p for p in PATCHES if p[0] == 0x105926)
        self.assertEqual(p[1][1], 0x21, "not a MOVS r1,#imm8")
        self.assertEqual(p[2][1], 0x21, "replacement not MOVS r1,#imm8")
        self.assertEqual(p[2][0], 0x0A, "new divisor should be 10")

    def test_clean_block_present_and_sized(self):
        p = next(p for p in PATCHES if p[0] == 0x10592E)
        self.assertEqual(len(p[1]), len(p[2]))
        self.assertEqual(len(p[2]), 0x105954 - 0x10592E)  # 38 bytes
        self.assertEqual(p[2], _HEIGHT_BLOCK_NEW)
        self.assertEqual(p[1], _HEIGHT_BLOCK_OLD)

    def test_clean_block_instructions(self):
        """New block: adds r6,r5 / movs r0,#10 / muls r0,r6 / subs r0,r4,r0 / adds r5,r0 / NOPs."""
        new = _HEIGHT_BLOCK_NEW
        self.assertEqual(new[0:2], b"\x2e\x1c")   # adds r6,r5,#0   (r6 = metres)
        self.assertEqual(new[2:4], b"\x0a\x20")   # movs r0,#10
        self.assertEqual(new[4:6], b"\x70\x43")   # muls r0,r6      (10·metres)
        self.assertEqual(new[6:8], b"\x20\x1a")   # subs r0,r4,r0   (dm − 10·metres = decimal)
        self.assertEqual(new[8:10], b"\x05\x1c")  # adds r5,r0,#0   (r5 = decimal)
        self.assertEqual(new[10:], b"\xc0\x46" * 14)  # NOP padding

    def test_feet_mark_replaced_by_period(self):
        p = next(p for p in PATCHES if p[0] == 0x10599C)
        self.assertEqual(p[1], b"\xb4\x20")  # MOVS r0,#0xB4 (foot mark)
        self.assertEqual(p[2], b"\xad\x20")  # MOVS r0,#0xAD (period)

    def test_inch_mark_replaced_by_blank(self):
        p = next(p for p in PATCHES if p[0] == 0x1059C2)
        self.assertEqual(p[1], b"\xb2\x20")  # MOVS r0,#0xB2 (inch mark)
        self.assertEqual(p[2], b"\x00\x20")  # MOVS r0,#0x00 (space/blank)

    def test_decimal_digit_patch_writes_r5_plus_0xa1(self):
        # New code: ADDS r0,r5,#0 / ADDS r0,#0xA1 / STRB r0,[r4] / NOPs
        p = next(p for p in PATCHES if p[0] == 0x1059A4)
        new = p[2]
        self.assertEqual(new[0:2], b"\x28\x1c")   # MOV r0,r5
        self.assertEqual(new[2:4], b"\xa1\x30")   # ADDS r0,#0xA1
        self.assertEqual(new[4:6], b"\x20\x70")   # STRB r0,[r4]
        self.assertEqual(new[6:], b"\xc0\x46" * 3)

    def test_m_unit_write_patch(self):
        # 0xE1 is 'm' in CFRU charmap (a=0xD5, m=0xD5+12=0xE1)
        p = next(p for p in PATCHES if p[0] == 0x1059B0)
        new = p[2]
        self.assertEqual(new[0:2], b"\x04\xac")   # ADD r4,SP,#0x10
        self.assertEqual(new[2:4], b"\xe1\x20")   # MOVS r0,#0xE1
        self.assertEqual(new[4:6], b"\x20\x70")   # STRB r0,[r4]
        self.assertEqual(len(new), 14)
        self.assertEqual(new[6:], b"\xc0\x46" * 4)


class TestStringTablePatches(unittest.TestCase):
    def test_ht_renamed_to_ta(self):
        p = next(p for p in PATCHES if p[0] == 0x415F98)
        self.assertEqual(p[1], b"\xc2\xe8\xff")
        self.assertEqual(p[2], b"\xce\xd5\xff")

    def test_wt_renamed_to_po(self):
        p = next(p for p in PATCHES if p[0] == 0x415F9B)
        self.assertEqual(p[1], b"\xd1\xe8\xff")
        self.assertEqual(p[2], b"\xca\xe3\xff")

    def test_lbs_replaced_by_kg(self):
        p = next(p for p in PATCHES if p[0] == 0x415FA0)
        self.assertEqual(p[1], b"\xe0\xd6\xe7\xad\xff")
        self.assertEqual(p[2], b"\xdf\xdb\xff\x00\x00")
        self.assertEqual(p[2][0], 0xDF)  # 'k'
        self.assertEqual(p[2][1], 0xDB)  # 'g'
        self.assertEqual(p[2][2], 0xFF)  # terminator

    def test_weight_divisor_lbs_to_kg(self):
        # The pounds→kg value fix: conversion divisor 4536 → 10000 so the
        # formatter's input becomes kg×100 instead of pounds×100.  The
        # multiplier literal (100000) must NOT also be patched here — it is
        # reused for digit extraction.
        p = next(p for p in PATCHES if p[0] == 0x105AD4)
        self.assertEqual(int.from_bytes(p[1], "little"), 4536)
        self.assertEqual(int.from_bytes(p[2], "little"), 10000)
        self.assertNotIn(
            0x105AD0, [off for off, _, _ in PATCHES],
            "0x105AD0 (×100000) is reused for digit extraction; must stay",
        )


# ---------------------------------------------------------------------------
# Faithful behaviour test: execute the patched Thumb routine under an emulator.
#
# This is the test that would have caught the long-standing decimal-digit and
# rounding bugs: it does NOT re-implement the algorithm (which is exactly how
# earlier hand-simulations baked in the wrong register/ABI assumptions).  It
# runs the REAL bytes of PrintMonHeight (0x1058C4) from a freshly patched ROM
# and reads the formatted CFRU buffer back from the emulated stack.
# ---------------------------------------------------------------------------

_EN_ROM = os.path.join(os.path.dirname(__file__), "..", "input", "roms", "englishrom.gba")
_FR_ROM = os.path.join(os.path.dirname(__file__), "..", "output", "roms", "GenedRom-fr.gba")

try:
    import unicorn  # noqa: F401
    _UNICORN = True
except Exception:
    _UNICORN = False

_CFRU_DIGIT_0 = 0xA1
_CFRU_PERIOD = 0xAD
_CFRU_M = 0xE1


def _decode_metric(buf: bytes) -> str:
    """Decode the visible CFRU height buffer to an ASCII 'X.Ym' string."""
    out = []
    for x in buf:
        if _CFRU_DIGIT_0 <= x <= _CFRU_DIGIT_0 + 9:
            out.append(str(x - _CFRU_DIGIT_0))
        elif x == _CFRU_PERIOD:
            out.append(".")
        elif x == _CFRU_M:
            out.append("m")
        elif x in (0x00, 0xFF):
            continue  # leading blank / terminator
        else:
            out.append(f"<{x:02X}>")
    return "".join(out)


def _emulate_height(rom: bytes, dm: int) -> str:
    """Run PrintMonHeight on the patched ROM for a stored height of *dm* dm.

    Starts execution just after the species 'seen?' check (0x105922) with the
    decimetre value preloaded in r4 — exactly the state the routine is in for a
    seen Pokémon — and reads the 8-byte formatted buffer from sp+0xC.
    """
    from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UcError
    from unicorn.arm_const import (
        UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_R4,
    )

    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    rom_size = (len(rom) + 0xFFF) & ~0xFFF
    uc.mem_map(0x08000000, rom_size)
    uc.mem_write(0x08000000, rom)
    uc.mem_map(0x03000000, 0x8000)  # IWRAM / stack
    sp = 0x03007F00
    uc.reg_write(UC_ARM_REG_SP, sp)
    uc.reg_write(UC_ARM_REG_R4, dm)
    uc.reg_write(UC_ARM_REG_LR, 0x08000001)
    try:
        uc.emu_start(0x08105922 | 1, 0x08105A00, count=4000)
    except UcError:
        pass
    return _decode_metric(bytes(uc.mem_read(sp + 0x0C, 8)))


def _decode_weight(buf: bytes) -> str:
    """Decode the visible CFRU weight buffer to an ASCII 'X.Y' string.

    The buffer holds only the numeric part (digits + period); the "kg" label
    is printed separately by the engine and is not in this buffer.
    """
    out = []
    for x in buf:
        if _CFRU_DIGIT_0 <= x <= _CFRU_DIGIT_0 + 9:
            out.append(str(x - _CFRU_DIGIT_0))
        elif x == _CFRU_PERIOD:
            out.append(".")
        elif x == 0xFF:
            break  # terminator
        elif x == 0x00:
            continue  # leading blank (suppressed digit)
        else:
            out.append(f"<{x:02X}>")
    return "".join(out)


def _emulate_weight(rom: bytes, hg: int) -> str:
    """Run PrintMonWeight on the patched ROM for a stored weight of *hg* hg.

    Starts just after the species 'seen?' check (0x105A92) with the hectogram
    value preloaded in r4 — the state the routine is in for a seen Pokémon —
    and reads the formatted numeric buffer that starts at sp+0xB (the three
    bytes at sp+8 are the FC 14 05 colour control code).
    """
    from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UcError
    from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_R4

    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    rom_size = (len(rom) + 0xFFF) & ~0xFFF
    uc.mem_map(0x08000000, rom_size)
    uc.mem_write(0x08000000, rom)
    uc.mem_map(0x03000000, 0x8000)  # IWRAM / stack
    sp = 0x03007F00
    uc.reg_write(UC_ARM_REG_SP, sp)
    uc.reg_write(UC_ARM_REG_R4, hg)
    uc.reg_write(UC_ARM_REG_LR, 0x08000001)
    try:
        uc.emu_start(0x08105A92 | 1, 0x08105BE6, count=8000)
    except UcError:
        pass
    return _decode_weight(bytes(uc.mem_read(sp + 0x0B, 12)))


@unittest.skipUnless(_UNICORN, "unicorn engine not installed")
@unittest.skipUnless(os.path.exists(_FR_ROM), "built FR ROM not present")
class TestPatchedWeightRenders(unittest.TestCase):
    """Execute the real patched weight routine and verify rendered kilogrammes.

    This is the test that would have caught the "weight too high" bug: the
    earlier run only relabelled "lbs."→"kg" and never executed the routine, so
    the pound *value* (≈2.2× kg) stayed on screen under a kg label.
    """

    @classmethod
    def setUpClass(cls):
        cls.rom = open(_FR_ROM, "rb").read()

    def _check(self, hg, expected):
        self.assertEqual(_emulate_weight(self.rom, hg), expected, f"hg={hg}")

    def test_sub_one_kg(self):
        self._check(1, "0.1")    # Gastly 0.1 kg
        self._check(8, "0.8")    # Castform 0.8 kg
        self._check(9, "0.9")

    def test_single_digit_kg(self):
        self._check(69, "6.9")   # Bulbasaur 6.9 kg (was "15.2" = pounds)
        self._check(40, "4.0")
        self._check(90, "9.0")

    def test_two_and_three_digit_kg(self):
        self._check(100, "10.0")
        self._check(905, "90.5")    # Charizard 90.5 kg
        self._check(2200, "220.0")
        self._check(4600, "460.0")  # Snorlax 460.0 kg
        self._check(3980, "398.0")  # Wailord 398.0 kg

    def test_max_realistic_kg(self):
        self._check(9999, "999.9")

    def test_never_pounds_and_never_garbage(self):
        # Every realistic stored weight must render exactly hg/10 kg with one
        # decimal, never the pound value and never a stray glyph.
        for hg in range(1, 5000):
            s = _emulate_weight(self.rom, hg)
            self.assertNotIn("<", s, f"garbage glyph for hg={hg}: {s}")
            self.assertEqual(s, f"{hg // 10}.{hg % 10}", f"hg={hg}")


@unittest.skipUnless(_UNICORN, "unicorn engine not installed")
@unittest.skipUnless(os.path.exists(_FR_ROM), "built FR ROM not present")
class TestPatchedRoutineRenders(unittest.TestCase):
    """Execute the real patched routine and verify the rendered metric string."""

    @classmethod
    def setUpClass(cls):
        cls.rom = open(_FR_ROM, "rb").read()

    def _check(self, dm, expected):
        self.assertEqual(_emulate_height(self.rom, dm), expected, f"dm={dm}")

    def test_sub_one_metre(self):
        self._check(1, "0.1m")
        self._check(7, "0.7m")   # Bulbasaur
        self._check(9, "0.9m")

    def test_single_digit_metres(self):
        self._check(10, "1.0m")  # Ivysaur
        self._check(17, "1.7m")  # Charizard
        self._check(25, "2.5m")  # Lapras
        self._check(50, "5.0m")

    def test_rounding_regression_x5_to_x9(self):
        # The old rounding block corrupted any height whose metres digit was
        # ≥5 (e.g. dm=99 displayed as "1?.?m").  Must now be exact.
        self._check(99, "9.9m")
        self._check(55, "5.5m")

    def test_two_digit_metres(self):
        self._check(100, "10.0m")
        self._check(145, "14.5m")  # Wailord
        self._check(205, "20.5m")

    def test_decimal_digit_never_garbage(self):
        # Regression: every decimal digit used to render as 0xAB (garbage)
        # because the decimal was read from the wrong register.
        for dm in range(1, 160):
            s = _emulate_height(self.rom, dm)
            self.assertNotIn("<", s, f"garbage glyph for dm={dm}: {s}")
            self.assertEqual(s, f"{dm // 10}.{dm % 10}m", f"dm={dm}")


if __name__ == "__main__":
    unittest.main()
