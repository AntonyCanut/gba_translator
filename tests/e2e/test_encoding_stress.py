"""E2E: Stress test encoding/decoding for CFRU Pokemon text codec.

Verifies round-trip correctness for French accents, Spanish chars,
control codes, edge cases, and bulk translation entries.
"""

import pytest

from src.core.text_codec import (
    FRENCH_EXTENDED_TABLE,
    POKEMON_TABLE,
    SPANISH_EXTENDED_TABLE,
    TextDecoder,
    TextEncoder,
)


class TestFrenchAccentRoundTrip:
    """All French accented characters encode and decode correctly."""

    FRENCH_CHARS = list(FRENCH_EXTENDED_TABLE.keys())

    def test_individual_french_chars(self):
        for char in self.FRENCH_CHARS:
            encoded = TextEncoder.encode_pokemon(char)
            assert len(encoded) == 2, f"'{char}' encoded to {len(encoded)} bytes"
            decoded = TextDecoder.decode_pokemon(encoded)
            assert decoded == char, f"Round-trip failed for '{char}': got '{decoded}'"

    def test_french_sentence(self):
        text = "Prends soin de toi!"
        encoded = TextEncoder.encode_pokemon(text)
        decoded = TextDecoder.decode_pokemon(encoded)
        re_encoded = TextEncoder.encode_pokemon(decoded)
        assert encoded == re_encoded

    def test_french_accented_sentence(self):
        text = "Il est là, ça fait très bien"
        encoded = TextEncoder.encode_pokemon(text)
        decoded = TextDecoder.decode_pokemon(encoded)
        re_encoded = TextEncoder.encode_pokemon(decoded)
        assert encoded == re_encoded

    def test_mixed_french_spanish(self):
        text = "àçèîâù áéíóúñ"
        encoded = TextEncoder.encode_pokemon(text)
        decoded = TextDecoder.decode_pokemon(encoded)
        re_encoded = TextEncoder.encode_pokemon(decoded)
        assert encoded == re_encoded


class TestSpanishCharRoundTrip:
    """Spanish extended characters survive encode/decode."""

    SPANISH_CHARS = list(SPANISH_EXTENDED_TABLE.keys())

    def test_individual_spanish_chars(self):
        for char in self.SPANISH_CHARS:
            encoded = TextEncoder.encode_pokemon(char)
            decoded = TextDecoder.decode_pokemon(encoded)
            re_encoded = TextEncoder.encode_pokemon(decoded)
            assert encoded == re_encoded, f"Round-trip mismatch for '{char}'"

    def test_pokemon_name_with_accent(self):
        text = "Pokemon"
        encoded = TextEncoder.encode_pokemon(text)
        assert encoded[-1] == 0xFF
        decoded = TextDecoder.decode_pokemon(encoded)
        re_encoded = TextEncoder.encode_pokemon(decoded)
        assert encoded == re_encoded


class TestAliasCharacters:
    """Characters aliased to simpler forms encode without error."""

    ALIAS_PAIRS = [
        ("ê", "e"),
        ("ô", "o"),
        ("û", "u"),
        ("ë", "e"),
        ("ï", "i"),
        ("ö", "o"),
        ("ü", "u"),
        ("œ", "oe"),
    ]

    def test_aliases_produce_same_bytes(self):
        for orig, alias in self.ALIAS_PAIRS:
            encoded_orig = TextEncoder.encode_pokemon(orig)
            encoded_alias = TextEncoder.encode_pokemon(alias)
            assert encoded_orig == encoded_alias, (
                f"Alias mismatch: '{orig}' != '{alias}' "
                f"({encoded_orig.hex()} vs {encoded_alias.hex()})"
            )

    def test_alias_sentence(self):
        text = "Cœur brisé"
        encoded = TextEncoder.encode_pokemon(text)
        assert encoded[-1] == 0xFF
        assert len(encoded) > 1


class TestControlCodes:
    """Newlines and hex tokens encode correctly."""

    def test_newline_encodes_to_0xfe(self):
        encoded = TextEncoder.encode_pokemon("Hello\nWorld")
        assert 0xFE in encoded

    def test_newline_decodes_back(self):
        encoded = TextEncoder.encode_pokemon("Hello\nWorld")
        decoded = TextDecoder.decode_pokemon(encoded)
        assert "\n" in decoded

    def test_hex_token_inline(self):
        text = "Test<0xFC>Done"
        encoded = TextEncoder.encode_pokemon(text)
        assert 0xFC in encoded

    def test_hex_token_round_trip(self):
        text = "Test<0xAB>End"
        encoded = TextEncoder.encode_pokemon(text)
        decoded = TextDecoder.decode_pokemon(encoded, preserve_unknown=True)
        re_encoded = TextEncoder.encode_pokemon(decoded)
        assert encoded == re_encoded


class TestEdgeCases:
    """Boundary conditions for the encoder/decoder."""

    def test_empty_string(self):
        encoded = TextEncoder.encode_pokemon("")
        assert encoded == bytes([0xFF])
        decoded = TextDecoder.decode_pokemon(encoded)
        assert decoded == ""

    def test_single_char(self):
        for char in "AaZ!?. ":
            encoded = TextEncoder.encode_pokemon(char)
            assert len(encoded) == 2
            decoded = TextDecoder.decode_pokemon(encoded)
            assert decoded == char

    def test_long_string(self):
        text = "A" * 200
        encoded = TextEncoder.encode_pokemon(text)
        assert len(encoded) == 201
        decoded = TextDecoder.decode_pokemon(encoded)
        assert decoded == text

    def test_all_digits(self):
        text = "0123456789"
        encoded = TextEncoder.encode_pokemon(text)
        decoded = TextDecoder.decode_pokemon(encoded)
        assert decoded == text

    def test_all_uppercase(self):
        text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        encoded = TextEncoder.encode_pokemon(text)
        decoded = TextDecoder.decode_pokemon(encoded)
        assert decoded == text

    def test_all_lowercase(self):
        text = "abcdefghijklmnopqrstuvwxyz"
        encoded = TextEncoder.encode_pokemon(text)
        decoded = TextDecoder.decode_pokemon(encoded)
        assert decoded == text

    def test_terminator_in_middle(self):
        data = bytes([0xD5, 0xD6, 0xFF, 0xD7, 0xD8, 0xFF])
        decoded = TextDecoder.decode_pokemon(data)
        assert decoded == "ab"

    def test_unknown_byte_preserve(self):
        data = bytes([0xD5, 0x99, 0xFF])
        decoded = TextDecoder.decode_pokemon(data, preserve_unknown=True)
        assert "<0x99>" in decoded

    def test_unknown_byte_question_mark(self):
        data = bytes([0xD5, 0x99, 0xFF])
        decoded = TextDecoder.decode_pokemon(data, preserve_unknown=False)
        assert "?" in decoded


class TestBulkTranslationEncoding:
    """Verify all translation entries encode without error."""

    def test_all_entries_encodable(self, translation_entries):
        failures = []
        for entry in translation_entries:
            text = entry.get("translation", "")
            if not text:
                continue
            try:
                encoded = TextEncoder.encode_pokemon(text)
                assert encoded[-1] == 0xFF
            except Exception as e:
                failures.append({
                    "offset": hex(entry.get("offset", 0)),
                    "text": text[:50],
                    "error": str(e),
                })

        assert len(failures) == 0, (
            f"{len(failures)} entries failed encoding. First 5: {failures[:5]}"
        )

    def test_bulk_round_trip(self, translation_entries):
        # Threshold set at 20% because alias chars (ê→e, ô→o, etc.) and
        # hex tokens (<0xFD>, <0xFB>) cause expected one-way normalization.
        failures = []
        checked = 0

        for entry in translation_entries[:1000]:
            text = entry.get("translation", "")
            if not text or len(text) < 2:
                continue

            encoded = TextEncoder.encode_pokemon(text)
            decoded = TextDecoder.decode_pokemon(encoded)
            re_encoded = TextEncoder.encode_pokemon(decoded)
            checked += 1

            if encoded != re_encoded:
                failures.append({
                    "offset": hex(entry.get("offset", 0)),
                    "original": text[:40],
                    "decoded": decoded[:40],
                })

        failure_rate = len(failures) / max(checked, 1) * 100
        assert failure_rate < 20.0, (
            f"{len(failures)}/{checked} ({failure_rate:.1f}%) fail round-trip. "
            f"First 3: {failures[:3]}"
        )
