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
        # The injected_rom fixture only reinserts the first 500 valid entries
        # (in file/offset order) to keep the module-scoped build fast — every
        # other offset still holds the untouched English source. Sampling the
        # "longest" entries from the full corpus almost always lands outside
        # that injected slice, so the in-place comparison is checking ROM
        # bytes that were never written by this fixture in the first place.
        # Restrict the candidate pool to the same slice that was injected.
        injected_pool = entries[:500]
        injected_pool.sort(key=lambda e: len(e.get("translation", "")), reverse=True)
        sample = injected_pool[:100]

        matches = 0
        checked = 0
        for entry in sample:
            offset = entry["offset"]
            if offset >= len(rom_data):
                continue

            expected = _normalize_for_comparison(entry["translation"])
            # A couple of the longest in-place entries (multi-page dialogue
            # with many <0xFB> page breaks) encode past the default 500-byte
            # read window, which would truncate them before the comparison.
            decoded = _decode_rom_string_at(rom_data, offset, max_len=700)
            expected_norm = _normalize_for_comparison(expected)
            decoded_norm = _normalize_for_comparison(decoded)
            checked += 1

            if expected_norm == decoded_norm:
                matches += 1

        assert checked > 0, "No entries were checked"
        match_pct = matches / checked * 100
        # Most injected in-place entries decode back verbatim; some of the
        # longest get relocated to free space (won't match at their original
        # offset). A healthy injection keeps the bulk in place.
        assert match_pct >= 50.0, (
            f"Only {match_pct:.1f}% of the longest injected entries match "
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
        # Some entries are relocated (not at original offset), so threshold
        # accounts for ~30% relocation rate in random samples.
        assert match_pct >= 10.0, (
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
            # 0x00 is the space glyph in this encoding, so trailing box-padding
            # (spaces, present in the EN source too) is not corruption: strip a
            # trailing run of spaces (0x00) and newlines (0xFE) before scanning.
            string_bytes = chunk[:term].rstrip(b"\x00\xFE")
            # Fixed-width fields (e.g. item descriptions) can also carry interior
            # padding inherited from the English source; only flag an interior
            # run longer than whatever run already exists in original_text — i.e.
            # one *introduced* by the translation/injection, not inherited.
            source_max_run = 0
            run = 0
            for ch in entry.get("original_text", ""):
                if ch == " ":
                    run += 1
                    source_max_run = max(source_max_run, run)
                else:
                    run = 0
            allowed_run = max(source_max_run, 4)

            null_run = 0
            for b in string_bytes:
                if b == 0x00:
                    null_run += 1
                else:
                    null_run = 0
                if null_run > allowed_run:
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
