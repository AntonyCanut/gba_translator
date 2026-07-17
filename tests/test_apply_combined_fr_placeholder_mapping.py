import unittest

import scripts.apply_combined_fr as apply_combined_fr


class ApplyPlaceholderMappingTests(unittest.TestCase):
    def test_reordered_named_placeholders_resolve_by_name(self):
        # Regression (issue #123): English says "<name>'s <ability>" but
        # French reorders it to "<ability> de <name>". The old code zipped
        # placeholders to control tokens purely by position, so the first
        # "{...}" in French always grabbed the first "<0xFD>..." token
        # found in English regardless of which variable it actually named —
        # swapping the ability and the Pokemon name in the rendered banner.
        english = "<0xFD><0x0F>'s <0xFD><0x18>\nactivated!"
        translation = "{B_ATK_ABILITY} de\n{B_ATK_NAME_WITH_PREFIX} s'active !"
        expected = "<0xFD><0x18> de\n<0xFD><0x0F> s'active !"
        self.assertEqual(
            apply_combined_fr._apply_placeholder_mapping(translation, english),
            expected,
        )

    def test_in_order_named_placeholders_still_resolve(self):
        english = "<0xFD><0x02> gained <0xFD><0x16>!"
        translation = "{STR_VAR_1} a obtenu {B_LAST_ITEM} !"
        expected = "<0xFD><0x02> a obtenu <0xFD><0x16> !"
        self.assertEqual(
            apply_combined_fr._apply_placeholder_mapping(translation, english),
            expected,
        )

    def test_unknown_placeholder_falls_back_to_position(self):
        english = "<0xFD><0x00> semble tenir <0xFD><0x16>."
        translation = "{UNKNOWN_STR} seems to hold {B_LAST_ITEM}."
        expected = "<0xFD><0x00> seems to hold <0xFD><0x16>."
        self.assertEqual(
            apply_combined_fr._apply_placeholder_mapping(translation, english),
            expected,
        )

    def test_mismatched_placeholder_count_is_left_untouched(self):
        english = "<0xFD><0x18>"
        translation = "{B_ATK_ABILITY} de {B_ATK_NAME_WITH_PREFIX}"
        self.assertEqual(
            apply_combined_fr._apply_placeholder_mapping(translation, english),
            translation,
        )


if __name__ == '__main__':
    unittest.main()
