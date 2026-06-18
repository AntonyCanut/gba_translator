import json
import os
import unittest

from scripts.patch_pokedex_categories_fr import (
    CODE_PATCHES,
    SUFFIX_OFFSET,
    _SUFFIX_NEW,
    _SUFFIX_OLD_FORMS,
    CAT_TABLE_BASE,
    CAT_TABLE_STRIDE,
    CAT_CELL_LEN,
    DEFAULT_MAP,
    apply_code_patches,
    apply_suffix,
    apply_cells,
    load_map,
)
from src.core.text_codec import TextDecoder, TextEncoder

_EN_ROM = os.path.join(os.path.dirname(__file__), "..", "input", "roms", "englishrom.gba")


# ---------------------------------------------------------------------------
# Static patch sanity
# ---------------------------------------------------------------------------
class TestCodePatches(unittest.TestCase):
    def test_all_same_length(self):
        for off, old, new in CODE_PATCHES:
            self.assertEqual(len(old), len(new), f"length mismatch at 0x{off:X}")

    def test_no_overlap(self):
        spans = []
        for off, old, _ in CODE_PATCHES:
            end = off + len(old)
            for a, b in spans:
                self.assertFalse(a < end and off < b, f"overlap at 0x{off:X}")
            spans.append((off, end))

    def test_suffix_target_is_pokemon_trailing_space(self):
        # new canonical suffix = "Pokémon " (trailing space) + terminator
        self.assertEqual(_SUFFIX_NEW, bytes.fromhex("cae3df1be1e3e200ff"))
        self.assertEqual(TextDecoder.decode_pokemon(_SUFFIX_NEW[:-1]), "Pokémon ")

    def test_apply_idempotent_on_synthetic(self):
        size = max(off + len(old) for off, old, _ in CODE_PATCHES) + 4
        data = bytearray(size)
        for off, old, _ in CODE_PATCHES:
            data[off:off + len(old)] = old
        self.assertEqual(apply_code_patches(data), len(CODE_PATCHES))
        self.assertEqual(apply_code_patches(data), 0)  # second pass = no-op

    def test_suffix_handles_both_layouts_and_is_idempotent(self):
        for old in _SUFFIX_OLD_FORMS:
            data = bytearray(0x416000)
            data[SUFFIX_OFFSET:SUFFIX_OFFSET + len(old)] = old
            self.assertEqual(apply_suffix(data), 1)
            self.assertEqual(bytes(data[SUFFIX_OFFSET:SUFFIX_OFFSET + len(_SUFFIX_NEW)]), _SUFFIX_NEW)
            self.assertEqual(apply_suffix(data), 0)  # idempotent

    def test_suffix_rejects_unexpected_bytes(self):
        data = bytearray(0x416000)
        data[SUFFIX_OFFSET:SUFFIX_OFFSET + 9] = b"\xde" * 9
        with self.assertRaises(ValueError):
            apply_suffix(data)


# ---------------------------------------------------------------------------
# Translation map
# ---------------------------------------------------------------------------
class TestTranslationMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fr = load_map(DEFAULT_MAP)

    def test_map_nonempty(self):
        self.assertGreater(len(self.fr), 600)

    def test_every_value_fits_cell(self):
        for en, fr in self.fr.items():
            enc = TextEncoder.encode_pokemon(fr)  # includes terminator
            self.assertLessEqual(len(enc), CAT_CELL_LEN,
                                 f"{en!r}->{fr!r} encodes to {len(enc)} bytes (cell={CAT_CELL_LEN})")

    def test_known_official_categories(self):
        self.assertEqual(self.fr["Mouse"], "Souris")    # Pikachu -> Pokémon Souris
        self.assertEqual(self.fr["Seed"], "Graine")     # Bulbasaur -> Pokémon Graine
        self.assertEqual(self.fr["Flame"], "Flamme")
        self.assertEqual(self.fr["Lizard"], "Lézard")

    def test_no_value_contains_pokemon_word(self):
        for fr in self.fr.values():
            self.assertNotIn("Pokémon", fr)
            self.assertNotIn("Pokemon", fr)


# ---------------------------------------------------------------------------
# Cell writing against the real source ROM
# ---------------------------------------------------------------------------
@unittest.skipUnless(os.path.exists(_EN_ROM), "source EN ROM not present")
class TestCellWriting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fr = load_map(DEFAULT_MAP)

    def test_writes_french_and_preserves_numeric_fields(self):
        rom = bytearray(open(_EN_ROM, "rb").read())
        # Snapshot numeric fields (+0x0C..+0x23) for a sample of records.
        sample = [1, 4, 7, 25, 100, 300]
        before = {i: bytes(rom[CAT_TABLE_BASE + i * CAT_TABLE_STRIDE + 0x0C:
                                CAT_TABLE_BASE + (i + 1) * CAT_TABLE_STRIDE]) for i in sample}
        stats = apply_cells(rom, self.fr)
        self.assertGreater(stats["translated"], 700)

        # Numeric tails untouched.
        for i in sample:
            after = bytes(rom[CAT_TABLE_BASE + i * CAT_TABLE_STRIDE + 0x0C:
                              CAT_TABLE_BASE + (i + 1) * CAT_TABLE_STRIDE])
            self.assertEqual(before[i], after, f"numeric fields clobbered at #{i}")

        # Pikachu (#25) category cell now decodes to "Souris".
        off = CAT_TABLE_BASE + 25 * CAT_TABLE_STRIDE
        end = rom.find(b"\xff", off)
        self.assertEqual(TextDecoder.decode_pokemon(rom[off:end]), "Souris")

    def test_idempotent(self):
        rom = bytearray(open(_EN_ROM, "rb").read())
        apply_cells(rom, self.fr)
        snapshot = bytes(rom)
        apply_cells(rom, self.fr)  # already French -> no change
        self.assertEqual(snapshot, bytes(rom))


# ---------------------------------------------------------------------------
# Faithful behaviour test: execute the REAL patched category routine
# (0x105800) under unicorn and verify the print order is now
# constant ("Pokémon ") first, category cell ("Souris") second.
# ---------------------------------------------------------------------------
try:
    import unicorn  # noqa: F401
    _UNICORN = True
except Exception:
    _UNICORN = False

_PRINT_FN = 0x08104AB0    # seen? check at 0x105830 (returns bool in r0)
_PRINT_STR = 0x081047C8   # prints r2=string at r3=x
_STR_WIDTH = 0x08005ED4   # GetStringWidth -> r0


@unittest.skipUnless(_UNICORN, "unicorn engine not installed")
@unittest.skipUnless(os.path.exists(_EN_ROM), "source EN ROM not present")
class TestPatchedRoutineReorders(unittest.TestCase):
    """Run the patched 0x105800 routine; capture the order of print calls."""

    @classmethod
    def setUpClass(cls):
        rom = bytearray(open(_EN_ROM, "rb").read())
        apply_code_patches(rom)
        apply_suffix(rom)
        cls.rom = bytes(rom)

    def _run(self, category: str):
        from unicorn import (
            Uc, UC_ARCH_ARM, UC_MODE_THUMB, UcError, UC_HOOK_CODE,
        )
        from unicorn.arm_const import (
            UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC,
            UC_ARM_REG_R0, UC_ARM_REG_R2, UC_ARM_REG_R3,
            UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_R8,
        )

        uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        rom_size = (len(self.rom) + 0xFFF) & ~0xFFF
        uc.mem_map(0x08000000, rom_size)
        uc.mem_write(0x08000000, self.rom)
        uc.mem_map(0x03000000, 0x10000)  # IWRAM: stack + the category source string

        cat_addr = 0x03001000
        uc.mem_write(cat_addr, TextEncoder.encode_pokemon(category))  # "<cat>\xff"

        sp = 0x03008000
        uc.reg_write(UC_ARM_REG_SP, sp)
        uc.reg_write(UC_ARM_REG_R5, cat_addr)  # r5 = category source pointer
        uc.reg_write(UC_ARM_REG_R6, 0x10)      # r6 = start x cursor
        uc.reg_write(UC_ARM_REG_R7, 0)
        uc.reg_write(UC_ARM_REG_R8, 0)
        uc.reg_write(UC_ARM_REG_LR, 0x08000001)

        calls = []  # ordered list of (string_ptr, x) for each print

        def hook(uc, address, size, _user):
            pc = address & ~1
            if pc == (_PRINT_FN & ~1):
                uc.reg_write(UC_ARM_REG_R0, 1)  # "seen" -> copy real category
                uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
            elif pc == (_STR_WIDTH & ~1):
                uc.reg_write(UC_ARM_REG_R0, 0x30)  # arbitrary non-zero width
                uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
            elif pc == (_PRINT_STR & ~1):
                calls.append((uc.reg_read(UC_ARM_REG_R2), uc.reg_read(UC_ARM_REG_R3)))
                uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

        uc.hook_add(UC_HOOK_CODE, hook)
        # Start just past the CFRU category-lookup trampoline (r5 already set).
        try:
            uc.emu_start(0x0810582A | 1, 0x081058BE, count=20000)
        except UcError:
            pass

        # Read back the stack category buffer (built at sp+8).
        buf = bytes(uc.mem_read(sp + 8, 16))
        end = buf.find(b"\xff")
        cell_text = TextDecoder.decode_pokemon(buf[:end]) if end >= 0 else ""
        return calls, cell_text

    def test_constant_printed_before_category(self):
        calls, cell_text = self._run("Souris")
        self.assertEqual(len(calls), 2, f"expected 2 print calls, got {calls}")
        # 1st print = the "Pokémon " constant string at 0x415F8F.
        self.assertEqual(calls[0][0], 0x08415F8F,
                         "first print must be the 'Pokémon ' constant")
        # 2nd print = the category buffer on the stack (the species noun).
        self.assertNotEqual(calls[1][0], 0x08415F8F)
        self.assertEqual(cell_text, "Souris")
        # 2nd print is positioned to the right of the 1st (cursor advanced).
        self.assertGreater(calls[1][1], calls[0][1])

    def test_rendered_phrase_is_pokemon_then_noun(self):
        """End-to-end: constant text + cell text == 'Pokémon ' + 'Souris'."""
        calls, cell_text = self._run("Souris")
        const_bytes = self.rom[0x415F8F:self.rom.find(b"\xff", 0x415F8F)]
        const_text = TextDecoder.decode_pokemon(const_bytes)
        self.assertEqual(const_text, "Pokémon ")
        self.assertEqual(const_text + cell_text, "Pokémon Souris")


if __name__ == "__main__":
    unittest.main()
