"""Regression guard for scripts/patch_trainer_class_names_it.py.

The Italian trainer-class names live in a fixed-width table reached by index
arithmetic (``base + class_id * 13``); no pointer references the cells, so the
generic pipeline never touches them. This patch writes the Italian names from
``combined_it.txt`` in place. The tests below verify:

* fitting Italian text is written, terminated, and zero-padded *inside* the
  13-byte cell (never spilling into the neighbour);
* text that overflows the fixed cell is left untouched (kept English), never
  truncated;
* against the real source ROM + combined_it.txt, a sample of common classes
  decode to their expected Italian, while a known-overflow class stays English.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.patch_trainer_class_names_it import (  # noqa: E402
    CELL_STRIDE,
    CLASS_COUNT,
    TABLE_BASE,
    _encode,
    _load_combined,
    patch,
)
from src.text.charmap_data import BYTE_TO_CHAR  # noqa: E402

SOURCE_ROM = REPO_ROOT / "input/roms/englishrom.gba"
COMBINED = REPO_ROOT / "languages/it/combined_it.txt"


def _decode_cell(rom, offset: int) -> str:
    out = []
    for i in range(offset, offset + CELL_STRIDE):
        b = rom[i]
        if b == 0xFF:
            break
        out.append(BYTE_TO_CHAR.get(b) or f"[{b:02x}]")
    return "".join(out)


def _blank_table_rom() -> bytearray:
    size = TABLE_BASE + CLASS_COUNT * CELL_STRIDE + 0x100
    rom = bytearray(b"\xAB" * size)  # sentinel so stray writes are visible
    return rom


class TestTrainerClassPatchUnit(unittest.TestCase):
    def test_fitting_cell_written_and_bounded(self):
        rom = _blank_table_rom()
        idx = 3  # Agent -> Agente
        offset = TABLE_BASE + idx * CELL_STRIDE
        neighbour = TABLE_BASE + (idx + 1) * CELL_STRIDE
        combined = {offset: "Agente"}

        stats = patch(rom, combined)

        self.assertEqual(stats["written"], 1)
        self.assertEqual(_decode_cell(rom, offset), "Agente")
        # Terminator present and the rest of the cell zero-padded.
        cell = bytes(rom[offset:offset + CELL_STRIDE])
        self.assertIn(0xFF, cell)
        self.assertEqual(cell, _encode("Agente") + bytes(CELL_STRIDE - len(_encode("Agente"))))
        # Neighbour cell untouched (still sentinel).
        self.assertEqual(rom[neighbour], 0xAB)

    def test_overflow_cell_left_untouched(self):
        rom = _blank_table_rom()
        idx = 6  # Interviewer -> Intervistatore (15 bytes > 13)
        offset = TABLE_BASE + idx * CELL_STRIDE
        combined = {offset: "Intervistatore"}
        original = bytes(rom)

        stats = patch(rom, combined)

        self.assertEqual(stats["overflow"], 1)
        self.assertEqual(stats["written"], 0)
        self.assertEqual(bytes(rom), original)

    def test_special_tokens_expand(self):
        # \pk\mn -> PK/MN glyphs, \sm -> ♂ ; all must encode to a fitting cell.
        rom = _blank_table_rom()
        off_prof = TABLE_BASE + 97 * CELL_STRIDE
        off_swim = TABLE_BASE + 70 * CELL_STRIDE
        combined = {off_prof: "\\pk\\mn PROF.", off_swim: "Nuotatore\\sm"}

        patch(rom, combined)

        self.assertEqual(rom[off_prof], 0x53)      # PK glyph
        self.assertEqual(rom[off_prof + 1], 0x54)  # MN glyph
        self.assertEqual(_decode_cell(rom, off_swim), "Nuotatore♂")

    def test_never_writes_past_cell(self):
        rom = _blank_table_rom()
        # A name that exactly fills the cell (12 bytes + terminator).
        idx = 4
        offset = TABLE_BASE + idx * CELL_STRIDE
        text = "Cameriereee"  # 11 chars + term = 12 bytes, fits
        combined = {offset: text}
        patch(rom, combined)
        # Byte immediately after the cell stays sentinel.
        self.assertEqual(rom[offset + CELL_STRIDE], 0xAB)


@unittest.skipUnless(SOURCE_ROM.exists() and COMBINED.exists(),
                     "englishrom.gba / combined_it.txt not available")
class TestTrainerClassPatchAgainstSource(unittest.TestCase):
    """Exercise the patch on a copy of the real source ROM."""

    def setUp(self):
        self.rom = bytearray(SOURCE_ROM.read_bytes())
        self.combined = _load_combined(COMBINED)

    def test_common_classes_become_italian(self):
        patch(self.rom, self.combined)
        expected = {
            3: "Agente",        # Agent
            5: "Cameriera",     # Waitress
            7: "Ciclista",      # Cyclist
            10: "Infermiera",   # Nurse
            27: "Pokéfan",      # Pokéfan (identical, still a valid cell)
            70: "Nuotatore♂",   # Swimmer♂
        }
        for idx, want in expected.items():
            offset = TABLE_BASE + idx * CELL_STRIDE
            self.assertEqual(_decode_cell(self.rom, offset), want,
                             f"class idx {idx} @ {offset:#x}")

    def test_overflow_class_stays_english(self):
        before = _decode_cell(self.rom, TABLE_BASE + 6 * CELL_STRIDE)
        patch(self.rom, self.combined)
        after = _decode_cell(self.rom, TABLE_BASE + 6 * CELL_STRIDE)
        # Interviewer's Italian overflows the cell → English preserved.
        self.assertEqual(before, "Interviewer")
        self.assertEqual(after, "Interviewer")

    def test_reports_a_sane_split(self):
        stats = patch(self.rom, self.combined)
        # Structural sanity: most classes are covered, some overflow.
        self.assertGreaterEqual(stats["written"], 50)
        self.assertGreater(stats["overflow"], 0)
        self.assertEqual(
            stats["written"] + stats["unchanged"]
            + stats["overflow"] + stats["missing"],
            CLASS_COUNT - 1,  # cells 1..106
        )


if __name__ == "__main__":
    unittest.main()
