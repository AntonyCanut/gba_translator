#!/usr/bin/env python3
"""Vérifie le bundle BPS suivi sans nécessiter de ROM source."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.core.patch_bundle import PatchBundle, PatchBundleError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", nargs="?", type=Path, default=REPO_ROOT / "patches")
    parser.add_argument("--required", nargs="*", default=[])
    args = parser.parse_args()
    bundle = args.bundle if args.bundle.is_absolute() else REPO_ROOT / args.bundle
    try:
        manifest = PatchBundle(bundle).verify(
            required_codes=set(args.required) if args.required else None
        )
    except PatchBundleError as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return 1
    print(
        f"✓ Bundle BPS build {manifest['build_number']} vérifié "
        f"({len(manifest['languages'])} langues, aucune ROM chargée)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
