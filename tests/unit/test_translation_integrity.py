"""Tests for scripts/check_translation_integrity.py — FR anti-regression guard.

Verifies that the guard:
- validates the real combined_fr.txt in the repo (all protected labels are French);
- correctly applies the last-wins rule (last entry wins);
- detects a regression to an English/stale form (bug c7c1ede);
- detects an empty translation or a missing offset.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_translation_integrity as cti  # noqa: E402

REAL_COMBINED = ROOT / "languages/fr/combined_fr.txt"


class TestRealCombinedFr:
    """The guard must pass on the live combined_fr.txt in the repo."""

    def test_real_file_present(self):
        assert REAL_COMBINED.exists(), "combined_fr.txt not found at repo root"

    def test_real_file_passes_guard(self):
        report = cti.build_report(REAL_COMBINED)
        failures = [f"0x{r.label.offset:06X} {r.label.name}: {r.reason}" for r in report.failures]
        assert report.ok, "regressed map labels:\n" + "\n".join(failures)

    def test_protected_label_count(self):
        # 13 world-map labels (B-52) + 0x1F0F842 couleur ceinture/bottes (9ad0fee)
        # + 0x83008C/0x96CC1C réaction Méga-Cuff (dc84690f)
        # + 2 Hoopa dialogues (0x7D5083/0x1F3A9F2, Pattern C 8fe7dddb0).
        assert len(cti.CRITICAL_LABELS) == 18

    def test_main_returns_zero_on_real_file(self):
        assert cti.main(["--file", str(REAL_COMBINED)]) == 0


class TestLastWinsResolution:
    """When an offset appears twice, the last occurrence wins (same as the build)."""

    def test_last_entry_wins(self, tmp_path: Path):
        target = tmp_path / "combined.txt"
        target.write_text(
            "0x720E74: Ville de Fallshore\n"  # old value (top of file)
            "0x720e74: Fallshore\n",          # live value (lowercase hex block)
            encoding="utf-8",
        )
        mapping, total = cti.load_last_wins(target)
        assert total == 2
        assert mapping[0x720E74] == "Fallshore"


class TestRegressionDetection:
    """The guard must fail when a label regresses to its English/stale form."""

    def _write_all_french(self, path: Path, overrides: dict[int, str] | None = None) -> Path:
        overrides = overrides or {}
        lines = []
        for label in cti.CRITICAL_LABELS:
            value = overrides.get(label.offset, label.expected_fr)
            lines.append(f"0x{label.offset:06X}: {value}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def test_all_french_passes(self, tmp_path: Path):
        path = self._write_all_french(tmp_path / "ok.txt")
        assert cti.build_report(path).ok

    def test_regression_to_english_fails(self, tmp_path: Path):
        # Reproduces c7c1ede: Fallshore rewritten as « Ville de Fallshore ».
        path = self._write_all_french(tmp_path / "bad.txt", {0x720E74: "Ville de Fallshore"})
        report = cti.build_report(path)
        assert not report.ok
        assert report.failures[0].label.offset == 0x720E74
        assert "forbidden" in report.failures[0].reason

    def test_regression_case_insensitive(self, tmp_path: Path):
        path = self._write_all_french(tmp_path / "bad.txt", {0x7214E8: "glimmer island"})
        assert not cti.build_report(path).ok

    def test_empty_translation_fails(self, tmp_path: Path):
        path = self._write_all_french(tmp_path / "empty.txt", {0xB535C8: ""})
        report = cti.build_report(path)
        assert not report.ok
        assert "empty" in report.failures[0].reason

    def test_missing_offset_fails(self, tmp_path: Path):
        target = tmp_path / "partial.txt"
        target.write_text("0xB500A0: Gurenbourg\n", encoding="utf-8")
        report = cti.build_report(target)
        assert not report.ok
        absent = [r for r in report.failures if "absent" in r.reason]
        assert len(absent) == len(cti.CRITICAL_LABELS) - 1  # all labels − 1 present

    def test_main_returns_one_on_regression(self, tmp_path: Path):
        path = self._write_all_french(tmp_path / "bad.txt", {0x720E74: "Ville de Fallshore"})
        assert cti.main(["--file", str(path)]) == 1
