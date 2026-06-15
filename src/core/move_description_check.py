#!/usr/bin/env python3
"""Vérifie que chaque description d'attaque tient dans la fenêtre de résumé.

L'écran « Capacités connues » affiche la description d'une attaque dans une
fenêtre de **5 lignes maximum**, chaque ligne devant rester sous ~142 px de
large (environ 21 caractères de la police FRLG). Au-delà, le texte déborde :
horizontalement les mots sont coupés au bord droit, verticalement les lignes
supplémentaires sont masquées (cf. les captures du ticket : Jet-Pierres et
Morsure débordaient, Groz'Yeux tenait).

Les descriptions sont stockées dans la ROM via une table de pointeurs
(``gMoveDescriptionPointers``) indexée par numéro d'attaque. Ce module lit la
ROM construite, décode chaque description et signale celles qui débordent.

Le budget (5 lignes, 142 px) et la table sont partagés avec
:mod:`src.core.moves`, qui re-wrappe/relocalise chaque description au build
(``scripts/patch_move_descriptions_fr.py``). La largeur de 142 px est la plus
large ligne trouvée dans la ROM espagnole de référence — la mise en page pour
laquelle la fenêtre a été conçue, donc garantie de tenir à l'écran. La police
étant à chasse variable, le pixel fait foi ; la limite « 21 caractères » du
ticket n'en est qu'une approximation.
police étant à chasse variable, le pixel fait foi ; la limite « 21 caractères »
du ticket n'en est qu'une approximation.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import List, Optional

from src.core import moves
from src.core.dialogue_linewrap import line_width
from src.core.text_codec import TextDecoder

# --- Disposition ROM (Pokemon Unbound / CFRU) -------------------------------
GBA_ROM_BASE = 0x08000000

# Table de pointeurs des descriptions d'attaque, indexée par numéro d'attaque.
# Source unique partagée avec :mod:`src.core.moves` (qui re-wrappe/relocalise
# les descriptions au build). Localisée et vérifiée contre la ROM FR :
# desc[1] = Écras'Face, desc[44] = Morsure, desc[88] = Jet-Pierres. Le texte
# décodé reproduit exactement l'écran de résumé in-game.
MOVE_DESCRIPTION_TABLE = moves.MOVE_DESCRIPTION_TABLE

# Table des noms d'attaque (déjà en français dans la ROM source), 894 cellules
# de 13 octets. cf. src/core/fixed_tables.py (« attack names »).
MOVE_NAME_TABLE = 0x1B2980
MOVE_NAME_STRIDE = 13
MOVE_COUNT = 894

TERMINATOR = 0xFF
# Octet maximal à lire pour une description avant de renoncer (garde-fou contre
# une description sans terminateur qui partirait à la dérive dans la ROM).
MAX_DESCRIPTION_BYTES = 512

# --- Contraintes d'affichage de la fenêtre de description -------------------
#: Nombre maximal de lignes affichées simultanément (partagé avec moves).
MAX_LINES = moves.MOVE_MAX_LINES

#: Largeur utile de la fenêtre, en pixels (partagé avec moves). 130 px = la
#: plus large ligne espagnole (142 px) moins une marge de 2 caractères (~12 px).
MAX_LINE_WIDTH = moves.MOVE_LINE_WIDTH

#: Approximation « caractères affichés » du ticket (purement indicative).
MAX_CHARS = 21


@dataclass
class LineInfo:
    """Mesure d'une ligne de description."""

    text: str
    width: int
    chars: int
    too_wide: bool


@dataclass
class MoveDescriptionResult:
    """Résultat de la vérification d'une attaque."""

    index: int
    name: str
    description: str
    lines: List[LineInfo]
    too_many_lines: bool
    max_lines: int
    max_width: int

    @property
    def line_count(self) -> int:
        return len(self.lines)

    @property
    def max_line_width(self) -> int:
        return max((ln.width for ln in self.lines), default=0)

    @property
    def fits(self) -> bool:
        return not self.too_many_lines and not any(ln.too_wide for ln in self.lines)

    @property
    def reasons(self) -> List[str]:
        """Liste lisible des causes de débordement (vide si tout tient)."""
        out: List[str] = []
        if self.too_many_lines:
            out.append(
                f"{self.line_count} lignes (max {self.max_lines})"
            )
        wide = [ln for ln in self.lines if ln.too_wide]
        if wide:
            worst = max(ln.width for ln in wide)
            out.append(
                f"{len(wide)} ligne(s) trop large(s) "
                f"(jusqu'à {worst} px, max {self.max_width} px)"
            )
        return out


def check_description_text(
    description: str,
    *,
    max_lines: int = MAX_LINES,
    max_width: int = MAX_LINE_WIDTH,
) -> tuple[List[LineInfo], bool]:
    """Mesure une description décodée (lignes séparées par ``\\n``).

    Retourne la liste des lignes mesurées et un booléen ``too_many_lines``.
    Fonction pure : aucun accès ROM, testable directement.
    """
    raw_lines = description.split("\n")
    lines = [
        LineInfo(
            text=ln,
            width=line_width(ln),
            chars=len(ln),
            too_wide=line_width(ln) > max_width,
        )
        for ln in raw_lines
    ]
    too_many_lines = len(raw_lines) > max_lines
    return lines, too_many_lines


def read_move_name(rom: bytes, index: int) -> str:
    """Décode le nom français de l'attaque ``index`` depuis la table fixe."""
    base = MOVE_NAME_TABLE + index * MOVE_NAME_STRIDE
    cell = rom[base : base + MOVE_NAME_STRIDE]
    end = cell.find(b"\xff")
    if end == -1:
        end = len(cell)
    return TextDecoder.decode_pokemon(bytes(cell[:end]))


def read_move_description(rom: bytes, index: int) -> Optional[str]:
    """Décode la description de l'attaque ``index`` via la table de pointeurs.

    Retourne ``None`` si le pointeur est invalide.
    """
    ptr_off = MOVE_DESCRIPTION_TABLE + index * 4
    if ptr_off + 4 > len(rom):
        return None
    ptr = struct.unpack_from("<I", rom, ptr_off)[0]
    if not (GBA_ROM_BASE <= ptr < GBA_ROM_BASE + len(rom)):
        return None
    off = ptr - GBA_ROM_BASE
    end = rom.find(b"\xff", off, off + MAX_DESCRIPTION_BYTES)
    if end == -1:
        end = off + MAX_DESCRIPTION_BYTES
    return TextDecoder.decode_pokemon(bytes(rom[off:end]))


def check_move(
    rom: bytes,
    index: int,
    *,
    max_lines: int = MAX_LINES,
    max_width: int = MAX_LINE_WIDTH,
) -> Optional[MoveDescriptionResult]:
    """Vérifie une attaque. ``None`` si le pointeur de description est invalide."""
    description = read_move_description(rom, index)
    if description is None:
        return None
    name = read_move_name(rom, index)
    lines, too_many = check_description_text(
        description, max_lines=max_lines, max_width=max_width
    )
    return MoveDescriptionResult(
        index=index,
        name=name,
        description=description,
        lines=lines,
        too_many_lines=too_many,
        max_lines=max_lines,
        max_width=max_width,
    )


def _is_placeholder(name: str) -> bool:
    return name.strip() in ("", "-", "?")


def check_all_moves(
    rom: bytes,
    *,
    count: int = MOVE_COUNT,
    start: int = 1,
    max_lines: int = MAX_LINES,
    max_width: int = MAX_LINE_WIDTH,
    skip_placeholders: bool = True,
) -> List[MoveDescriptionResult]:
    """Vérifie toutes les attaques de ``start`` à ``count`` (exclus).

    L'attaque 0 (« aucune ») est ignorée par défaut, ainsi que les emplacements
    dont le nom est un simple tiret (attaques non utilisées).
    """
    results: List[MoveDescriptionResult] = []
    for index in range(start, count):
        result = check_move(
            rom, index, max_lines=max_lines, max_width=max_width
        )
        if result is None:
            continue
        if skip_placeholders and _is_placeholder(result.name):
            continue
        results.append(result)
    return results
