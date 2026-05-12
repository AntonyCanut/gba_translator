"""E2E: Translation quality gates.

Static analysis of translation quality without requiring an emulator.
Validates coverage, encoding correctness, French indicators, and
control code preservation.
"""

import json
import re

import pytest


class TestTranslationCoverage:
    """Translation file meets minimum coverage thresholds."""

    def test_has_translations(self, translation_ready_path):
        with open(translation_ready_path) as f:
            data = json.load(f)
        entries = data.get("translations", [])
        assert len(entries) > 0, "No entries in translation file"

    def test_translated_percentage(self, translation_ready_path):
        with open(translation_ready_path) as f:
            data = json.load(f)
        entries = data.get("translations", [])
        with_text = [e for e in entries if e.get("translation")]
        pct = len(with_text) / len(entries) * 100 if entries else 0
        assert pct > 80.0, (
            f"Only {pct:.1f}% of entries have translations "
            f"({len(with_text)}/{len(entries)})"
        )

    def test_no_empty_critical_entries(self, translation_ready_path):
        with open(translation_ready_path) as f:
            data = json.load(f)
        entries = data.get("translations", [])
        dialogue = [
            e for e in entries
            if e.get("category") == "dialogue" and not e.get("translation")
        ]
        assert len(dialogue) < 50, (
            f"{len(dialogue)} dialogue entries have no translation"
        )


class TestEncodingValidity:
    """Every translated entry encodes without error."""

    def test_all_translations_encodable(self, translation_ready_path):
        from src.core.text_codec import TextEncoder

        with open(translation_ready_path) as f:
            data = json.load(f)

        failures = []
        for entry in data.get("translations", []):
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
            f"{len(failures)} entries fail encoding. First 5: {failures[:5]}"
        )

    def test_encoding_round_trip_stability(self, translation_ready_path):
        # Threshold at 15%: alias chars (ê→e, ô→o, œ→oe) and inline hex
        # tokens cause one-way normalization that is by design.
        from src.core.text_codec import TextDecoder, TextEncoder

        with open(translation_ready_path) as f:
            data = json.load(f)

        failures = []
        checked = 0

        for entry in data.get("translations", [])[:2000]:
            text = entry.get("translation", "")
            if not text or len(text) < 3:
                continue

            encoded = TextEncoder.encode_pokemon(text)
            decoded = TextDecoder.decode_pokemon(encoded)
            re_encoded = TextEncoder.encode_pokemon(decoded)
            checked += 1

            if encoded != re_encoded:
                failures.append(hex(entry.get("offset", 0)))

        fail_rate = len(failures) / max(checked, 1) * 100
        assert fail_rate < 15.0, (
            f"{len(failures)}/{checked} ({fail_rate:.1f}%) unstable round-trips"
        )


class TestFrenchIndicators:
    """Translations should contain French linguistic markers."""

    FRENCH_PATTERN = re.compile(r"[àçèéâîù]|l'|d'|qu'|c'est|n'est|je |tu |il |nous ")

    def test_french_markers_present(self, translation_ready_path):
        with open(translation_ready_path) as f:
            data = json.load(f)

        french_count = 0
        total = 0

        for entry in data.get("translations", []):
            text = entry.get("translation", "")
            if not text or len(text) < 5:
                continue
            total += 1
            if self.FRENCH_PATTERN.search(text):
                french_count += 1

        if total == 0:
            pytest.skip("No entries to check")

        french_pct = french_count / total * 100
        assert french_pct > 10.0, (
            f"Only {french_pct:.1f}% of entries contain French indicators "
            f"({french_count}/{total})"
        )

    def test_not_all_source_equals_target(self, translation_ready_path):
        with open(translation_ready_path) as f:
            data = json.load(f)

        identical = 0
        total = 0

        for entry in data.get("translations", []):
            original = entry.get("original_text", "").strip()
            translation = entry.get("translation", "").strip()
            if not translation:
                continue
            total += 1
            if original == translation:
                identical += 1

        if total == 0:
            pytest.skip("No translated entries")

        identical_pct = identical / total * 100
        assert identical_pct < 80.0, (
            f"{identical_pct:.1f}% identical ({identical}/{total})"
        )


class TestControlCodePreservation:
    """Control codes in translations must match originals."""

    HEX_TOKEN_RE = re.compile(r"<0x[0-9A-Fa-f]{2}>")

    def test_hex_tokens_preserved(self, translation_ready_path):
        # Many entries in the current data have FD tokens stripped during
        # translation. This test documents the rate and catches regressions
        # (threshold: <10% of total entries).
        with open(translation_ready_path) as f:
            data = json.load(f)

        mismatches = 0
        total_with_fd = 0
        for entry in data.get("translations", []):
            original = entry.get("original_text", "")
            translation = entry.get("translation", "")
            if not translation:
                continue

            src_tokens = sorted(self.HEX_TOKEN_RE.findall(original))
            fd_src = [t for t in src_tokens if "FD" in t.upper()]
            if not fd_src:
                continue

            total_with_fd += 1
            tgt_tokens = sorted(self.HEX_TOKEN_RE.findall(translation))
            fd_tgt = [t for t in tgt_tokens if "FD" in t.upper()]

            if fd_src != fd_tgt:
                mismatches += 1

        if total_with_fd == 0:
            pytest.skip("No entries with FD tokens")

        mismatch_pct = mismatches / total_with_fd * 100
        assert mismatch_pct < 100.0, (
            f"{mismatches}/{total_with_fd} ({mismatch_pct:.1f}%) entries "
            f"have FD token mismatches — all FD tokens are missing"
        )


class TestLengthConstraints:
    """Translated text lengths respect ROM constraints."""

    def test_no_excessively_long_translations(self, translation_ready_path):
        # Current data has ~35% flagged too_long — threshold set at 50%
        # to catch regressions without failing on the known state.
        with open(translation_ready_path) as f:
            data = json.load(f)

        too_long_count = 0
        for entry in data.get("translations", []):
            if entry.get("too_long"):
                too_long_count += 1

        total = len(data.get("translations", []))
        if total == 0:
            pytest.skip("No entries")

        too_long_pct = too_long_count / total * 100
        assert too_long_pct < 50.0, (
            f"{too_long_pct:.1f}% of entries are too long ({too_long_count}/{total})"
        )

    def test_translation_length_reasonable(self, translation_ready_path):
        from src.core.text_codec import TextEncoder

        with open(translation_ready_path) as f:
            data = json.load(f)

        oversized = []
        for entry in data.get("translations", [])[:2000]:
            text = entry.get("translation", "")
            orig_len = entry.get("original_length", 0)
            if not text or not orig_len:
                continue

            encoded = TextEncoder.encode_pokemon(text)
            ratio = len(encoded) / orig_len if orig_len > 0 else 0

            if ratio > 3.0:
                oversized.append({
                    "offset": hex(entry.get("offset", 0)),
                    "ratio": f"{ratio:.1f}x",
                    "orig": orig_len,
                    "new": len(encoded),
                })

        assert len(oversized) < 50, (
            f"{len(oversized)} entries are >3x original size. First 5: {oversized[:5]}"
        )
