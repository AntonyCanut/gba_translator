import unittest

from src.core.text_validator import TextValidator


class TestIsCorrupted(unittest.TestCase):

    def test_empty_text_is_corrupted(self):
        is_corrupt, reason = TextValidator.is_corrupted("")
        self.assertTrue(is_corrupt)
        self.assertEqual(reason, "empty_text")

    def test_normal_text_not_corrupted(self):
        is_corrupt, _ = TextValidator.is_corrupted("Hello world!")
        self.assertFalse(is_corrupt)

    def test_high_suspicious_ratio(self):
        text = "????\x00\x00\xff\xff"
        is_corrupt, reason = TextValidator.is_corrupted(text)
        self.assertTrue(is_corrupt)
        self.assertIn("suspicious_ratio", reason)

    def test_unrealistic_length(self):
        text = "A" * 200
        is_corrupt, reason = TextValidator.is_corrupted(text)
        self.assertTrue(is_corrupt)
        self.assertIn("unrealistic_length", reason)

    def test_repeated_question_marks(self):
        is_corrupt, reason = TextValidator.is_corrupted("normal text here ???????? more text")
        self.assertTrue(is_corrupt)
        self.assertEqual(reason, "repeated_question_marks")

    def test_normal_pokemon_text(self):
        is_corrupt, _ = TextValidator.is_corrupted("Nurse Joy")
        self.assertFalse(is_corrupt)

    def test_accented_text_not_corrupted(self):
        is_corrupt, _ = TextValidator.is_corrupted("Pokémon est génial!")
        self.assertFalse(is_corrupt)


class TestIsValidGameText(unittest.TestCase):

    def test_valid_dialogue(self):
        is_valid, _ = TextValidator.is_valid_game_text("Hello, trainer!")
        self.assertTrue(is_valid)

    def test_corrupted_text_invalid(self):
        is_valid, reason = TextValidator.is_valid_game_text("")
        self.assertFalse(is_valid)
        self.assertIn("corrupted", reason)

    def test_no_normal_characters(self):
        is_valid, reason = TextValidator.is_valid_game_text("****")
        self.assertFalse(is_valid)
        self.assertIn("no_normal_characters", reason)

    def test_short_valid_text(self):
        is_valid, _ = TextValidator.is_valid_game_text("OK")
        self.assertTrue(is_valid)

    def test_single_char_valid(self):
        is_valid, _ = TextValidator.is_valid_game_text("A")
        self.assertTrue(is_valid)


class TestShouldSkipTest(unittest.TestCase):

    def test_valid_pair_not_skipped(self):
        should_skip, _ = TextValidator.should_skip_test("Hello", "Hola")
        self.assertFalse(should_skip)

    def test_invalid_english_skipped(self):
        should_skip, reason = TextValidator.should_skip_test("", "Hola")
        self.assertTrue(should_skip)
        self.assertIn("invalid_english", reason)

    def test_merged_texts_detected(self):
        should_skip, reason = TextValidator.should_skip_test("6 v 6", "6 v 6/Estándar")
        self.assertTrue(should_skip)
        self.assertEqual(reason, "merged_texts_in_spanish_rom")

    def test_unrealistic_length_ratio(self):
        should_skip, reason = TextValidator.should_skip_test("Hi", "H" * 100)
        self.assertTrue(should_skip)
        self.assertIn("unrealistic_length_ratio", reason)


class TestSanitizeText(unittest.TestCase):

    def test_sanitize_normal_text(self):
        result = TextValidator.sanitize_text_for_display("Hello World")
        self.assertEqual(result, "Hello World")

    def test_sanitize_truncates(self):
        long_text = "A" * 100
        result = TextValidator.sanitize_text_for_display(long_text, max_length=10)
        self.assertEqual(result, "AAAAAAAAAA...")
        self.assertEqual(len(result), 13)

    def test_sanitize_replaces_nonprintable(self):
        result = TextValidator.sanitize_text_for_display("AB\x01CD")
        self.assertEqual(result, "AB?CD")


if __name__ == "__main__":
    unittest.main()
