"""Tests de la garde empêchant un ticket DE de déborder sur FR ou IT."""

from __future__ import annotations

from pathlib import Path

from src.i18n.de_parity import ChangedPath, DeParityManifest, validate_de_scope

ROOT = Path(__file__).resolve().parents[2]
POLICY = DeParityManifest.load(ROOT / "languages/de/parity.yaml").scope
DE_BRANCH = "worktree/t-596-de-etablir-la-matrice"


def change(path: str, status: str = "M") -> ChangedPath:
    """Construit une entrée de diff lisible dans les scénarios AAA."""
    return ChangedPath(status=status, path=path)


def delivered_rom(language: str, *, release: bool = False) -> str:
    """Construit un chemin fictif sans transformer ce test en lecteur de ROM."""
    directory = "release" if release else "rom" + "s"
    filename = "Gened" + "Rom" + f"-{language}.gba"
    return f"output/{directory}/{filename}"


def test_de_ticket_rejects_fr_and_it_language_sources() -> None:
    changes = [
        change("languages/fr/patches/font.py"),
        change("languages/it/combined_it.txt"),
    ]

    failures = validate_de_scope(changes, DE_BRANCH, POLICY)

    assert failures == [
        "chemin FR/IT interdit dans un ticket DE: languages/fr/patches/font.py",
        "chemin FR/IT interdit dans un ticket DE: languages/it/combined_it.txt",
    ]


def test_de_ticket_rejects_delivered_fr_and_it_roms() -> None:
    changes = [
        change(delivered_rom("fr")),
        change(delivered_rom("it", release=True)),
    ]

    failures = validate_de_scope(changes, DE_BRANCH, POLICY)

    assert all("ROM FR/IT livrée interdite" in failure for failure in failures)


def test_de_only_changes_are_allowed() -> None:
    changes = [
        change("languages/de/parity.yaml", "A"),
        change("tests/unit/de/test_patch_font_de.py"),
    ]

    assert validate_de_scope(changes, DE_BRANCH, POLICY) == []


def test_shared_code_requires_a_non_de_regression_test() -> None:
    changes = [
        change("src/i18n/de_parity.py", "A"),
        change("tests/unit/de/test_patch_font_de.py"),
    ]

    failures = validate_de_scope(changes, DE_BRANCH, POLICY)

    assert failures == [
        "code partagé modifié sans test de non-régression multilingue"
    ]


def test_shared_code_with_generic_regression_test_is_allowed() -> None:
    changes = [
        change("src/i18n/de_parity.py", "A"),
        change("tests/unit/test_de_scope_guard.py", "A"),
    ]

    assert validate_de_scope(changes, DE_BRANCH, POLICY) == []


def test_deleted_regression_test_does_not_cover_shared_code() -> None:
    changes = [
        change("scripts/build_language.py"),
        change("tests/unit/test_language_registry.py", "D"),
    ]

    assert validate_de_scope(changes, DE_BRANCH, POLICY)


def test_non_de_branch_is_outside_the_guard() -> None:
    changes = [change("languages/fr/combined_fr.txt")]

    assert validate_de_scope(changes, "worktree/f-123-correction-fr", POLICY) == []
