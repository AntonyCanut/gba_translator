#!/usr/bin/env python3
"""Italian port of ``patch_move_descriptions_fr`` — re-wraps every Italian move
description to the 5-line summary window, sourcing the text from the Italian
translation-ready JSON.

The French implementation is translation-JSON driven; this wrapper points it at
``output/translation/it_translation_ready.json`` and, crucially, at an *empty*
Italian overrides file so the curated **French** short-description overrides can
never leak into the Italian build. Moves absent from the Italian JSON stay
English.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from src.i18n.fr_patch_delegate import build_command, run  # noqa: E402

IT_TRANSLATIONS = REPO_ROOT / "output/translation/it_translation_ready.json"
IT_OVERRIDES = REPO_ROOT / "languages/it/data/move_descriptions_it_overrides.json"


def make_command(rom: Path, translations: Path | None = None) -> list[str]:
    return build_command(
        "patch_move_descriptions_fr.py",
        rom,
        source=True,
        translations=translations or IT_TRANSLATIONS,
        overrides=IT_OVERRIDES,
        reference_rom=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument(
        "--translations",
        type=Path,
        default=None,
        help="Italian translation-ready JSON (defaults to output/translation/it_translation_ready.json)",
    )
    args = parser.parse_args(argv)
    translations = args.translations or IT_TRANSLATIONS
    if not translations.exists():
        print(f"⚠ skipping move_descriptions (IT): {translations} not found")
        return 0
    return run(make_command(args.rom, translations))


if __name__ == "__main__":
    raise SystemExit(main())
