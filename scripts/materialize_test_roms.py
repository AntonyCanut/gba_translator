#!/usr/bin/env python3
"""Matérialise localement les ROMs E2E depuis le bundle BPS suivi."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.core.patch_bundle import PatchBundle, PatchBundleError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("languages", nargs="+", help="Codes langue à matérialiser")
    parser.add_argument(
        "--source",
        type=Path,
        default=REPO_ROOT / "input/roms/englishrom.gba",
    )
    parser.add_argument("--bundle", type=Path, default=REPO_ROOT / "patches")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "output/roms",
    )
    args = parser.parse_args()
    try:
        patch_bundle = PatchBundle(args.bundle)
        manifest = patch_bundle.verify()
        entries = {entry["code"]: entry for entry in manifest["languages"]}
        for code in args.languages:
            if code not in entries:
                raise PatchBundleError(f"langue absente du bundle: {code}")
            output = args.output_dir / entries[code]["target"]["file"]
            patch_bundle.materialize(code, args.source, output)
            print(f"✓ {code}: {output}")
    except PatchBundleError as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
