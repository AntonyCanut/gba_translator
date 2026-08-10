#!/usr/bin/env python3
"""Traduit les libellés de statistiques de la page « Capacités » (issue #145).

Dans le menu Pokémon → onglet « Capacités », les libellés de statistiques ne
sont pas du texte : ce sont des **images de mots** (word-images) gravées dans
le tileset LZ77 ``0x00E9A460`` (512 tuiles 4bpp, feuille de 16 tuiles de large)
et positionnées par le tilemap de la page résumé. Aucune passe de traduction ne
les atteint — d'où l'anglais résiduel dans la ROM FR.

Les six libellés sont empilés tous les 12 px à partir de ``y = 54``, chacun
dessiné dans une gélule de 9 rangées occupant au plus ``x = 50..92`` :

===========  ===========  ==============================
libellé      y (haut)     traitement
===========  ===========  ==============================
ATTACK       54           → ``ATTAQUE``
DEFENSE      66           inchangé (transparent en FR)
SP.ATK       78           → ``ATQ. SPE.``
SP.DEF       90           → ``DEF. SPE.``
SPEED        102          → ``VITESSE``
EXP.         114          inchangé
===========  ===========  ==============================

Le « HP » gris de la même feuille (tuiles 100/101 + 116/117) est déjà traduit
en « PV » par :mod:`languages.fr.patches.hp_labels` — ce patch n'y touche pas.

Forme de la gélule
------------------
La gélule n'est **pas** un ovale de largeur fixe : ses rangées haute et basse
épousent le mot, ce qui interdit de se contenter de réécrire les lettres — un
mot français plus long déborderait d'une gélule restée à la taille anglaise.
Sa forme est entièrement déterministe (:func:`capsule_mask`) : ``a`` = fond du
panneau, ``7`` = intérieur de la gélule, ``1`` = lettres.

======  ==========================================================
rangée  colonnes remplies
======  ==========================================================
0       colonnes-lettres de la rangée 1, dilatées de 1 px
1       colonnes-lettres des rangées 1 et 2, dilatées de 1 px
2       ``x = 51..91`` (corps fixe)
3-6     ``x = 50..92`` (corps fixe)
7       ``x = 51..91`` (corps fixe)
8       colonnes-lettres de la rangée 7, dilatées de 1 px
======  ==========================================================

Ce modèle reproduit **au pixel près** les cinq gélules de statistiques
anglaises (ATTACK / DEFENSE / SP.ATK / SP.DEF / SPEED) ; le test unitaire le
revérifie contre la ROM. Seule ``EXP.`` échappe à la règle de centrage
``x = 71 - largeur // 2`` (décalée d'1 px par son point final) — raison de plus
pour la laisser tranquille.

Police
------
Les lettres sont une fonte pixel maison de 7 rangées, trait 1 px. Le ``Q``
redessiné par l'auteur possède seul une huitième rangée de descente dans le
bord bas de la gélule.
:data:`GLYPHS` reprend au pixel près les glyphes déjà présents dans la feuille
(ATTACK / DEFENSE / SP.ATK / SPEED / EXP. / NAME / TYPE / OT / IDNo / ITEM /
PV) ; seuls ``Q`` et ``U``, absents de tout libellé anglais, ont été dessinés
dans le même style — ``U`` est le ``O`` sans la courbe haute, ``Q`` le ``O``
refermé une rangée plus tôt avec une queue en bas à droite.

Validation stricte
------------------
Pour chaque libellé, les 9 × 43 pixels lus dans la ROM doivent reproduire
exactement soit la gélule anglaise, soit la gélule française (ROM déjà patchée
→ aucun changement). Toute autre forme est signalée et sautée : le patch ne
corrompt jamais une feuille inattendue, et il est idempotent.

S'exécute dans la chaîne ``build-fr`` APRÈS ``hp_labels`` (voir Makefile), les
deux patchs se partageant le bloc ``0x00E9A460`` sans se recouvrir.

Usage::

    python3 languages/fr/patches/summary_stat_labels.py \\
        --rom output/roms/GenedRom-fr.gba
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT_DIR))

from languages.fr.patches.font import lz77_compress, lz77_decompress  # noqa: E402

TILE = 32          # octets par tuile 4bpp 8x8
SHEET_WIDE = 16    # tuiles par rangée dans la feuille 0x00E9A460

BLOCK = 0x00E9A460

# Le bloc possède son emplacement : la première adresse visée par un pointeur
# au-dessus de lui est 0x08E9B188, et rien ne pointe à l'intérieur du flux. Le
# flux anglais d'origine fait 3084 octets et la fin de l'emplacement est du
# remplissage à zéro (vérifié sur les ROMs EN, ES et FR source) ; ``hp_labels``
# recompresse le bloc juste avant nous et le raccourcit (3059 octets), laissant
# derrière lui la queue morte de l'ancien flux. Se contenter de comparer à la
# longueur *courante* refuserait donc à tort une gélule française plus large :
# on vérifie l'emplacement complet, et on remet sa fin à zéro pour ne pas
# laisser à notre tour une queue morte (elle ferait échouer la tolérance
# « queue de remplissage » des outils génériques comme insert_sprite.py).
SLOT_LEN = 0x00E9B188 - BLOCK

BACKGROUND = 0xA   # fond du panneau, autour de la gélule
LETTER = 0x1       # couleur des lettres
PILL = 0x7         # intérieur de la gélule

PILL_X0, PILL_X1 = 50, 92     # emprise horizontale maximale de la gélule
PILL_HEIGHT = 9               # lettres sur 1..7, descente du Q sur 8
GLYPH_ROWS = 7
LABEL_CENTER = 71             # axe de centrage par défaut des libellés
LABEL_CENTER_OVERRIDES = {
    "DEF. SPE.": 72,          # position exacte de la planche définitive
}

# Corps fixe de la gélule, par rangée (les rangées 0 et 8 épousent le mot).
PILL_BODY: dict[int, tuple[int, int]] = {
    2: (51, 91),
    3: (50, 92),
    4: (50, 92),
    5: (50, 92),
    6: (50, 92),
    7: (51, 91),
}

# Libellés à traduire : (y du haut de la gélule, mot anglais, mot français).
# DEFENSE (y=66) et EXP. (y=114) sont volontairement absents : le premier est
# transparent en français, le second n'est pas un libellé de statistique.
LABELS: tuple[tuple[int, str, str], ...] = (
    (54, "ATTACK", "ATTAQUE"),
    (78, "SP.ATK", "ATQ. SPE."),
    (90, "SP.DEF", "DEF. SPE."),
    (102, "SPEED", "VITESSE"),
)

# Fonte des images-mots : 7 rangées, '#' = pixel lettre. Relevée au pixel près
# dans la feuille anglaise (cf. tests/test_summary_stat_labels_fr.py, qui
# revérifie chaque glyphe contre la ROM).
GLYPHS: dict[str, tuple[str, ...]] = {
    "A": (".##.", "#..#", "#..#", "####", "#..#", "#..#", "#..#"),
    "C": (".##.", "#..#", "#...", "#...", "#..#", "#..#", ".##."),
    "D": ("###.", "#..#", "#..#", "#..#", "#..#", "#..#", "###."),
    "E": ("####", "#...", "#...", "###.", "#...", "#...", "####"),
    "F": ("####", "#...", "#...", "###.", "#...", "#...", "#..."),
    "I": ("###", ".#.", ".#.", ".#.", ".#.", ".#.", "###"),
    "K": ("#..#", "#..#", "#.#.", "##..", "#.#.", "#..#", "#..#"),
    "M": ("#...#", "##.##", "#.#.#", "#...#", "#...#", "#...#", "#...#"),
    "N": ("#..#", "##.#", "##.#", "#.##", "#.##", "#..#", "#..#"),
    "O": (".##.", "#..#", "#..#", "#..#", "#..#", "#..#", ".##."),
    "P": ("###.", "#..#", "#..#", "###.", "#...", "#...", "#..."),
    "S": (".##.", "#..#", "#...", ".##.", "...#", "#..#", ".##."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    # Pointe refermée sur un pixel, comme l'a redessiné l'auteur de l'issue
    # dans languages/fr/sprites/summary_stat_labels.png : la planche fait foi,
    # ce glyphe la suit (cf. tests/test_summary_sheet_fr.py).
    "V": ("#..#", "#..#", "#..#", "#..#", "#..#", "#.#.", ".#.."),
    "X": ("#..#", "#..#", "#..#", ".##.", "#..#", "#..#", "#..#"),
    "Y": ("#...#", "#...#", ".#.#.", ".#.#.", "..#..", "..#..", "..#.."),
    ".": ("..", "..", "..", "..", "..", "##", "##"),
    # Glyphes absents de la feuille anglaise, dessinés dans le même style.
    "U": ("#..#", "#..#", "#..#", "#..#", "#..#", "#..#", ".##."),
    "Q": (".##.", "#..#", "#..#", "#..#", "#..#", "#.##", ".##.", "...#"),
}

LETTER_GAP = 1     # colonnes vides entre deux glyphes
SPACE_WIDTH = 0    # les deux gaps voisins suffisent à séparer les mots


# ---------------------------------------------------------------------------
# Accès pixel dans la feuille décompressée (pixel gauche = quartet bas)
# ---------------------------------------------------------------------------

def _offset(x: int, y: int) -> int:
    tile = (y // 8) * SHEET_WIDE + x // 8
    return tile * TILE + (y % 8) * 4 + (x % 8) // 2


def px_get(tiles: bytes, x: int, y: int) -> int:
    byte = tiles[_offset(x, y)]
    return byte & 0xF if x % 2 == 0 else byte >> 4


def px_set(tiles: bytearray, x: int, y: int, value: int) -> None:
    off = _offset(x, y)
    if x % 2 == 0:
        tiles[off] = (tiles[off] & 0xF0) | value
    else:
        tiles[off] = (tiles[off] & 0x0F) | (value << 4)


# ---------------------------------------------------------------------------
# Composition d'un libellé
# ---------------------------------------------------------------------------

def render_word(word: str) -> tuple[set[tuple[int, int]], int]:
    """Pixels ``(dx, dy)`` de *word* et sa largeur, origine en haut à gauche."""
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
            for col, cell in enumerate(line):
                if cell == "#":
                    pixels.add((cursor + col, row))
        cursor += len(glyph[0])
    return pixels, cursor


def letter_mask(word: str) -> set[tuple[int, int]]:
    """Pixels-lettre ``(x, dy)`` du mot centré, ``dy`` relatif au haut de la gélule.

    Les lettres occupent les rangées 1 à 7 de la gélule, les rangées 0 et 8
    étant ses bords hauts et bas.
    """
    pixels, width = render_word(word)
    center = LABEL_CENTER_OVERRIDES.get(word, LABEL_CENTER)
    start = center - width // 2
    return {(start + dx, dy + 1) for dx, dy in pixels}


def _dilate(columns: set[int]) -> set[int]:
    """Colonnes élargies d'1 px de chaque côté (le liseré de la gélule)."""
    return {x + dx for x in columns for dx in (-1, 0, 1)}


def capsule_mask(letters: set[tuple[int, int]]) -> dict[int, set[int]]:
    """Colonnes remplies de la gélule, par rangée, pour un jeu de lettres donné."""
    rows = {dy: {x for x, row in letters if row == dy} for dy in range(PILL_HEIGHT)}
    capsule = {dy: set(range(x0, x1 + 1)) for dy, (x0, x1) in PILL_BODY.items()}
    capsule[0] = _dilate(rows.get(1, set()))
    capsule[1] = _dilate(rows.get(1, set()) | rows.get(2, set()))
    # Le Q définitif descend sur la rangée 8 : son pixel doit lui aussi être
    # entouré par le bord bas de la gélule.
    capsule[8] = _dilate(rows.get(7, set()) | rows.get(8, set()))
    return capsule


def label_pixels(word: str) -> dict[tuple[int, int], int]:
    """Couleur attendue de chaque pixel ``(x, dy)`` de la zone du libellé."""
    letters = letter_mask(word)
    capsule = capsule_mask(letters)
    return {
        (x, dy): (
            LETTER if (x, dy) in letters
            else PILL if x in capsule[dy]
            else BACKGROUND
        )
        for dy in range(PILL_HEIGHT)
        for x in range(PILL_X0, PILL_X1 + 1)
    }


def read_label(tiles: bytes, y0: int) -> dict[tuple[int, int], int]:
    """Couleur courante de chaque pixel de la zone du libellé à *y0*."""
    return {
        (x, dy): px_get(tiles, x, y0 + dy)
        for dy in range(PILL_HEIGHT)
        for x in range(PILL_X0, PILL_X1 + 1)
    }


def fits(word: str) -> bool:
    """Vrai si la gélule de *word* tient dans l'emprise ``x = 50..92``."""
    letters = letter_mask(word)
    return all(
        PILL_X0 <= x <= PILL_X1
        for columns in capsule_mask(letters).values()
        for x in columns
    )


# ---------------------------------------------------------------------------
# Pilote du patch
# ---------------------------------------------------------------------------

def patch_sheet(tiles: bytearray) -> tuple[int, list[str]]:
    """Traduit les libellés dans la feuille décompressée. Retourne (n, messages)."""
    patched = 0
    messages: list[str] = []
    for y0, english, french in LABELS:
        current = read_label(tiles, y0)
        target = label_pixels(french)
        if current == target:
            messages.append(f"  « {french} » (y={y0}) : déjà traduit — inchangé")
            continue
        if current != label_pixels(english):
            messages.append(
                f"  WARN « {english} » (y={y0}) : la gélule ne correspond ni à "
                f"l'anglais ni à « {french} » — saut"
            )
            continue
        if not fits(french):
            messages.append(
                f"  WARN « {french} » (y={y0}) : trop long, la gélule déborderait "
                f"de x={PILL_X0}..{PILL_X1} — saut"
            )
            continue
        for (x, dy), value in target.items():
            px_set(tiles, x, y0 + dy, value)
        messages.append(f"  « {english} » → « {french} » (y={y0})")
        patched += 1
    return patched, messages


def apply_patches(rom_path: Path) -> int:
    rom = bytearray(rom_path.read_bytes())
    if rom[0xB2] != 0x96:
        raise SystemExit(f"Not a valid GBA ROM: {rom_path}")

    result = lz77_decompress(rom, BLOCK)
    if result is None:
        print(f"  WARN bloc 0x{BLOCK:08X} indécompressable — saut", file=sys.stderr)
        return 0
    tiles = bytearray(result[0])

    patched, messages = patch_sheet(tiles)
    for message in messages:
        print(message, file=sys.stderr if "WARN" in message else sys.stdout)
    if not patched:
        return 0

    compressed = lz77_compress(bytes(tiles))
    if len(compressed) > SLOT_LEN:
        print(
            f"  WARN recompressé ({len(compressed)}) dépasse l'emplacement de "
            f"{SLOT_LEN} octets — aucun changement",
            file=sys.stderr,
        )
        return 0
    rom[BLOCK:BLOCK + SLOT_LEN] = compressed + bytes(SLOT_LEN - len(compressed))
    rom_path.write_bytes(rom)
    return patched


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path,
                        default=Path("output/roms/GenedRom-fr.gba"))
    args = parser.parse_args()
    if not args.rom.exists():
        raise SystemExit(f"ROM not found: {args.rom}")
    count = apply_patches(args.rom)
    print(f"patch_summary_stat_labels_fr: {count} libellé(s) traduit(s)")


if __name__ == "__main__":
    main()
