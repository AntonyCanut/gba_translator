import importlib
import unittest

from src.core.fixed_tables import FIXED_TABLE_RANGES, in_fixed_table


builder_module = importlib.import_module('src.translators.19_build_translated_rom_generic')
TranslatedROMBuilder = builder_module.TranslatedROMBuilder
BuildConfig = builder_module.BuildConfig


class FixedTableRangeTests(unittest.TestCase):
    def test_move_name_cells_are_protected(self):
        # "Charge" / "Plaquage" cells whose rewrite fused into
        # "hargeurPlaquage" in battle.
        self.assertTrue(in_fixed_table(0x1B2B2C))
        self.assertTrue(in_fixed_table(0x1B2B34))

    def test_species_kind_cells_are_protected(self):
        self.assertTrue(in_fixed_table(0x1A35812))
        self.assertTrue(in_fixed_table(0x1A3AB9A))

    def test_dialogue_offsets_are_not_protected(self):
        self.assertFalse(in_fixed_table(0x1F2D162))  # overworld dialogue
        self.assertFalse(in_fixed_table(0x75CDE5))   # party-join string

    def test_engine_font_tables_are_protected(self):
        # Issue #97: glyph bytes of the raw text-printer fonts were extracted
        # as strings ("FüFgF") and re-encoded on injection, moving accent
        # pixels. The whole font complex must be off-limits to reinsertion.
        self.assertTrue(in_fixed_table(0x1EB266))   # é accent rows, FONT_SMALL
        self.assertTrue(in_fixed_table(0x2094E4))   # font-2 glyph rows
        self.assertTrue(in_fixed_table(0x21A0E1))   # font-4 glyph rows
        self.assertFalse(in_fixed_table(0x1EAEFF))  # just before the fonts
        self.assertFalse(in_fixed_table(0x230000))  # just after the fonts

    def test_ranges_are_well_formed(self):
        for start, end, _label in FIXED_TABLE_RANGES:
            self.assertLess(start, end)


class BuilderSkipsFixedTablesTests(unittest.TestCase):
    def test_prepare_translations_skips_protected_offsets(self):
        config = BuildConfig(
            source_rom=None,
            language='french',
        )
        builder = TranslatedROMBuilder(config)
        builder.translations = {
            0x1B2B2C: {  # move-name cell: must be skipped
                'offset': 0x1B2B2C,
                'translation': 'Chargeur',
                'encoding': 'pokemon',
            },
            0x1F2D162: {  # regular dialogue: must pass through
                'offset': 0x1F2D162,
                'translation': 'Alors dégage.',
                'encoding': 'pokemon',
            },
        }
        translations, stats = builder._prepare_translations()
        self.assertEqual(stats['fixed_table'], 1)
        self.assertEqual(len(translations), 1)
        self.assertEqual(translations[0]['offset'], 0x1F2D162)


if __name__ == '__main__':
    unittest.main()
