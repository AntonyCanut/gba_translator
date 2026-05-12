"""E2E: Direct ROM content verification against translation source.

Reads the injected ROM at known offsets, decodes using CFRU charmap,
and compares with the expected translation from the JSON source file.
Also verifies French accent encoding and detects corrupted bytes.
"""

import json
import random

import pytest

from src.core.text_codec import (
    ENCODE_ALIASES,
    FRENCH_EXTENDED_TABLE,
    POKEMON_TABLE,
    POKEMON_TERMINATOR,
    TextDecoder,
    TextEncoder,
)


def _normalize_for_comparison(text: str) -> str:
    """Apply the same alias normalization the encoder uses."""
    for src, dst in ENCODE_ALIASES.items():
        text = text.replace(src, dst)
    return text


def _decode_rom_string_at(rom_data: bytes, offset: int, max_len: int = 500) -> str:
    """Decode a Pokemon-encoded string from ROM bytes at given offset."""
    end = min(offset + max_len, len(rom_data))
    raw = rom_data[offset:end]
    return TextDecoder.decode_pokemon(raw, preserve_unknown=True)


CONTROL_PREFIXES = (0xFC, 0xFD, 0xF8, 0xF9, 0xF7)


class TestRomContentMatchesTranslation:
    """Read ROM bytes at translation offsets and compare with expected text."""

    def test_top_100_longest_entries_match(self, injected_rom, translation_ready_path):
        output_path, _ = injected_rom
        with open(output_path, "rb") as f:
            rom_data = f.read()
        with open(translation_ready_path) as f:
            data = json.load(f)

        entries = [
            e for e in data.get("translations", [])
            if e.get("translation") and not e.get("too_long")
        ]
        entries.sort(key=lambda e: len(e.get("translation", "")), reverse=True)
        sample = entries[:100]

        matches = 0
        checked = 0
        for entry in sample:
            offset = entry["offset"]
            if offset >= len(rom_data):
                continue

            expected = _normalize_for_comparison(entry["translation"])
            decoded = _decode_rom_string_at(rom_data, offset)
            expected_norm = _normalize_for_comparison(expected)
            decoded_norm = _normalize_for_comparison(decoded)
            checked += 1

            if expected_norm == decoded_norm:
                matches += 1

        assert checked > 0, "No entries were checked"
        match_pct = matches / checked * 100
        assert match_pct >= 50.0, (
            f"Only {match_pct:.1f}% of top-100 longest entries match "
            f"({matches}/{checked})"
        )

    def test_random_50_entries_match(self, injected_rom, translation_ready_path):
        output_path, _ = injected_rom
        with open(output_path, "rb") as f:
            rom_data = f.read()
        with open(translation_ready_path) as f:
            data = json.load(f)

        entries = [
            e for e in data.get("translations", [])
            if e.get("translation") and not e.get("too_long")
        ]
        random.seed(42)
        sample = random.sample(entries, min(50, len(entries)))

        matches = 0
        checked = 0
        for entry in sample:
            offset = entry["offset"]
            if offset >= len(rom_data):
                continue

            expected = _normalize_for_comparison(entry["translation"])
            decoded = _decode_rom_string_at(rom_data, offset)
            expected_norm = _normalize_for_comparison(expected)
            decoded_norm = _normalize_for_comparison(decoded)
            checked += 1

            if expected_norm == decoded_norm:
                matches += 1

        assert checked > 0, "No entries were checked"
        match_pct = matches / checked * 100
        assert match_pct >= 50.0, (
            f"Only {match_pct:.1f}% of random-50 entries match "
            f"({matches}/{checked})"
        )


class TestFrenchAccentEncoding:
    """Verify critical French accented characters are correctly encoded in ROM."""

    CRITICAL_FR_CHARS = list(FRENCH_EXTENDED_TABLE.keys())

    def test_all_french_accents_have_rom_mapping(self):
        for char in self.CRITICAL_FR_CHARS:
            assert char in POKEMON_TABLE, (
                f"French character '{char}' has no POKEMON_TABLE entry"
            )
            byte_val = POKEMON_TABLE[char]
            encoded = TextEncoder.encode_pokemon(char)
            assert encoded[0] == byte_val, (
                f"'{char}' encodes to 0x{encoded[0]:02X}, "
                f"expected 0x{byte_val:02X}"
            )

    def test_french_accents_survive_encode_decode(self):
        for char in self.CRITICAL_FR_CHARS:
            encoded = TextEncoder.encode_pokemon(char)
            decoded = TextDecoder.decode_pokemon(encoded)
            assert decoded == char, (
                f"Round-trip failed for '{char}': got '{decoded}'"
            )

    def test_french_accents_present_in_injected_rom(
        self, injected_rom, translation_ready_path
    ):
        output_path, _ = injected_rom
        with open(output_path, "rb") as f:
            rom_data = f.read()
        with open(translation_ready_path) as f:
            data = json.load(f)

        entries = [
            e for e in data.get("translations", [])
            if e.get("translation") and not e.get("too_long")
        ]

        accent_bytes = {
            char: POKEMON_TABLE[char]
            for char in self.CRITICAL_FR_CHARS
        }
        found_accents = set()

        for entry in entries[:500]:
            offset = entry["offset"]
            if offset >= len(rom_data):
                continue
            end = min(offset + 500, len(rom_data))
            chunk = rom_data[offset:end]
            term = chunk.find(POKEMON_TERMINATOR)
            if term < 0:
                continue
            chunk = chunk[:term]
            for char, byte_val in accent_bytes.items():
                if byte_val in chunk:
                    found_accents.add(char)

        assert len(found_accents) >= 3, (
            f"Only {len(found_accents)} French accents found in ROM: "
            f"{found_accents}. Expected at least 3 of {self.CRITICAL_FR_CHARS}"
        )


class TestCorruptedBytesDetection:
    """Detect corrupted sequences in injected ROM strings."""

    def test_no_null_bytes_in_strings(self, injected_rom, translation_ready_path):
        output_path, _ = injected_rom
        with open(output_path, "rb") as f:
            rom_data = f.read()
        with open(translation_ready_path) as f:
            data = json.load(f)

        entries = [
            e for e in data.get("translations", [])
            if e.get("translation") and not e.get("too_long")
        ]

        corrupted = []
        for entry in entries[:500]:
            offset = entry["offset"]
            if offset >= len(rom_data):
                continue
            end = min(offset + 500, len(rom_data))
            chunk = rom_data[offset:end]
            term = chunk.find(POKEMON_TERMINATOR)
            if term <= 0:
                continue
            string_bytes = chunk[:term]
            # 0x00 is space in Pokemon encoding, but consecutive 0x00 is suspicious
            null_run = 0
            for b in string_bytes:
                if b == 0x00:
                    null_run += 1
                else:
                    null_run = 0
                if null_run >= 5:
                    corrupted.append(hex(offset))
                    break

        assert len(corrupted) == 0, (
            f"{len(corrupted)} strings have suspicious null runs: "
            f"{corrupted[:10]}"
        )

    def test_no_orphan_control_codes(self, injected_rom, translation_ready_path):
        output_path, _ = injected_rom
        with open(output_path, "rb") as f:
            rom_data = f.read()
        with open(translation_ready_path) as f:
            data = json.load(f)

        entries = [
            e for e in data.get("translations", [])
            if e.get("translation") and not e.get("too_long")
        ]

        orphan_count = 0
        for entry in entries[:500]:
            offset = entry["offset"]
            if offset >= len(rom_data):
                continue
            end = min(offset + 500, len(rom_data))
            chunk = rom_data[offset:end]
            term = chunk.find(POKEMON_TERMINATOR)
            if term <= 0:
                continue
            string_bytes = chunk[:term]
            i = 0
            while i < len(string_bytes):
                b = string_bytes[i]
                if b in (0xFC, 0xFD):
                    if i + 1 >= len(string_bytes):
                        orphan_count += 1
                        break
                i += 1

        assert orphan_count == 0, (
            f"{orphan_count} strings have orphan FC/FD control codes "
            f"(missing following byte)"
        )
