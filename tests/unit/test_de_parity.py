"""Gardes exécutables de la matrice de parité FR vers DE."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from src.i18n.de_parity import ALLOWED_CLASSIFICATIONS, DeParityManifest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "languages/de/parity.yaml"


def test_current_de_parity_manifest_covers_the_repository() -> None:
    """Une étape, un patch ou un asset FR ajouté sans décision DE doit casser."""
    manifest = DeParityManifest.load(MANIFEST_PATH)

    failures = manifest.validate(ROOT)

    assert failures == []


def test_manifest_lists_every_fr_patch_and_asset_exactly_once() -> None:
    """Retirer une ligne de matrice ne doit jamais laisser l'inventaire vert."""
    manifest = DeParityManifest.load(MANIFEST_PATH)
    truncated = replace(manifest, patches=manifest.patches[1:])

    failures = truncated.validate(ROOT)

    assert any("patch FR absent de la matrice" in failure for failure in failures)


def test_manifest_lists_every_localized_fr_test_exactly_once() -> None:
    """Un nouveau test FR doit recevoir un équivalent DE ou une exclusion."""
    manifest = DeParityManifest.load(MANIFEST_PATH)
    truncated = replace(manifest, rom_tests=manifest.rom_tests[1:])

    failures = truncated.validate(ROOT)

    assert any("test FR absent de la matrice" in failure for failure in failures)


def test_manifest_accounts_for_de_only_build_steps_and_tests() -> None:
    """Les traitements déjà présents uniquement en DE ne doivent pas être recréés."""
    manifest = DeParityManifest.load(MANIFEST_PATH)
    without_step = replace(manifest, de_only_build_steps=())
    without_test = replace(manifest, de_only_rom_tests=())

    step_failures = without_step.validate(ROOT)
    test_failures = without_test.validate(ROOT)

    assert any("étape propre à DE absente de la matrice" in failure for failure in step_failures)
    assert any("test propre à DE absent de la matrice" in failure for failure in test_failures)


def test_manifest_includes_non_python_and_long_language_test_names() -> None:
    """Playwright et les alias `german`/`french` appartiennent aussi à l'inventaire."""
    manifest = DeParityManifest.load(MANIFEST_PATH)
    fr_sources = {entry.source for entry in manifest.rom_tests}
    de_sources = {entry.source for entry in manifest.de_only_rom_tests}

    assert "tests/unit/test_audit_english_rom_french_leak.py" in fr_sources
    assert "tests/e2e-playwright/german-translation.spec.ts" in de_sources


def test_manifest_preserves_de_graphics_coverage_landed_in_parallel() -> None:
    """Le rebase ne doit pas faire recréer les traitements graphiques DE existants."""
    manifest = DeParityManifest.load(MANIFEST_PATH)
    de_steps = {entry.source for entry in manifest.de_only_build_steps}
    de_tests = {entry.source for entry in manifest.de_only_rom_tests}

    assert {"screen_graphics", "summary_stat_labels"} <= de_steps
    assert {
        "tests/unit/de/test_interface_labels_de.py",
        "tests/unit/de/test_screen_graphics_de.py",
        "tests/unit/de/test_summary_stat_labels_de.py",
    } <= de_tests


def test_every_required_gap_has_a_supported_classification() -> None:
    """Une catégorie libre masquerait le type de travail restant à porter."""
    manifest = DeParityManifest.load(MANIFEST_PATH)
    entries = (
        *manifest.build_steps,
        *manifest.de_only_build_steps,
        *manifest.patches,
        *manifest.assets,
        *manifest.rom_tests,
        *manifest.de_only_rom_tests,
    )

    assert {entry.classification for entry in entries} <= ALLOWED_CLASSIFICATIONS
    assert ALLOWED_CLASSIFICATIONS == {
        "pointer_text",
        "fixed_table",
        "asm_patch",
        "lz77_graphic",
        "font",
        "format_control",
        "rom_test",
    }


def test_exclusion_without_justification_is_rejected() -> None:
    """Une exclusion vide ne doit pas contourner la garde de parité."""
    manifest = DeParityManifest.load(MANIFEST_PATH)
    excluded = next(entry for entry in manifest.assets if entry.status == "excluded")
    invalid = replace(excluded, reason="")
    entries = tuple(invalid if entry is excluded else entry for entry in manifest.assets)

    failures = replace(manifest, assets=entries).validate(ROOT)

    assert any("exclusion sans justification" in failure for failure in failures)


def test_shared_build_step_must_still_exist_in_de_descriptor() -> None:
    """Un mécanisme partagé retiré de la recette DE ne constitue plus une parité."""
    manifest = DeParityManifest.load(MANIFEST_PATH)
    shared = next(entry for entry in manifest.build_steps if entry.status == "shared")
    invalid = replace(shared, target="missing_shared_step")
    entries = tuple(invalid if entry is shared else entry for entry in manifest.build_steps)

    failures = replace(manifest, build_steps=entries).validate(ROOT)

    assert any("étape DE déclarée absente" in failure for failure in failures)


def test_equivalent_descriptor_field_must_exist_in_de_descriptor() -> None:
    """Une clé cible mal orthographiée ne doit pas valider la comparaison YAML."""
    manifest = DeParityManifest.load(MANIFEST_PATH)
    field = next(
        entry for entry in manifest.descriptor_fields if entry.status == "equivalent"
    )
    invalid = replace(field, target="missing_descriptor_key")
    entries = tuple(
        invalid if entry is field else entry for entry in manifest.descriptor_fields
    )

    failures = replace(manifest, descriptor_fields=entries).validate(ROOT)

    assert any("champ DE déclaré absent" in failure for failure in failures)


@pytest.mark.parametrize("script", ["check_de_parity.py", "check_de_scope.py"])
def test_guard_cli_runs_directly_from_the_repository(script: str) -> None:
    """Les cibles Makefile exécutent les scripts, pas leurs modules importés."""
    result = subprocess.run(
        [sys.executable, f"scripts/{script}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
