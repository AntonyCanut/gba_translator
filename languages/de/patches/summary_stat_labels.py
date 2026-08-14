#!/usr/bin/env python3
"""Traduit les images-mots des pages Info, Capacités et Attaques en allemand.

La feuille LZ77 à ``0x00E9A460`` contient des mots dessinés en pixels plutôt
que des chaînes CFRU. Le patch reproduit d'abord chaque capsule anglaise au
pixel près, puis la remplace par une forme allemande qui tient dans ses 43 px.
Il couvre les six statistiques, NR./TYP/ID-NR. et les capsules STÄRKE et
GENAUIG. recomposées par le tilemap. Il s'exécute après
:mod:`languages.de.patches.hp_labels` et ne touche jamais à la zone ``KP``
voisine (x=32..47, y=48..63).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT_DIR))

from languages.de.terminology import section as terminology_section
from languages.fr.patches.font import (
    lz77_compress,
    lz77_decompress,
    pixels_to_tile,
    tile_to_pixels,
)
from languages.fr.patches.summary_stat_labels import GLYPHS as BASE_GLYPHS

OFFICIAL_STATS = terminology_section("stats")
STAT_DISPLAY = terminology_section("stat_display")
SUMMARY_WORD_IMAGES = terminology_section("summary_word_images")

TILE = 32
SHEET_WIDE = 16
BLOCK = 0x00E9A460
SLOT_LEN = 0x00E9B188 - BLOCK

BACKGROUND = 0xA
LETTER = 0x1
PILL = 0x7
PILL_X0, PILL_X1 = 50, 92
PILL_HEIGHT = 9
GLYPH_ROWS = 7
LABEL_CENTER = 71
LABEL_CENTER_OVERRIDES = {"EXP.": 72}
LETTER_GAP = 1
SPACE_WIDTH = 0

PILL_BODY: dict[int, tuple[int, int]] = {
    2: (51, 91),
    3: (50, 92),
    4: (50, 92),
    5: (50, 92),
    6: (50, 92),
    7: (51, 91),
}

# Formes officielles allemandes, raccourcies uniquement lorsque la capsule de
# 43 px l'exige. « Initiative » devient la forme historique « INIT. ».
LABELS: tuple[tuple[int, str, str], ...] = (
    (54, "ATTACK", STAT_DISPLAY["Attack"]),
    (66, "DEFENSE", STAT_DISPLAY["Defense"]),
    (78, "SP.ATK", STAT_DISPLAY["Special Attack"]),
    (90, "SP.DEF", STAT_DISPLAY["Special Defense"]),
    (102, "SPEED", STAT_DISPLAY["Speed"]),
    (114, "EXP.", STAT_DISPLAY["Experience"]),
)

GLYPHS: dict[str, tuple[str, ...]] = {
    **BASE_GLYPHS,
    "G": (".##.", "#..#", "#...", "#.##", "#..#", "#..#", ".###"),
    "R": ("###.", "#..#", "#..#", "###.", "#.#.", "#..#", "#..#"),
    "-": ("...", "...", "...", "###", "...", "...", "..."),
    "Ä": ("#..#", ".##.", "#..#", "#..#", "####", "#..#", "#..#"),
}

# Images-mots de la page Info. NAME, OT et ITEM sont déjà identiques en DE ;
# les trois autres doivent être redessinées dans leur créneau de 32 px.
INFO_LABELS: tuple[tuple[int, str, str], ...] = (
    (56, "NO", SUMMARY_WORD_IMAGES["number"]),
    (80, "TYPE", SUMMARY_WORD_IMAGES["type"]),
    (104, "IDNO", SUMMARY_WORD_IMAGES["id_number"]),
)

# Le tilemap du panneau de détail recompose ses deux capsules à partir de
# tuiles non contiguës. Cette carte a été relevée dans BG1 screenbase 0x6000
# sous mGBA ; la tuile 124 est volontairement dupliquée comme remplissage.
MOVE_PANEL_TILEMAP: tuple[tuple[int | None, ...], ...] = (
    (124, 125, 126, 127, 172, 173, 124),
    (140, 141, 142, 143, 188, 189, None),
    (158, 159, 204, 205, 190, 191, None),
    (174, 175, 220, 221, 206, 207, None),
)
MOVE_LABELS: tuple[tuple[int, str, str], ...] = (
    (6, "POWER", SUMMARY_WORD_IMAGES["power"]),
    (18, "ACCURACY", SUMMARY_WORD_IMAGES["accuracy"]),
)
COMPACT_BACKGROUND = BACKGROUND
COMPACT_CENTER = 24
COMPACT_X0, COMPACT_X1 = 0, 47


def _offset(x: int, y: int) -> int:
    tile = (y // 8) * SHEET_WIDE + x // 8
    return tile * TILE + (y % 8) * 4 + (x % 8) // 2


def px_get(tiles: bytes, x: int, y: int) -> int:
    """Retourne l'index de palette du pixel ``(x, y)``."""
    byte = tiles[_offset(x, y)]
    return byte & 0xF if x % 2 == 0 else byte >> 4


def px_set(tiles: bytearray, x: int, y: int, value: int) -> None:
    """Écrit un index de palette 4 bpp au pixel ``(x, y)``."""
    offset = _offset(x, y)
    if x % 2 == 0:
        tiles[offset] = (tiles[offset] & 0xF0) | value
    else:
        tiles[offset] = (tiles[offset] & 0x0F) | (value << 4)


def render_word(word: str) -> tuple[set[tuple[int, int]], int]:
    """Compose les pixels d'un mot et retourne aussi sa largeur."""
    pixels: set[tuple[int, int]] = set()
    cursor = 0
    for index, char in enumerate(word):
        if index:
            cursor += LETTER_GAP
        if char == " ":
            cursor += SPACE_WIDTH
            continue
        glyph = GLYPHS[char]
        for row, line in enumerate(glyph):
            for column, cell in enumerate(line):
                if cell == "#":
                    pixels.add((cursor + column, row))
        cursor += len(glyph[0])
    return pixels, cursor


def letter_mask(word: str) -> set[tuple[int, int]]:
    """Centre les pixels-lettres du mot dans la capsule."""
    pixels, width = render_word(word)
    center = LABEL_CENTER_OVERRIDES.get(word, LABEL_CENTER)
    start = center - width // 2
    return {(start + x, y + 1) for x, y in pixels}


def _dilate(columns: set[int]) -> set[int]:
    return {x + delta for x in columns for delta in (-1, 0, 1)}


def capsule_mask(letters: set[tuple[int, int]]) -> dict[int, set[int]]:
    """Construit les colonnes occupées par chaque rangée de la capsule."""
    rows = {y: {x for x, row in letters if row == y} for y in range(PILL_HEIGHT)}
    capsule = {y: set(range(x0, x1 + 1)) for y, (x0, x1) in PILL_BODY.items()}
    capsule[0] = _dilate(rows.get(1, set()))
    capsule[1] = _dilate(rows.get(1, set()) | rows.get(2, set()))
    capsule[8] = _dilate(rows.get(7, set()) | rows.get(8, set()))
    return capsule


def label_pixels(word: str) -> dict[tuple[int, int], int]:
    """Retourne le rendu complet des 9 × 43 pixels d'un libellé."""
    letters = letter_mask(word)
    capsule = capsule_mask(letters)
    return {
        (x, y): LETTER if (x, y) in letters else PILL if x in capsule[y] else BACKGROUND
        for y in range(PILL_HEIGHT)
        for x in range(PILL_X0, PILL_X1 + 1)
    }


def read_label(tiles: bytes, y0: int) -> dict[tuple[int, int], int]:
    """Lit la zone complète d'un libellé dans la feuille décompressée."""
    return {
        (x, y): px_get(tiles, x, y0 + y)
        for y in range(PILL_HEIGHT)
        for x in range(PILL_X0, PILL_X1 + 1)
    }


def fits(word: str) -> bool:
    """Indique si le libellé tient entièrement dans la capsule réservée."""
    return all(
        PILL_X0 <= x <= PILL_X1
        for columns in capsule_mask(letter_mask(word)).values()
        for x in columns
    )


def compact_label_pixels(
    word: str,
    *,
    center: int,
    x0: int,
    x1: int,
) -> dict[tuple[int, int], int]:
    """Compose une capsule arrondie de 9 px autour d'un mot contraint."""
    pixels, width = render_word(word)
    start = center - width // 2
    letters = {(start + x, y + 1) for x, y in pixels}
    left = start - 2
    right = start + width + 1
    if left < x0 or right > x1:
        raise ValueError(f"« {word} » dépasse la fenêtre {x0}..{x1}")
    pill = {
        0: set(range(left + 2, right - 1)),
        1: set(range(left + 1, right)),
        2: set(range(left, right + 1)),
        3: set(range(left, right + 1)),
        4: set(range(left, right + 1)),
        5: set(range(left, right + 1)),
        6: set(range(left, right + 1)),
        7: set(range(left + 1, right)),
        8: set(range(left + 2, right - 1)),
    }
    return {
        (x, y): LETTER if (x, y) in letters else PILL if x in pill[y] else COMPACT_BACKGROUND
        for y in range(9)
        for x in range(x0, x1 + 1)
    }


def _read_compact_label(
    tiles: bytes,
    y0: int,
    *,
    x0: int,
    x1: int,
) -> dict[tuple[int, int], int]:
    return {
        (x, y): px_get(tiles, x, y0 + y)
        for y in range(9)
        for x in range(x0, x1 + 1)
    }


def _move_panel_grid(tiles: bytes) -> list[list[int]]:
    grid = [[COMPACT_BACKGROUND] * 56 for _ in range(32)]
    for tile_y, row in enumerate(MOVE_PANEL_TILEMAP):
        for tile_x, index in enumerate(row):
            if index is None:
                continue
            pixels = tile_to_pixels(tiles[index * TILE : (index + 1) * TILE])
            for y in range(8):
                grid[tile_y * 8 + y][tile_x * 8 : tile_x * 8 + 8] = pixels[y * 8 : y * 8 + 8]
    return grid


def _write_move_panel_grid(tiles: bytearray, grid: list[list[int]]) -> None:
    written: dict[int, bytes] = {}
    for tile_y, row in enumerate(MOVE_PANEL_TILEMAP):
        for tile_x, index in enumerate(row):
            if index is None:
                continue
            pixels = [
                grid[tile_y * 8 + y][tile_x * 8 + x]
                for y in range(8)
                for x in range(8)
            ]
            encoded = pixels_to_tile(pixels)
            if index in written and written[index] != encoded:
                raise ValueError(f"tuile répétée {index} incohérente dans le panneau")
            written[index] = encoded
    for index, encoded in written.items():
        tiles[index * TILE : (index + 1) * TILE] = encoded


def patch_word_images(tiles: bytearray) -> tuple[int, list[str]]:
    """Traduit les labels Info et les capsules Puissance/Précision."""
    patched = 0
    messages: list[str] = []
    for slot_y, english, german in INFO_LABELS:
        y0 = slot_y + 2
        target = compact_label_pixels(german, center=16, x0=0, x1=31)
        if _read_compact_label(tiles, y0, x0=0, x1=31) == target:
            continue
        for (x, y), value in target.items():
            px_set(tiles, x, y0 + y, value)
        patched += 1
        messages.append(f"  « {english} » → « {german} » (Info)")

    panel = _move_panel_grid(tiles)
    for y0, english, german in MOVE_LABELS:
        target = compact_label_pixels(
            german,
            center=COMPACT_CENTER,
            x0=COMPACT_X0,
            x1=COMPACT_X1,
        )
        current = {
            (x, y): panel[y0 + y][x]
            for y in range(9)
            for x in range(COMPACT_X0, COMPACT_X1 + 1)
        }
        if current == target:
            continue
        for (x, y), value in target.items():
            panel[y0 + y][x] = value
        patched += 1
        messages.append(f"  « {english} » → « {german} » (attaque)")
    _write_move_panel_grid(tiles, panel)
    return patched, messages


def patch_sheet(tiles: bytearray) -> tuple[int, list[str]]:
    """Traduit la feuille en mémoire, sans altérer une capsule inconnue."""
    patched = 0
    messages: list[str] = []
    for y0, english, german in LABELS:
        current = read_label(tiles, y0)
        target = label_pixels(german)
        if current == target:
            messages.append(f"  « {german} » (y={y0}) : déjà traduit")
            continue
        if current != label_pixels(english):
            messages.append(f"  WARN « {english} » (y={y0}) : capsule inconnue — saut")
            continue
        if not fits(german):
            messages.append(f"  WARN « {german} » (y={y0}) : dépasse 43 px — saut")
            continue
        for (x, y), value in target.items():
            px_set(tiles, x, y0 + y, value)
        messages.append(f"  « {english} » → « {german} » (y={y0})")
        patched += 1
    return patched, messages


def apply_patches(rom_path: Path) -> int:
    """Applique le patch à une ROM et retourne le nombre de mots modifiés."""
    rom = bytearray(rom_path.read_bytes())
    if rom[0xB2] != 0x96:
        raise SystemExit(f"Not a valid GBA ROM: {rom_path}")
    result = lz77_decompress(rom, BLOCK)
    if result is None:
        print(f"  WARN bloc 0x{BLOCK:08X} indécompressable — saut", file=sys.stderr)
        return 0
    tiles = bytearray(result[0])
    patched, messages = patch_sheet(tiles)
    word_patched, word_messages = patch_word_images(tiles)
    patched += word_patched
    messages.extend(word_messages)
    for message in messages:
        print(message, file=sys.stderr if "WARN" in message else sys.stdout)
    if not patched:
        return 0
    compressed = lz77_compress(bytes(tiles))
    if len(compressed) > SLOT_LEN:
        print(
            f"  WARN bloc recompressé trop grand ({len(compressed)} > {SLOT_LEN})",
            file=sys.stderr,
        )
        return 0
    rom[BLOCK : BLOCK + SLOT_LEN] = compressed + bytes(SLOT_LEN - len(compressed))
    rom_path.write_bytes(rom)
    return patched


def main() -> None:
    """Point d'entrée en ligne de commande."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-de.gba"))
    args = parser.parse_args()
    if not args.rom.exists():
        raise SystemExit(f"ROM not found: {args.rom}")
    count = apply_patches(args.rom)
    print(f"patch_summary_stat_labels_de: {count} libellé(s) traduit(s)")


if __name__ == "__main__":
    main()
