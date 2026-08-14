"""Gardes des recettes de certification multilingues."""

from __future__ import annotations

import subprocess
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def _dry_run(target: str) -> str:
    """Développe une cible Make sans exécuter ses commandes."""
    result = subprocess.run(
        ["make", "--dry-run", "--always-make", target],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def _recipe(target: str) -> str:
    """Lit la recette développée par GNU Make sans lancer un sous-Make."""
    result = subprocess.run(
        ["make", "-qpRr", "-f", "Makefile"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode in {0, 1}, result.stderr
    lines = result.stdout.splitlines()
    start = lines.index(f"{target}:")
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if re.match(r"^[^#\t\s][^:]*:$", lines[index])
        ),
        len(lines),
    )
    return "\n".join(lines[start:end])


def test_de_determinism_runs_two_independent_builds() -> None:
    """Une seule construction ne peut pas certifier le déterminisme DE."""
    commands = _recipe("verify-de-determinism")

    assert commands.count("build-de BUILD_NUMBER=0") == 2
    assert "cmp -s" in commands


def test_de_audit_fails_on_every_rom_safety_gap() -> None:
    """La porte DE doit auditer contenu, collisions et consommateurs vivants."""
    commands = _dry_run("audit-de")

    assert "audit_translation_coverage.py --languages de" in commands
    assert "audit_translation_collisions.py" in commands
    assert "--fail-on-collision" in commands
    assert "audit_english_toponyms_de.py" in commands
    assert "tests/e2e/de" in commands


def test_de_certification_keeps_fr_and_it_in_the_gate() -> None:
    """Clore DE ne doit jamais sortir FR/IT de la non-régression."""
    commands = _recipe("certify-de")

    assert "verify-de-determinism" in commands
    assert "audit-de" in commands
    assert "test-vitest" in commands
    assert "test-playwright-de" in commands
    assert "verify-fr-it-nonregression" in commands


def test_de_certification_rebuilds_fr_it_before_shared_playwright() -> None:
    """Les captures multilingues ne doivent jamais lire des ROM FR/IT périmées."""
    commands = _dry_run("certify-de")

    hp_bar_test = commands.index("npm run test:e2e:hp-bar")
    assert commands.index("scripts/build_language.py it") < hp_bar_test
    assert commands.index("languages/fr/patches/hp_labels.py") < hp_bar_test
