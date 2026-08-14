#!/usr/bin/env python3
"""Crée un patch BPS vérifié à partir d'une ROM source et d'une ROM cible."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.core.bps import apply_bps_patch, create_bps_patch


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="ROM source privée")
    parser.add_argument("target", type=Path, help="ROM construite")
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()

    source = args.source.read_bytes()
    target = args.target.read_bytes()
    patch = create_bps_patch(source, target)
    if apply_bps_patch(source, patch) != target:
        print("Erreur: le round-trip BPS diffère de la cible", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patch)
    print(f"Patch BPS vérifié: {args.output} ({len(patch):,} octets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
