#!/usr/bin/env python3
"""Bloque les débordements FR/IT dans les commits d'un ticket DE."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.i18n.de_parity import (
    ChangedPath,
    DeParityManifest,
    changed_since,
    current_branch,
    staged_changes,
    validate_de_scope,
)


def parse_args() -> argparse.Namespace:
    """Déclare les sources de diff utilisables en hook comme en CI."""
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--base-ref", help="Comparer base-ref...HEAD")
    group.add_argument("--path", action="append", default=[], help="Chemin à contrôler")
    parser.add_argument("--staged", action="store_true", help="Contrôler l'index Git")
    parser.add_argument("--branch", help="Nom de branche explicite pour la CI")
    return parser.parse_args()


def main() -> int:
    """Valide le périmètre DE et retourne un code non nul au moindre débordement."""
    args = parse_args()
    manifest = DeParityManifest.load(ROOT / "languages/de/parity.yaml")
    branch = args.branch or current_branch(ROOT)
    if args.path:
        changes = [ChangedPath(status="M", path=path) for path in args.path]
    elif args.base_ref:
        changes = changed_since(ROOT, args.base_ref)
    else:
        changes = staged_changes(ROOT)
    failures = validate_de_scope(changes, branch, manifest.scope)
    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 1
    print("[OK] Périmètre du ticket DE respecté.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
