#!/usr/bin/env python3
"""Injecte les sources graphiques éditables des menus allemands."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from languages.de.sprites import SPRITES

INSERT_SPRITE = ROOT / "scripts/insert_sprite.py"
ASSET_DIR = ROOT / "languages/de/sprites"


@dataclass(frozen=True)
class SpritePatch:
    """Décrit une insertion d'image dans une copie de sprite active."""

    sprite: str
    image: Path
    block_index: int = 0


PATCHES = (
    SpritePatch("selection", ASSET_DIR / "selection.png"),
    SpritePatch("start_menu_move_hint", ASSET_DIR / "start_menu_move_hint.png"),
    SpritePatch("cube_sort_hint", ASSET_DIR / "cube_sort_hint.png"),
    SpritePatch("pc_box_labels", ASSET_DIR / "pc_box_labels.png"),
    SpritePatch("pokemon_mart_sign", ASSET_DIR / "pokemon_mart_sign-0.png", 0),
    SpritePatch("pokemon_mart_sign", ASSET_DIR / "pokemon_mart_sign-1.png", 1),
    SpritePatch("pokemon_mart_sign", ASSET_DIR / "pokemon_mart_sign-2.png", 2),
)


def make_command(rom: Path, patch: SpritePatch) -> list[str]:
    """Construit la commande sûre d'insertion d'une source indexée."""
    command = [
        sys.executable,
        str(INSERT_SPRITE),
        "--rom",
        str(rom),
        "--lang",
        "de",
        "--sprite",
        patch.sprite,
        "--image",
        str(patch.image),
    ]
    if len(SPRITES[patch.sprite].blocks) > 1:
        command.extend(("--block-index", str(patch.block_index)))
    return command


def apply(rom: Path) -> int:
    """Injecte toutes les copies et retourne leur nombre."""
    for patch in PATCHES:
        subprocess.run(make_command(rom, patch), cwd=ROOT, check=True)
    return len(PATCHES)


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée CLI du patch post-build."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    args = parser.parse_args(argv)
    if not args.rom.exists():
        raise SystemExit(f"ROM introuvable : {args.rom}")

    patched = apply(args.rom)
    print(f"patch_menu_sprites_de: {patched} copie(s) injectée(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
