"""Unit tests for languages/fr/patches/move_names.py.

Move names live in a fixed-width 13-byte, 894-entry table whose live offset
depends on the base ROM: the stock 0xA40A10 on the clean vanilla base (what
every combined_<code>.txt records under), and the relocated 0x1B2980 on the old
French-patched base. ``resolve_live_base`` reads the live pointer from the ROM
so the patch targets the correct cell on either base; ``apply_to_rom`` then
remaps each legacy-offset entry to its move index and writes the live cell.
"""

import unittest

from languages.fr.patches.move_names import (
    LEGACY_TABLE_OFFSET,
    MOVE_COUNT,
    MOVE_NAME_PTR_SITE,
    MOVE_NAME_TABLE,
    MOVE_STRIDE,
    RELOCATED_TABLE_OFFSET,
    ROM_POINTER_BASE,
    _encode,
    apply_to_rom,
    resolve_live_base,
)


def _rom_with_cell(live_offset: int, name: str, size: int) -> bytearray:
    data = bytearray(size)
    data[0:size] = b"\xff" * size
    raw = _encode(name)
    data[live_offset : live_offset + len(raw)] = raw
    data[live_offset + len(raw)] = 0xFF
    return data


class TestApplyToRom(unittest.TestCase):
    def _kwargs(self, count: int):
        return {
            "legacy_base": LEGACY_TABLE_OFFSET,
            "live_base": MOVE_NAME_TABLE,
            "stride": MOVE_STRIDE,
            "count": count,
        }

    def test_patches_contaminated_cell(self):
        index = 1
        live_offset = MOVE_NAME_TABLE + index * MOVE_STRIDE
        legacy_offset = LEGACY_TABLE_OFFSET + index * MOVE_STRIDE
        data = _rom_with_cell(live_offset, "Écras'Face", live_offset + MOVE_STRIDE)
        translations = {legacy_offset: "Botta"}

        patched, warnings = apply_to_rom(data, translations, **self._kwargs(index + 1))

        self.assertEqual(patched, 1)
        self.assertEqual(warnings, [])
        raw = _encode("Botta")
        self.assertEqual(bytes(data[live_offset : live_offset + len(raw)]), raw)
        self.assertEqual(data[live_offset + len(raw)], 0xFF)

    def test_idempotent(self):
        index = 2
        live_offset = MOVE_NAME_TABLE + index * MOVE_STRIDE
        legacy_offset = LEGACY_TABLE_OFFSET + index * MOVE_STRIDE
        data = _rom_with_cell(live_offset, "Poing Karaté", live_offset + MOVE_STRIDE)
        translations = {legacy_offset: "Colpo Karate"}

        apply_to_rom(data, translations, **self._kwargs(index + 1))
        patched, _ = apply_to_rom(data, translations, **self._kwargs(index + 1))
        self.assertEqual(patched, 0)

    def test_skips_index_without_translation(self):
        index = 3
        live_offset = MOVE_NAME_TABLE + index * MOVE_STRIDE
        data = _rom_with_cell(live_offset, "Torgnoles", live_offset + MOVE_STRIDE)

        patched, warnings = apply_to_rom(data, {}, **self._kwargs(index + 1))

        self.assertEqual(patched, 0)
        self.assertEqual(warnings, [])
        self.assertEqual(bytes(data[live_offset : live_offset + len(_encode("Torgnoles"))]), _encode("Torgnoles"))

    def test_warns_and_skips_overflowing_name(self):
        index = 4
        live_offset = MOVE_NAME_TABLE + index * MOVE_STRIDE
        legacy_offset = LEGACY_TABLE_OFFSET + index * MOVE_STRIDE
        data = _rom_with_cell(live_offset, "Poing Comète", live_offset + MOVE_STRIDE)
        # 13 chars + terminator = 14 > 13-byte cell.
        translations = {legacy_offset: "Pugno Cometa!"}

        patched, warnings = apply_to_rom(data, translations, **self._kwargs(index + 1))

        self.assertEqual(patched, 0)
        self.assertEqual(len(warnings), 1)
        self.assertIn("byte cell", warnings[0])
        self.assertEqual(
            bytes(data[live_offset : live_offset + len(_encode("Poing Comète"))]),
            _encode("Poing Comète"),
        )

    def test_never_touches_legacy_offset(self):
        """The legacy address must never be read from the ROM, only used as a
        translations-dict lookup key — writing there would corrupt live
        Pokédex free-space text (see module docstring)."""
        index = 1
        legacy_offset = LEGACY_TABLE_OFFSET + index * MOVE_STRIDE
        live_offset = MOVE_NAME_TABLE + index * MOVE_STRIDE
        size = live_offset + MOVE_STRIDE
        data = bytearray(size)
        data[0:size] = b"\xff" * size
        translations = {legacy_offset: "Botta"}

        apply_to_rom(data, translations, **self._kwargs(index + 1))

        # Legacy offset is far below the live table / synthetic ROM size in
        # this test, so simply assert the function never indexes past `size`.
        self.assertEqual(len(data), size)
        raw = _encode("Botta")
        self.assertEqual(bytes(data[live_offset : live_offset + len(raw)]), raw)


class TestResolveLiveBase(unittest.TestCase):
    """resolve_live_base must follow the ROM's own pointer, not a hard-coded
    address, so the shared FR-core patch is correct on both the clean base
    (→ 0xA40A10) and the French-patched base (→ 0x1B2980)."""

    def _rom_pointing_at(self, base: int, size: int, placeholder: bool = True) -> bytearray:
        data = bytearray(b"\xff" * size)
        data[MOVE_NAME_PTR_SITE : MOVE_NAME_PTR_SITE + 4] = (
            ROM_POINTER_BASE + base
        ).to_bytes(4, "little")
        if placeholder:
            data[base] = _encode("-")[0]  # "-" glyph
            data[base + 1] = 0xFF
        return data

    def test_follows_pointer_to_clean_base(self):
        size = LEGACY_TABLE_OFFSET + MOVE_STRIDE * MOVE_COUNT
        data = self._rom_pointing_at(LEGACY_TABLE_OFFSET, size)
        self.assertEqual(resolve_live_base(data), LEGACY_TABLE_OFFSET)

    def test_follows_pointer_to_relocated_base(self):
        size = LEGACY_TABLE_OFFSET + MOVE_STRIDE * MOVE_COUNT
        data = self._rom_pointing_at(RELOCATED_TABLE_OFFSET, size)
        self.assertEqual(resolve_live_base(data), RELOCATED_TABLE_OFFSET)

    def test_falls_back_when_placeholder_missing(self):
        size = LEGACY_TABLE_OFFSET + MOVE_STRIDE * MOVE_COUNT
        data = self._rom_pointing_at(RELOCATED_TABLE_OFFSET, size, placeholder=False)
        self.assertEqual(resolve_live_base(data), LEGACY_TABLE_OFFSET)

    def test_falls_back_when_pointer_out_of_range(self):
        size = LEGACY_TABLE_OFFSET + MOVE_STRIDE * MOVE_COUNT
        data = bytearray(b"\xff" * size)
        data[MOVE_NAME_PTR_SITE : MOVE_NAME_PTR_SITE + 4] = (0xFFFFFFFF).to_bytes(4, "little")
        self.assertEqual(resolve_live_base(data), LEGACY_TABLE_OFFSET)

    def test_apply_to_rom_uses_resolved_base_by_default(self):
        # Pointer says the live table is at the clean-base offset; a translation
        # authored under the (identical) legacy key must land there, and the
        # relocated 0x1B2980 must stay untouched.
        size = LEGACY_TABLE_OFFSET + MOVE_STRIDE * MOVE_COUNT
        data = self._rom_pointing_at(LEGACY_TABLE_OFFSET, size)
        index = 1
        live_offset = LEGACY_TABLE_OFFSET + index * MOVE_STRIDE
        data[live_offset : live_offset + len(_encode("Pound"))] = _encode("Pound")
        data[live_offset + len(_encode("Pound"))] = 0xFF
        translations = {LEGACY_TABLE_OFFSET + index * MOVE_STRIDE: "Botta"}

        patched, warnings = apply_to_rom(data, translations, count=index + 1)

        self.assertEqual((patched, warnings), (1, []))
        raw = _encode("Botta")
        self.assertEqual(bytes(data[live_offset : live_offset + len(raw)]), raw)


if __name__ == "__main__":
    unittest.main()
