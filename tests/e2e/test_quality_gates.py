"""E2E: Quality gate non-regression tests.

Verifies that translation quality maintains or exceeds a stored baseline.
Checks quality score distribution, FD control code preservation,
and overall BAD entry rate.
"""

import json
import pathlib
import re

import pytest

from src.core.text_codec import TextEncoder

BASELINE_PATH = pathlib.Path(__file__).parent / "data" / "quality_baseline.json"

HEX_TOKEN_RE = re.compile(r"<0x[0-9A-Fa-f]{2}>")
FRENCH_PATTERN = re.compile(r"[àçèéâîù]|l'|d'|qu'|c'est|n'est|je |tu |il |nous ")


def _load_baseline():
    if not BASELINE_PATH.exists():
        pytest.skip("quality_baseline.json not found")
    with open(BASELINE_PATH) as f:
        return json.load(f)


def _classify_entry(entry):
    """Classify a translation entry as GOOD, ACCEPTABLE, or BAD."""
    orig = entry.get("original_text", "")
    trans = entry.get("translation", "")

    if not trans:
        return "BAD"

    too_long = entry.get("too_long", False)
    identical = orig.strip() == trans.strip()

    if too_long or identical:
        return "ACCEPTABLE"

    has_french = bool(FRENCH_PATTERN.search(trans))
    if has_french or len(trans) > 3:
        return "GOOD"

    return "ACCEPTABLE"


class TestQualityBaseline:
    """Quality score must meet or exceed baseline thresholds."""

    def test_good_acceptable_above_baseline(self, translation_ready_path):
        baseline = _load_baseline()
        with open(translation_ready_path) as f:
            data = json.load(f)

        entries = data.get("translations", [])
        if not entries:
            pytest.skip("No translation entries")

        classifications = [_classify_entry(e) for e in entries]
        good_accept = sum(1 for c in classifications if c in ("GOOD", "ACCEPTABLE"))
        pct = good_accept / len(entries) * 100

        threshold = baseline["min_good_acceptable_pct"]
        assert pct >= threshold, (
            f"GOOD+ACCEPTABLE rate {pct:.1f}% below baseline {threshold}% "
            f"({good_accept}/{len(entries)})"
        )

    def test_bad_rate_below_threshold(self, translation_ready_path):
        baseline = _load_baseline()
        with open(translation_ready_path) as f:
            data = json.load(f)

        entries = data.get("translations", [])
        if not entries:
            pytest.skip("No translation entries")

        bad_count = sum(1 for e in entries if _classify_entry(e) == "BAD")
        bad_pct = bad_count / len(entries) * 100

        threshold = baseline["max_bad_pct"]
        assert bad_pct <= threshold, (
            f"BAD rate {bad_pct:.1f}% exceeds threshold {threshold}% "
            f"({bad_count}/{len(entries)})"
        )


class TestFDControlCodePreservation:
    """FD control codes must be preserved from source to translation."""

    def test_fd_tokens_preserved_in_translations(self, translation_ready_path):
        with open(translation_ready_path) as f:
            data = json.load(f)

        entries = data.get("translations", [])
        total_with_fd = 0
        preserved = 0

        for entry in entries:
            orig = entry.get("original_text", "")
            trans = entry.get("translation", "")
            if not trans:
                continue

            fd_src = sorted(
                t for t in HEX_TOKEN_RE.findall(orig) if "FD" in t.upper()
            )
            if not fd_src:
                continue

            total_with_fd += 1
            fd_tgt = sorted(
                t for t in HEX_TOKEN_RE.findall(trans) if "FD" in t.upper()
            )
            if fd_src == fd_tgt:
                preserved += 1

        if total_with_fd == 0:
            pytest.skip("No entries with FD tokens")

        pct = preserved / total_with_fd * 100
        assert pct >= 60.0, (
            f"FD preservation rate {pct:.1f}% too low "
            f"({preserved}/{total_with_fd}). "
            f"FD tokens in translations must match source."
        )

    def test_fd_byte_sequences_valid_in_rom(
        self, injected_rom, translation_ready_path
    ):
        output_path, _ = injected_rom
        with open(output_path, "rb") as f:
            rom_data = f.read()
        with open(translation_ready_path) as f:
            data = json.load(f)

        entries = [
            e for e in data.get("translations", [])
            if e.get("translation")
            and not e.get("too_long")
            and "<0xFD>" in e.get("original_text", "").upper()
        ]

        invalid_fd = 0
        checked = 0
        for entry in entries[:200]:
            offset = entry["offset"]
            if offset >= len(rom_data):
                continue
            end = min(offset + 500, len(rom_data))
            chunk = rom_data[offset:end]
            term = chunk.find(0xFF)
            if term <= 0:
                continue
            string_bytes = chunk[:term]
            checked += 1

            i = 0
            while i < len(string_bytes):
                if string_bytes[i] == 0xFD:
                    if i + 1 >= len(string_bytes):
                        invalid_fd += 1
                        break
                i += 1

        if checked == 0:
            pytest.skip("No FD entries could be checked in ROM")

        assert invalid_fd == 0, (
            f"{invalid_fd}/{checked} ROM strings have truncated FD sequences"
        )


class TestTranslatedPercentage:
    """Translation coverage must meet baseline."""

    def test_translation_coverage_above_baseline(self, translation_ready_path):
        baseline = _load_baseline()
        with open(translation_ready_path) as f:
            data = json.load(f)

        entries = data.get("translations", [])
        if not entries:
            pytest.skip("No entries")

        translated = sum(1 for e in entries if e.get("translation"))
        pct = translated / len(entries) * 100
        threshold = baseline["min_translated_pct"]

        assert pct >= threshold, (
            f"Translation coverage {pct:.1f}% below baseline {threshold}% "
            f"({translated}/{len(entries)})"
        )

    def test_french_markers_above_baseline(self, translation_ready_path):
        baseline = _load_baseline()
        with open(translation_ready_path) as f:
            data = json.load(f)

        entries = data.get("translations", [])
        french_count = 0
        total = 0

        for entry in entries:
            text = entry.get("translation", "")
            if not text or len(text) < 5:
                continue
            total += 1
            if FRENCH_PATTERN.search(text):
                french_count += 1

        if total == 0:
            pytest.skip("No entries to check")

        pct = french_count / total * 100
        threshold = baseline["min_french_markers_pct"]
        assert pct >= threshold, (
            f"French marker rate {pct:.1f}% below baseline {threshold}% "
            f"({french_count}/{total})"
        )


class TestEncodingQuality:
    """Encoded translation quality checks."""

    def test_no_encoding_failures(self, translation_ready_path):
        with open(translation_ready_path) as f:
            data = json.load(f)

        failures = []
        for entry in data.get("translations", [])[:2000]:
            text = entry.get("translation", "")
            if not text:
                continue
            try:
                encoded = TextEncoder.encode_pokemon(text)
                assert encoded[-1] == 0xFF
            except Exception as exc:
                failures.append(
                    f"{hex(entry.get('offset', 0))}: {str(exc)[:60]}"
                )

        assert len(failures) == 0, (
            f"{len(failures)} encoding failures: {failures[:5]}"
        )
