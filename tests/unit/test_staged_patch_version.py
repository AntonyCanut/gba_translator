"""Gardes de régression du numéro de build des patchs suivis."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts" / "check_staged_patch_version.py"
HOOK = ROOT / ".githooks" / "pre-commit"


def _clean_git_env() -> dict[str, str]:
    """Retire le contexte du hook parent pour isoler le dépôt synthétique."""

    return {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }


def _git(repo: Path, *args: str) -> None:
    """Exécute une commande Git dans le dépôt de test."""

    subprocess.run(
        ["git", *args],
        cwd=repo,
        env=_clean_git_env(),
        check=True,
        capture_output=True,
    )


def _write_manifest(repo: Path, build_number: int, marker: str) -> None:
    """Écrit un manifeste minimal dont le marqueur force un diff staged."""

    manifest = {"build_number": build_number, "marker": marker}
    (repo / "patches" / "RELEASE_MANIFEST.json").write_text(
        json.dumps(manifest) + "\n", encoding="utf-8"
    )


def _release_repo(tmp_path: Path) -> Path:
    """Crée un dépôt avec un bundle build 43 déjà committé."""

    repo = tmp_path / "repo"
    patches = repo / "patches"
    patches.mkdir(parents=True)
    (patches / "pokemon_unbound_fr.bps").write_bytes(b"ancienne version")
    _write_manifest(repo, 43, "ancienne version")
    _git(repo, "init", "-q")
    _git(repo, "add", "patches")
    _git(
        repo,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-q",
        "-m",
        "bundle initial",
    )
    return repo


def _stage_patch(repo: Path, build_number: int) -> None:
    """Stage un nouvel asset FR et le manifeste correspondant."""

    (repo / "patches" / "pokemon_unbound_fr.bps").write_bytes(b"nouvelle version")
    _write_manifest(repo, build_number, "nouvelle version")
    _git(repo, "add", "patches")


def _run_guard(repo: Path) -> subprocess.CompletedProcess[str]:
    """Exécute la garde réelle contre le dépôt synthétique."""

    return subprocess.run(
        ["python3", str(GUARD), "--repo", str(repo)],
        cwd=ROOT,
        env=_clean_git_env(),
        capture_output=True,
        text=True,
        check=False,
    )


def test_modified_patch_requires_a_higher_build_number(tmp_path: Path) -> None:
    """Réutiliser 43 pour un asset différent doit échouer avant GitHub Actions."""

    # Arrange
    repo = _release_repo(tmp_path)
    _stage_patch(repo, 43)

    # Act
    result = _run_guard(repo)

    # Assert
    assert result.returncode == 1
    assert "build 43" in result.stderr
    assert "strictement supérieur" in result.stderr


def test_modified_patch_accepts_a_higher_build_number(tmp_path: Path) -> None:
    """Un nouveau bundle numéroté peut remplacer les assets suivis."""

    # Arrange
    repo = _release_repo(tmp_path)
    _stage_patch(repo, 44)

    # Act
    result = _run_guard(repo)

    # Assert
    assert result.returncode == 0, result.stderr
    assert "43 → 44" in result.stdout


def test_commit_without_patch_change_skips_the_version_guard(tmp_path: Path) -> None:
    """La garde ne doit pas imposer un bump aux commits sans asset BPS modifié."""

    # Arrange
    repo = _release_repo(tmp_path)
    (repo / "README.md").write_text("documentation\n", encoding="utf-8")
    _git(repo, "add", "README.md")

    # Act
    result = _run_guard(repo)

    # Assert
    assert result.returncode == 0, result.stderr


def test_pre_commit_runs_the_patch_version_guard(tmp_path: Path) -> None:
    """Le hook doit exécuter la garde avant les tests de publication."""

    # Arrange
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    command_log = tmp_path / "commands.log"
    for command in ("python3", "make", "npm"):
        executable = fake_bin / command
        executable.write_text(
            "#!/bin/sh\nprintf '%s %s\\n' "
            f"'{command}' \"$*\" >> \"$COMMAND_LOG\"\n",
            encoding="utf-8",
        )
        executable.chmod(0o755)
    env = os.environ | {
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "COMMAND_LOG": str(command_log),
    }

    # Act
    result = subprocess.run(
        ["sh", str(HOOK)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    # Assert
    assert result.returncode == 0, result.stderr
    calls = command_log.read_text(encoding="utf-8").splitlines()
    guard = "python3 scripts/check_staged_patch_version.py"
    release_tests = "python3 -m pytest -q tests/unit/test_release_workflow.py"
    assert guard in calls
    assert calls.index(guard) < calls.index(release_tests)
