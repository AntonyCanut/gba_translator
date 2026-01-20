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
        english = 'Hello<0xFC><0x08><0x20>World'
        translation = 'Hello{PAUSE}OEWorld'
        expected = 'Hello<0xFC><0x08><0x20>World'
        self.assertEqual(
            TranslatedROMBuilder._apply_control_placeholders(translation, english),
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
