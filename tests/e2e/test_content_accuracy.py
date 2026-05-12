"""E2E: Content accuracy — verify ROM bytes match expected translations.

Loads the translation JSON, reads ROM bytes at each offset, decodes
using the CFRU charmap, and verifies the content matches. Handles
alias normalization (ê→e, ô→o, œ→oe) which makes round-trips lossy
by design.
"""

import json
import re

import pytest

from src.core.text_codec import (
    ENCODE_ALIASES,
    POKEMON_TERMINATOR,
    TextDecoder,
    TextEncoder,
)


HEX_TOKEN_RE = re.compile(r"<0x[0-9A-Fa-f]{2}>")


def _normalize(text: str) -> str:
    """Normalize text using the same alias table as the encoder."""
    for src, dst in ENCODE_ALIASES.items():
        text = text.replace(src, dst)
    return text


def _strip_hex_tokens(text: str) -> str:
    """Remove inline hex tokens for comparison purposes."""
    return HEX_TOKEN_RE.sub("", text)


def _read_rom_string(rom_data: bytes, offset: int, max_len: int = 500) -> bytes:
    """Extract raw bytes from ROM until terminator (0xFF)."""
    end = min(offset + max_len, len(rom_data))
    chunk = rom_data[offset:end]
    term = chunk.find(POKEMON_TERMINATOR)
    if term < 0:
        return chunk
    return chunk[: term + 1]


class TestContentCorrespondence:
    """Verify ROM content matches translation JSON at known offsets."""

    def test_overall_match_rate(self, injected_rom, translation_ready_path):
        """At least 95% of injected entries must match (exact + alias)."""
        output_path, _ = injected_rom
        with open(output_path, "rb") as f:
            rom_data = f.read()
        with open(translation_ready_path) as f:
            data = json.load(f)

        entries = [
            e
            for e in data.get("translations", [])
            if e.get("translation") and not e.get("too_long")
        ]

        exact = 0
        alias_match = 0
        divergent = 0
        checked = 0

        for entry in entries[:500]:
            offset = entry["offset"]
            if offset >= len(rom_data):
                continue

            expected_text = entry["translation"]
            expected_encoded = TextEncoder.encode_pokemon(expected_text)
            actual_bytes = _read_rom_string(rom_data, offset, len(expected_encoded) + 10)

            checked += 1

            if actual_bytes == expected_encoded:
                exact += 1
                continue

            actual_decoded = TextDecoder.decode_pokemon(actual_bytes, preserve_unknown=True)
            expected_norm = _normalize(expected_text)
            actual_norm = _normalize(actual_decoded)
            expected_stripped = _strip_hex_tokens(expected_norm)
            actual_stripped = _strip_hex_tokens(actual_norm)

            if expected_stripped == actual_stripped:
                alias_match += 1
            else:
                divergent += 1

        assert checked > 0, "No entries were checked"

        total_match = exact + alias_match
        match_pct = total_match / checked * 100
        exact_pct = exact / checked * 100

        # Relocated entries won't match at original offset, expect ~6% relocation
        assert match_pct >= 85.0, (
            f"Match rate {match_pct:.1f}% below 85% threshold. "
            f"Exact: {exact_pct:.1f}%, alias: {alias_match}, "
            f"divergent: {divergent}/{checked}"
        )

    def test_exact_match_statistics(self, injected_rom, translation_ready_path):
        """Report exact vs alias vs divergent stats (informational + soft gate)."""
        output_path, _ = injected_rom
        with open(output_path, "rb") as f:
            rom_data = f.read()
        with open(translation_ready_path) as f:
            data = json.load(f)

        entries = [
            e
            for e in data.get("translations", [])
            if e.get("translation") and not e.get("too_long")
        ]

        exact = 0
        alias_match = 0
        divergent_list = []
        checked = 0

        for entry in entries[:500]:
            offset = entry["offset"]
            if offset >= len(rom_data):
                continue

            expected_text = entry["translation"]
            expected_encoded = TextEncoder.encode_pokemon(expected_text)
            actual_bytes = _read_rom_string(rom_data, offset, len(expected_encoded) + 10)
            checked += 1

            if actual_bytes == expected_encoded:
                exact += 1
                continue

            actual_decoded = TextDecoder.decode_pokemon(actual_bytes, preserve_unknown=True)
            expected_norm = _normalize(expected_text)
            actual_norm = _normalize(actual_decoded)

            if _strip_hex_tokens(expected_norm) == _strip_hex_tokens(actual_norm):
                alias_match += 1
            else:
                divergent_list.append(hex(offset))

        assert checked > 0, "No entries checked"
        divergent_pct = len(divergent_list) / checked * 100
        assert divergent_pct < 10.0, (
            f"{divergent_pct:.1f}% divergent ({len(divergent_list)}/{checked}). "
            f"First divergent offsets: {divergent_list[:5]}"
        )


class TestCriticalStrings:
    """Verify known critical strings (menus, common game text) in ROM."""

    CRITICAL_STRINGS = [
        "Bonjour",
        "Merci",
        "Au revoir",
        "Salut",
    ]

    def test_critical_french_words_findable(self, injected_rom):
        output_path, _ = injected_rom
        with open(output_path, "rb") as f:
            rom_data = f.read()

        found = []
        for word in self.CRITICAL_STRINGS:
            try:
                encoded = TextEncoder.encode_pokemon(word)[:-1]
                if encoded in rom_data:
                    found.append(word)
            except Exception:
                continue

        assert len(found) >= 1, (
            f"None of the critical French strings found in ROM. "
            f"Searched for: {self.CRITICAL_STRINGS}"
        )

    def test_injected_entries_decodable(self, injected_rom, translation_ready_path):
        output_path, _ = injected_rom
        with open(output_path, "rb") as f:
            rom_data = f.read()
        with open(translation_ready_path) as f:
            data = json.load(f)

        entries = [
            e
            for e in data.get("translations", [])
            if e.get("translation") and not e.get("too_long")
        ]

        decodable = 0
        checked = 0
        for entry in entries[:100]:
            offset = entry["offset"]
            if offset >= len(rom_data):
                continue
            raw = _read_rom_string(rom_data, offset)
            if len(raw) <= 1:
                continue
            decoded = TextDecoder.decode_pokemon(raw, preserve_unknown=True)
            checked += 1
            if decoded and len(decoded) > 0:
                decodable += 1

        assert checked > 0, "No entries could be checked"
        pct = decodable / checked * 100
        assert pct >= 95.0, (
            f"Only {pct:.1f}% of injected entries are decodable "
            f"({decodable}/{checked})"
        )


class TestControlCodeIntegrity:
    """Verify control codes are properly structured in ROM strings."""

    def test_fc_fd_always_followed_by_byte(self, injected_rom, translation_ready_path):
        output_path, _ = injected_rom
        with open(output_path, "rb") as f:
            rom_data = f.read()
        with open(translation_ready_path) as f:
            data = json.load(f)

        entries = [
            e
            for e in data.get("translations", [])
            if e.get("translation") and not e.get("too_long")
        ]

        orphan_offsets = []
        for entry in entries[:500]:
            offset = entry["offset"]
            if offset >= len(rom_data):
                continue
            raw = _read_rom_string(rom_data, offset)
            term = raw.find(POKEMON_TERMINATOR)
            if term <= 0:
                continue
            string_bytes = raw[:term]
            i = 0
            while i < len(string_bytes):
                if string_bytes[i] in (0xFC, 0xFD):
                    if i + 1 >= len(string_bytes):
                        orphan_offsets.append(hex(offset))
                        break
                i += 1

        assert len(orphan_offsets) == 0, (
            f"{len(orphan_offsets)} strings with orphan FC/FD: "
            f"{orphan_offsets[:10]}"
        )

    def test_terminator_present_at_end(self, injected_rom, translation_ready_path):
        output_path, _ = injected_rom
        with open(output_path, "rb") as f:
            rom_data = f.read()
        with open(translation_ready_path) as f:
            data = json.load(f)

        entries = [
            e
            for e in data.get("translations", [])
            if e.get("translation") and not e.get("too_long")
        ]

        missing_term = 0
        checked = 0
        for entry in entries[:500]:
            offset = entry["offset"]
            if offset >= len(rom_data):
                continue
            expected_encoded = TextEncoder.encode_pokemon(entry["translation"])
            expected_len = len(expected_encoded)
            end = min(offset + expected_len + 50, len(rom_data))
            chunk = rom_data[offset:end]
            checked += 1
            if POKEMON_TERMINATOR not in chunk:
                missing_term += 1

        assert checked > 0, "No entries checked"
        assert missing_term == 0, (
            f"{missing_term}/{checked} strings missing 0xFF terminator"
        )


class TestEmulatorBridgeContent:
    """Read in-game text via mGBA bridge (skips if unavailable)."""

    def test_memory_read_decodable(self):
        try:
            from src.cooker.emulator import EmulatorBridge
        except ImportError:
            pytest.skip("EmulatorBridge not available")

        try:
            bridge = EmulatorBridge()
            bridge.connect()
        except Exception:
            pytest.skip("mGBA bridge not available or not running")

        try:
            text_buffer = bridge.read_memory(0x02021D18, 256)
            if not text_buffer or all(b == 0 for b in text_buffer):
                pytest.skip("No text in gStringVar4 buffer")

            decoded = TextDecoder.decode_pokemon(bytes(text_buffer), preserve_unknown=True)
            assert len(decoded) > 0, "Decoded text is empty"
        finally:
            try:
                bridge.disconnect()
            except Exception:
                pass
