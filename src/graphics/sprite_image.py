"""Dispatch BMP/PNG des images indexées utilisées par les sprites GBA."""

from __future__ import annotations

from pathlib import Path

from src.graphics.sprite_bmp import (
    DEFAULT_PALETTE,
    Grid,
    Palette,
    read_indexed_bmp,
    write_indexed_bmp,
)
from src.graphics.sprite_png import read_indexed_png, write_indexed_png


def _format(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix not in {".bmp", ".png"}:
        raise ValueError(f"{path}: unsupported image format (expected .bmp or .png)")
    return suffix


def write_indexed_image(
    path: Path,
    width: int,
    height: int,
    grid: Grid,
    palette: Palette = DEFAULT_PALETTE,
) -> None:
    """Écrit une image indexée selon l'extension de *path*."""
    if _format(path) == ".png":
        write_indexed_png(path, width, height, grid, palette)
    else:
        write_indexed_bmp(path, width, height, grid, palette)


def read_indexed_image(path: Path) -> tuple[int, int, Grid]:
    """Lit une image indexée selon l'extension de *path*."""
    if _format(path) == ".png":
        return read_indexed_png(path)
    return read_indexed_bmp(path)


def variant_path(path: Path, block_index: int) -> Path:
    """Ajoute ``-<index>`` avant l'extension pour un export multi-blocs."""
    return path.with_name(f"{path.stem}-{block_index}{path.suffix}")
