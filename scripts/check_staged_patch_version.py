#!/usr/bin/env python3
"""Refuse un asset BPS staged qui réutilise un numéro de build publié."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Sequence


MANIFEST_PATH = "patches/RELEASE_MANIFEST.json"
PATCH_PATHSPEC = ":(glob)patches/pokemon_unbound_*.bps"


class PatchVersionError(RuntimeError):
    """Signale un bundle staged qui ne peut pas créer une version immuable."""


def _git(repo: Path, args: Sequence[str]) -> str:
    """Retourne la sortie Git ou lève une erreur concise."""

    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        message = result.stderr.strip() or "commande Git en échec"
        raise PatchVersionError(message)
    return result.stdout


def _build_number(manifest_text: str, source: str) -> int:
    """Extrait un numéro de build entier strictement positif."""

    try:
        value = json.loads(manifest_text)["build_number"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise PatchVersionError(f"{source}: build_number absent ou invalide") from error
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PatchVersionError(f"{source}: build_number doit être un entier positif")
    return value


def validate_staged_patch_version(repo: Path) -> tuple[int, int] | None:
    """Vérifie qu'un patch modifié incrémente le build par rapport à ``HEAD``."""

    changed_patches = _git(
        repo,
        [
            "diff",
            "--cached",
            "--name-only",
            "--diff-filter=ACMRD",
            "--",
            PATCH_PATHSPEC,
        ],
    ).splitlines()
    if not changed_patches:
        return None

    previous = _build_number(
        _git(repo, ["show", f"HEAD:{MANIFEST_PATH}"]),
        f"{MANIFEST_PATH} dans HEAD",
    )
    staged = _build_number(
        _git(repo, ["show", f":{MANIFEST_PATH}"]),
        f"{MANIFEST_PATH} dans l’index",
    )
    if staged <= previous:
        raise PatchVersionError(
            f"Asset BPS modifié avec build {staged} ; le nouveau build doit être "
            f"strictement supérieur à {previous}."
        )
    return previous, staged


def main() -> int:
    """Valide le bundle staged et affiche un diagnostic exploitable par le hook."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()

    try:
        versions = validate_staged_patch_version(args.repo.resolve())
    except PatchVersionError as error:
        print(f"❌ Publication BPS bloquée : {error}", file=sys.stderr)
        return 1

    if versions is not None:
        previous, staged = versions
        print(f"✓ Bundle BPS staged : build {previous} → {staged}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
