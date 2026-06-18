"""Tests pour scripts/check_translation_integrity.py — garde anti-régression FR.

Vérifie que la garde :
- valide le vrai combined_fr.txt du dépôt (les 13 labels carte sont français) ;
- applique bien la règle last-wins (dernière entrée gagne) ;
- détecte une régression vers une forme anglaise/périmée (le bug c7c1ede) ;
- détecte une traduction vide ou un offset absent.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_translation_integrity as cti  # noqa: E402

REAL_COMBINED = ROOT / "combined_fr.txt"


class TestRealCombinedFr:
    """La garde doit passer sur le combined_fr.txt vivant du dépôt."""

    def test_real_file_present(self):
        assert REAL_COMBINED.exists(), "combined_fr.txt introuvable à la racine du dépôt"

    def test_real_file_passes_guard(self):
        report = cti.build_report(REAL_COMBINED)
        failures = [f"0x{r.label.offset:06X} {r.label.name}: {r.reason}" for r in report.failures]
        assert report.ok, "labels carte régressés :\n" + "\n".join(failures)

    def test_thirteen_labels_protected(self):
        assert len(cti.CRITICAL_LABELS) == 13

    def test_main_returns_zero_on_real_file(self):
        assert cti.main(["--file", str(REAL_COMBINED)]) == 0


class TestLastWinsResolution:
    """L'offset présent en double : la dernière occurrence l'emporte (comme le build)."""

    def test_last_entry_wins(self, tmp_path: Path):
        target = tmp_path / "combined.txt"
        target.write_text(
            "0x720E74: Ville de Fallshore\n"  # ancienne valeur (haut de fichier)
            "0x720e74: Fallshore\n",          # valeur vivante (bloc minuscule)
            encoding="utf-8",
        )
        mapping, total = cti.load_last_wins(target)
        assert total == 2
        assert mapping[0x720E74] == "Fallshore"


class TestRegressionDetection:
    """La garde doit échouer si un label régresse vers sa forme anglaise/périmée."""

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
        # Reproduit c7c1ede : Fallshore réécrit en « Ville de Fallshore ».
        path = self._write_all_french(tmp_path / "bad.txt", {0x720E74: "Ville de Fallshore"})
        report = cti.build_report(path)
        assert not report.ok
        assert report.failures[0].label.offset == 0x720E74
        assert "interdite" in report.failures[0].reason

    def test_regression_case_insensitive(self, tmp_path: Path):
        path = self._write_all_french(tmp_path / "bad.txt", {0x7214E8: "glimmer island"})
        assert not cti.build_report(path).ok

    def test_empty_translation_fails(self, tmp_path: Path):
        path = self._write_all_french(tmp_path / "empty.txt", {0xB535C8: ""})
        report = cti.build_report(path)
        assert not report.ok
        assert "vide" in report.failures[0].reason

    def test_missing_offset_fails(self, tmp_path: Path):
        target = tmp_path / "partial.txt"
        target.write_text("0xB500A0: Bourg Gurun\n", encoding="utf-8")
        report = cti.build_report(target)
        assert not report.ok
        absent = [r for r in report.failures if "absent" in r.reason]
        assert len(absent) == 12  # 13 labels − 1 présent

    def test_main_returns_one_on_regression(self, tmp_path: Path):
        path = self._write_all_french(tmp_path / "bad.txt", {0x720E74: "Ville de Fallshore"})
        assert cti.main(["--file", str(path)]) == 1
