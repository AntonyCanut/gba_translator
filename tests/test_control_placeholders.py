import importlib
import unittest

from src.core.text_codec import TextEncoder


builder_module = importlib.import_module('src.translators.19_build_translated_rom_generic')
TranslatedROMBuilder = builder_module.TranslatedROMBuilder


class ControlPlaceholderTests(unittest.TestCase):
    def test_pause_until_press_replacement(self):
        english = 'This is it!<0xFC><0x09>'
        translation = 'This is it!{PAUSE_UNTIL_PRESS}'
        expected = 'This is it!<0xFC><0x09>'
        self.assertEqual(
            TranslatedROMBuilder._apply_control_placeholders(translation, english),
            expected,
        )

    def test_button_icon_replacement(self):
        english = '<0xF8><0x0A>Pick <0xF8> OK'
        english_raw = TextEncoder.encode_pokemon(english).hex()
        translation = '{DPAD_UPDOWN}Pick {SE_SHOP}OK'
        expected = '<0xF8><0x0A>Pick <0xF8><0x00>OK'
        self.assertEqual(
            TranslatedROMBuilder._apply_control_placeholders(translation, english, english_raw),
            expected,
        )

    def test_color_and_var_replacement(self):
        english = 'Test <0xFC><0x01><0x06><0xFD><0x02><0xFC><0x01><0x02>.'
        translation = 'Test {COLOR}A{STR_VAR_1}{COLOR}B.'
        expected = 'Test <0xFC><0x01><0x06><0xFD><0x02><0xFC><0x01><0x02>.'
        self.assertEqual(
            TranslatedROMBuilder._apply_control_placeholders(translation, english),
            expected,
        )

    def test_placeholder_payload_trim(self):
        # 0x20 decodes to 'î': the duplicated argument glyph after the
        # placeholder is consumed, nothing else.
        english = 'Hello<0xFC><0x08><0x20>World'
        translation = 'Hello{PAUSE}îWorld'
        expected = 'Hello<0xFC><0x08><0x20>World'
        self.assertEqual(
            TranslatedROMBuilder._apply_control_placeholders(translation, english),
            expected,
        )

    def test_placeholder_payload_trim_accent_folded(self):
        # Translators sometimes fold the accent of the duplicated glyph.
        english = 'Hello<0xFC><0x08><0x20>World'
        translation = 'Hello{PAUSE}iWorld'
        expected = 'Hello<0xFC><0x08><0x20>World'
        self.assertEqual(
            TranslatedROMBuilder._apply_control_placeholders(translation, english),
            expected,
        )

    def test_placeholder_keeps_first_letter_of_next_word(self):
        # Regression: the in-game string "…{PAUSE}îsentir ma propre
        # colère." lost its 's' because the old code skipped a fixed
        # len(seq)-1 characters — but the FC command byte (0x08) never
        # appears as a glyph, so only the 'î' duplicate must go.
        english = 'unless you want\nto<0xFC><0x08><0x20> feel my wrath.'
        translation = 'sauf si tu veux...\n{PAUSE}îsentir ma propre colère.'
        expected = 'sauf si tu veux...\n<0xFC><0x08><0x20>sentir ma propre colère.'
        self.assertEqual(
            TranslatedROMBuilder._apply_control_placeholders(translation, english),
            expected,
        )

    def test_placeholder_without_duplicated_glyph(self):
        # When the translation never duplicated the argument glyph, no
        # character may be consumed.
        english = 'Hello<0xFC><0x08><0x20>World'
        translation = 'Hello{PAUSE}Bonjour'
        expected = 'Hello<0xFC><0x08><0x20>Bonjour'
        self.assertEqual(
            TranslatedROMBuilder._apply_control_placeholders(translation, english),
            expected,
        )

    def test_fc_argument_counts_from_raw(self):
        # Battle menu header: FC 05 (palette, 1 arg) and FC 04 (colour/
        # highlight/shadow, 3 args) must keep their argument bytes. The
        # old 1-arg-only table truncated them, corrupting the menu.
        english = (
            '<0xFC><0x05><0x05><0xFC><0x04><0x0D><0x0E><0x0F>Fight'
            '<0xFC><0x13><0x38>Run'
        )
        english_raw = TextEncoder.encode_pokemon(english).hex()
        translation = '{FC05}{FC04}Combat{FC13}Fuite'
        expected = (
            '<0xFC><0x05><0x05><0xFC><0x04><0x0D><0x0E><0x0F>Combat'
            '<0xFC><0x13><0x38>Fuite'
        )
        self.assertEqual(
            TranslatedROMBuilder._apply_control_placeholders(
                translation, english, english_raw
            ),
            expected,
        )

    def test_var_placeholder_keeps_following_text(self):
        english = '<0xFD><0x00> gained!'
        translation = '{B_ATK_NAME_WITH_PREFIX}a gained!'
        expected = '<0xFD><0x00>a gained!'
        self.assertEqual(
            TranslatedROMBuilder._apply_control_placeholders(translation, english),
            expected,
        )


if __name__ == '__main__':
    unittest.main()
