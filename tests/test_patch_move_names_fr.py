"""Unit tests for languages/fr/patches/move_names.py.

Move names live in a fixed-width 13-byte, 894-entry table at 0x1B2980 — but
every combined_<code>.txt records them at a stale "legacy" offset (0xA40A10)
that isn't the live table at all (it sits inside the generic builder's
Pokédex free-space pool). This patch remaps each legacy-offset entry to its
move index and writes it at the real table cell.
"""

import unittest

from languages.fr.patches.move_names import (
    LEGACY_TABLE_OFFSET,
    MOVE_NAME_TABLE,
    MOVE_STRIDE,
    _encode,
    apply_to_rom,
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


if __name__ == "__main__":
    unittest.main()
