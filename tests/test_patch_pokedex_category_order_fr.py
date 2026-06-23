"""Tests for the Pokédex category/«Pokémon» order swap (Pokémon Souris).

Two layers:
  * byte-level: PATCHES are same-length, non-overlapping, apply, and idempotent.
  * behavioural: the PrintMonInfo render order is checked under unicorn by
    stubbing the engine's print + width helpers and recording the call
    sequence — proving "Souris Pokémon" (before) becomes "Pokémon Souris"
    (after).
"""

import os
import unittest

from scripts.patch_pokedex_category_order_fr import PATCHES, apply_patches


def _rom_with(offset: int, content: bytes, size: int = 0x100) -> bytearray:
    data = bytearray(size)
    data[offset: offset + len(content)] = content
    return data


class TestApplyPatches(unittest.TestCase):
    def test_applies_single_patch(self):
        patches = [(0x10, (b"\x02\xaa",), b"\x0c\x4a")]
        data = _rom_with(0x10, b"\x02\xaa")
        self.assertEqual(apply_patches(data, patches), 1)
        self.assertEqual(bytes(data[0x10:0x12]), b"\x0c\x4a")

    def test_idempotent_when_already_patched(self):
        patches = [(0x10, (b"\x02\xaa",), b"\x0c\x4a")]
        data = _rom_with(0x10, b"\x0c\x4a")
        self.assertEqual(apply_patches(data, patches), 0)
        self.assertEqual(bytes(data[0x10:0x12]), b"\x0c\x4a")

    def test_raises_on_unexpected_bytes(self):
        patches = [(0x10, (b"\x02\xaa",), b"\x0c\x4a")]
        data = _rom_with(0x10, b"\xab\xcd")
        with self.assertRaises(ValueError):
            apply_patches(data, patches)

    def test_raises_on_length_mismatch(self):
        patches = [(0x10, (b"\x02\xaa",), b"\x0c")]
        data = _rom_with(0x10, b"\x02\xaa")
        with self.assertRaises(ValueError):
            apply_patches(data, patches)

    def test_accepts_any_listed_old_form(self):
        """A slot matching any of several accepted forms maps to the same new."""
        patches = [(0x10, (b"\xaa\xaa", b"\xbb\xbb"), b"\xcc\xcc")]
        for form in (b"\xaa\xaa", b"\xbb\xbb"):
            data = _rom_with(0x10, form)
            self.assertEqual(apply_patches(data, patches), 1)
            self.assertEqual(bytes(data[0x10:0x12]), b"\xcc\xcc")


class TestRealPatches(unittest.TestCase):
    def test_all_forms_same_length_as_new(self):
        for offset, olds, new in PATCHES:
            for old in olds:
                self.assertEqual(len(old), len(new), f"length mismatch at 0x{offset:X}")

    def test_no_overlapping_patches(self):
        spans = []
        for offset, _olds, new in PATCHES:
            end = offset + len(new)
            for a, b in spans:
                self.assertFalse(
                    a < end and offset < b,
                    f"patch at 0x{offset:X} overlaps with 0x{a:X}-0x{b:X}",
                )
            spans.append((offset, end))

    def _synthetic(self, form_index: int) -> bytearray:
        size = max(off + len(new) for off, _olds, new in PATCHES) + 4
        data = bytearray(size)
        for offset, olds, _new in PATCHES:
            form = olds[min(form_index, len(olds) - 1)]
            data[offset: offset + len(form)] = form
        return data

    def test_applies_on_synthetic_rom_both_suffix_forms(self):
        for form_index in (0, 1):  # exercise both accepted suffix source states
            data = self._synthetic(form_index)
            self.assertEqual(apply_patches(data), len(PATCHES))

    def test_idempotent_on_synthetic_rom(self):
        data = self._synthetic(0)
        apply_patches(data)
        self.assertEqual(apply_patches(data), 0)

    def test_suffix_gets_trailing_not_leading_space(self):
        """The patched suffix must read 'Pokémon ' (trailing space, 0x00 last)."""
        new = next(n for off, _olds, n in PATCHES if off == 0x415F8F)
        self.assertEqual(new[-1], 0xFF, "must stay 0xFF-terminated")
        self.assertEqual(new[-2], 0x00, "space byte must be trailing, before 0xFF")
        self.assertNotEqual(new[0], 0x00, "no leading space anymore")


# ---------------------------------------------------------------------------
# Behavioural test: emulate PrintMonInfo's render section under unicorn and
# record the order in which the print helper (0x81047C8) is called and which
# string each call renders.  The width helper (0x8005ED4) is stubbed to return
# a fixed advance so print #2's x position can be checked.
# ---------------------------------------------------------------------------

_EN_ROM = os.path.join(os.path.dirname(__file__), "..", "input", "roms", "englishrom.gba")

try:
    import unicorn  # noqa: F401
    _UNICORN = True
except Exception:
    _UNICORN = False

_PRINT_FN = 0x081047C8
_WIDTH_FN = 0x08005ED4
_SUFFIX_PTR = 0x08415F8F      # &" Pokémon" / "Pokémon "
_STUB_WIDTH = 40             # arbitrary fixed width returned by the width helper
_INITIAL_X = 0x20
_CATEGORY_BUF = 0x03007F08   # sp + 8  (sp = 0x03007F00)


def _emulate_render(rom: bytes):
    """Run the PrintMonInfo render section; return the recorded print calls.

    Returns a list of dicts in call order: {"str": ptr, "x": value} for each
    call to the print helper, plus the string pointer passed to the width
    helper under key collected separately.
    Output: (print_calls, width_arg)
    """
    from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE, UcError
    from unicorn.arm_const import (
        UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_R1, UC_ARM_REG_R2,
        UC_ARM_REG_R3, UC_ARM_REG_R4, UC_ARM_REG_R6, UC_ARM_REG_R7,
        UC_ARM_REG_R8,
    )

    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    rom_size = (len(rom) + 0xFFF) & ~0xFFF
    uc.mem_map(0x08000000, rom_size)
    uc.mem_write(0x08000000, rom)
    uc.mem_map(0x03000000, 0x8000)  # IWRAM / stack

    # Stub the engine helpers in emulated memory so the BLs return cleanly.
    #   print helper:  bx lr                 (just record args via the hook)
    #   width helper:  movs r0,#40 ; bx lr   (fixed advance)
    uc.mem_write(_PRINT_FN & ~1, b"\x70\x47")
    uc.mem_write(_WIDTH_FN & ~1, b"\x28\x20\x70\x47")

    sp = 0x03007F00
    uc.reg_write(UC_ARM_REG_SP, sp)
    uc.reg_write(UC_ARM_REG_R8, 0x10)          # window id
    uc.reg_write(UC_ARM_REG_R7, 0x00)          # font/colour param
    uc.reg_write(UC_ARM_REG_R6, _INITIAL_X)    # initial x cursor
    uc.reg_write(UC_ARM_REG_R4, 0x00)
    uc.reg_write(UC_ARM_REG_LR, 0x08000001)
    # Pre-load the category buffer at sp+8 with "Souris" + 0xFF terminator.
    uc.mem_write(_CATEGORY_BUF, bytes([0xCD, 0xE3, 0xE9, 0xE6, 0xDD, 0xE7, 0xFF]))

    print_calls = []
    width_args = []

    def _hook(uc_, address, size, _user):
        if address == 0x08105890:        # bl print #1
            print_calls.append({"str": uc_.reg_read(UC_ARM_REG_R2),
                                "x": uc_.reg_read(UC_ARM_REG_R3)})
        elif address == 0x0810589A:      # bl GetStringWidth
            width_args.append(uc_.reg_read(UC_ARM_REG_R1))
        elif address == 0x081058B0:      # bl print #2
            print_calls.append({"str": uc_.reg_read(UC_ARM_REG_R2),
                                "x": uc_.reg_read(UC_ARM_REG_R3)})
            uc_.emu_stop()

    uc.hook_add(UC_HOOK_CODE, _hook)
    try:
        # Start at the render section (after the category buffer is built).
        uc.emu_start(0x08105888 | 1, 0x081058B4, count=400)
    except UcError:
        pass
    return print_calls, (width_args[0] if width_args else None)


@unittest.skipUnless(_UNICORN, "unicorn engine not installed")
@unittest.skipUnless(os.path.exists(_EN_ROM), "english source ROM not present")
class TestRenderOrder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = open(_EN_ROM, "rb").read()           # unpatched (English order)
        after = bytearray(cls.before)
        apply_patches(after)
        cls.after = bytes(after)

    def test_before_renders_category_then_pokemon(self):
        """Sanity: the unpatched ROM renders category first, suffix second."""
        calls, width_arg = _emulate_render(self.before)
        self.assertEqual(len(calls), 2, f"expected 2 print calls, got {calls}")
        self.assertEqual(calls[0]["str"], _CATEGORY_BUF, "1st print should be the category")
        self.assertEqual(calls[0]["x"], _INITIAL_X)
        self.assertEqual(width_arg, _CATEGORY_BUF, "advance should measure the category")
        self.assertEqual(calls[1]["str"], _SUFFIX_PTR, "2nd print should be ' Pokémon'")
        self.assertEqual(calls[1]["x"], _INITIAL_X + _STUB_WIDTH)

    def test_after_renders_pokemon_then_category(self):
        """The patched ROM renders 'Pokémon ' first, category second."""
        calls, width_arg = _emulate_render(self.after)
        self.assertEqual(len(calls), 2, f"expected 2 print calls, got {calls}")
        self.assertEqual(calls[0]["str"], _SUFFIX_PTR, "1st print should be 'Pokémon '")
        self.assertEqual(calls[0]["x"], _INITIAL_X)
        self.assertEqual(width_arg, _SUFFIX_PTR, "advance should measure the suffix")
        self.assertEqual(calls[1]["str"], _CATEGORY_BUF, "2nd print should be the category")
        self.assertEqual(calls[1]["x"], _INITIAL_X + _STUB_WIDTH)

    def test_after_suffix_bytes_have_trailing_space(self):
        # "Pokémon" + space (0x00) + 0xFF terminator
        self.assertEqual(self.after[0x415F8F:0x415F98],
                         b"\xca\xe3\xdf\x1b\xe1\xe3\xe2\x00\xff")


if __name__ == "__main__":
    unittest.main()
