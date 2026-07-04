"""Locate & pin the real CFRU/Unbound ability-DESCRIPTION pointer table.

Ticket P-171 (ability-descriptions slice): the original claim that ability
descriptions live at ``0xA37D00-0xA40000`` is wrong — that range is the generic
builder's free-space relocation pool (relocated Pokédex/move blurbs), sitting
*above* the ability-NAME table at 0xA36398.

The real ability descriptions are pointer-referenced through
``gAbilityDescriptionPointers`` at **file offset 0x96DE04**, one 32-bit LE ROM
pointer per ability, **indexed by ability ID** (1:1 with the ability-name
table). The description text is scattered across several free-space pools, so it
can only be reached through this table — never by a fixed stride.

These tests are the machine-checkable proof of that finding and a regression
guard against anyone "fixing" ability descriptions at the dead 0xA37D00 offset.
They gate on the English ROM (skipped when it is absent, as in fast CI).
"""

import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from languages.en.tools.locate_ability_descriptions import (
    ABILITY_COUNT,
    ABILITY_DESC_POINTER_TABLE,
    ANCHORS,
    DEAD_CLAIMED_OFFSET,
    GBA_BASE,
    _decode,
    _name,
    _pointer,
    count_authored,
    locate_table,
    verify_alignment,
)

ENGLISH_ROM = (
    Path(__file__).parent.parent.parent.parent / "input" / "roms" / "englishrom.gba"
)


@pytest.mark.rom
class TestAbilityDescriptionTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ENGLISH_ROM.exists():
            raise unittest.SkipTest(f"English ROM not found at {ENGLISH_ROM}")
        cls.data = ENGLISH_ROM.read_bytes()

    def test_ability_count_matches_name_table(self):
        # 293 abilities (index 0 = "-------", last = "Royal Roar").
        self.assertEqual(ABILITY_COUNT, 293)
        self.assertEqual(_name(self.data, 0), "-------")
        self.assertEqual(_name(self.data, ABILITY_COUNT - 1), "Royal Roar")

    def test_pointer_table_found_by_byte_search(self):
        # Independently rediscover the table from a distinctive blurb (method
        # (a) from the ticket) and confirm it lands on the documented offset.
        self.assertEqual(locate_table(self.data), ABILITY_DESC_POINTER_TABLE)

    def test_one_to_one_index_alignment_with_names(self):
        ok, report = verify_alignment(self.data)
        self.assertTrue(ok, "ability descriptions not 1:1 aligned:\n" + "\n".join(report))

    def test_anchor_descriptions_are_addressed_by_ability_id(self):
        for index, expect_name, expect_desc in ANCHORS:
            self.assertEqual(_name(self.data, index), expect_name)
            ptr = _pointer(self.data, ABILITY_DESC_POINTER_TABLE, index)
            self.assertEqual(_decode(self.data, ptr - GBA_BASE), expect_desc)

    def test_descriptions_are_scattered_not_contiguous(self):
        # If the descriptions were a fixed-stride block, consecutive pointers
        # would step by a constant. They do not: the blurbs live in several
        # free-space pools, which is exactly why a stride-based patch is wrong.
        p0 = _pointer(self.data, ABILITY_DESC_POINTER_TABLE, 26)   # 0x0824F61F pool
        p1 = _pointer(self.data, ABILITY_DESC_POINTER_TABLE, 100)  # 0x08A3623A pool
        self.assertGreater(abs(p1 - p0), 0x100000)

    def test_most_abilities_have_authored_english_descriptions(self):
        # Vanilla + early-custom abilities carry a real blurb; the highest-ID
        # Unbound-custom abilities (Sound Waves, Royal Roar, ...) do not.
        authored = count_authored(self.data)
        self.assertGreaterEqual(authored, 250)
        self.assertLess(authored, ABILITY_COUNT)

    def test_claimed_offset_is_not_the_description_table(self):
        # The debunked 0xA37D00 must NOT decode as an ability description.
        blob = _decode(self.data, DEAD_CLAIMED_OFFSET)
        for _idx, _name_txt, desc in ANCHORS:
            self.assertNotEqual(blob, desc)

    def test_claimed_offset_is_above_the_ability_name_table(self):
        # 0xA37D00 sits past the name table (which ends at 0xA376FC) — proof it
        # is the free-space pool, not the descriptions (which are *below* names).
        self.assertGreater(DEAD_CLAIMED_OFFSET, 0xA376FC)


if __name__ == "__main__":
    unittest.main()
