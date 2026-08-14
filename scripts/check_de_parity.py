#!/usr/bin/env python3
"""Vérifie que chaque traitement localisable FR possède une décision DE."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.i18n.de_parity import DeParityManifest


def main() -> int:
    """Valide la matrice versionnée et affiche les écarts actionnables."""
    manifest = DeParityManifest.load(ROOT / "languages/de/parity.yaml")
    failures = manifest.validate(ROOT)
    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 1
    print("[OK] Matrice FR→DE complète et cohérente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
