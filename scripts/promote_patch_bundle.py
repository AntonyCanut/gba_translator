#!/usr/bin/env python3
"""Promeut un bundle BPS local vérifié vers le dossier suivi patches/."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.core.patch_bundle import PatchBundle, PatchBundleError
from src.i18n import load_registry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=REPO_ROOT / "output/release",
    )
    parser.add_argument(
        "--destination",
        type=Path,
        default=REPO_ROOT / "patches",
    )
    parser.add_argument(
        "--source-rom",
        type=Path,
        default=REPO_ROOT / "input/roms/englishrom.gba",
    )
    parser.add_argument(
        "--target-directory",
        type=Path,
        default=REPO_ROOT / "output/roms",
    )
    args = parser.parse_args()
    required = {config.code for config in load_registry().buildable()}
    try:
        manifest = PatchBundle(args.destination).promote_from(
            args.source,
            required,
            source_path=args.source_rom,
            target_directory=args.target_directory,
        )
    except PatchBundleError as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return 1
    print(
        f"✓ Bundle BPS build {manifest['build_number']} promu dans "
        f"{args.destination}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
