#!/usr/bin/env python3
"""Vérifie que chaque description d'attaque tient dans la fenêtre de résumé.

L'écran « Capacités connues » affiche la description d'une attaque sur **5
lignes maximum**, chaque ligne devant rester sous ~120 px (≈ 21 caractères de
la police FRLG). Au-delà, le texte déborde : mots coupés au bord droit
(horizontal) ou lignes masquées (vertical) — cf. les captures du ticket.

Ce script lit la ROM FR construite, décode chaque description d'attaque via la
table de pointeurs ``gMoveDescriptionPointers`` et liste celles qui débordent,
afin de retravailler ces traductions dans ``combined_fr.txt``.

Exemples
--------
    # Audit complet, ne lister que les attaques qui débordent
    python3 scripts/check_move_descriptions.py

    # Tout afficher (OK inclus), avec le détail ligne par ligne
    python3 scripts/check_move_descriptions.py --all --verbose

    # Export JSON de la liste à retravailler
    python3 scripts/check_move_descriptions.py --json out/move_overflow.json

    # Sur une autre ROM / avec des seuils personnalisés
    python3 scripts/check_move_descriptions.py --rom output/roms/GenedRom-fr.gba \\
        --max-lines 5 --max-width 120

Code de sortie : 0 si toutes les descriptions tiennent, 1 si au moins une
déborde (utilisable comme garde-fou de build).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.move_description_check import (  # noqa: E402
    MAX_LINES,
    MAX_LINE_WIDTH,
    MoveDescriptionResult,
    check_all_moves,
)

DEFAULT_ROM = Path("output/roms/GenedRom-fr.gba")


def _format_result(result: MoveDescriptionResult, verbose: bool) -> str:
    status = "OK    " if result.fits else "DÉBORDE"
    head = (
        f"[{status}] #{result.index:<3} {result.name:<18} "
        f"{result.line_count} ligne(s), max {result.max_line_width} px"
    )
    if result.fits and not verbose:
        return head
    parts = [head]
    if not result.fits:
        parts.append("        → " + " ; ".join(result.reasons))
    if verbose or not result.fits:
        for ln in result.lines:
            flag = " «<<" if ln.too_wide else ""
            parts.append(
                f"        {ln.width:3d}px {ln.chars:2d}c | {ln.text!r}{flag}"
            )
    return "\n".join(parts)


def _result_to_dict(result: MoveDescriptionResult) -> dict:
    return {
        "index": result.index,
        "name": result.name,
        "fits": result.fits,
        "line_count": result.line_count,
        "max_line_width": result.max_line_width,
        "reasons": result.reasons,
        "description": result.description,
        "lines": [
            {
                "text": ln.text,
                "width": ln.width,
                "chars": ln.chars,
                "too_wide": ln.too_wide,
            }
            for ln in result.lines
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Vérifie que les descriptions d'attaque tiennent dans la "
        "fenêtre de résumé (5 lignes × ~21 caractères)."
    )
    parser.add_argument(
        "--rom",
        type=Path,
        default=DEFAULT_ROM,
        help=f"ROM FR à auditer (défaut : {DEFAULT_ROM})",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=MAX_LINES,
        help=f"Nombre de lignes maximal (défaut : {MAX_LINES})",
    )
    parser.add_argument(
        "--max-width",
        type=int,
        default=MAX_LINE_WIDTH,
        help=f"Largeur de ligne maximale en pixels (défaut : {MAX_LINE_WIDTH})",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Afficher aussi les attaques qui tiennent (pas seulement les débordantes)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Détailler chaque ligne (largeur px, caractères)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Écrire le rapport complet en JSON à ce chemin",
    )
    args = parser.parse_args(argv)

    if not args.rom.is_file():
        parser.error(f"ROM introuvable : {args.rom}")

    rom = bytearray(args.rom.read_bytes())
    results = check_all_moves(
        rom, max_lines=args.max_lines, max_width=args.max_width
    )
    overflow = [r for r in results if not r.fits]

    shown = results if args.all else overflow
    for result in shown:
        print(_format_result(result, args.verbose))

    print()
    print(
        f"{len(results)} attaque(s) vérifiée(s) — "
        f"{len(results) - len(overflow)} OK, {len(overflow)} à retravailler "
        f"(seuils : {args.max_lines} lignes, {args.max_width} px/ligne)."
    )
    if overflow:
        names = ", ".join(f"{r.name} (#{r.index})" for r in overflow)
        print(f"À retravailler dans combined_fr.txt : {names}")

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "rom": str(args.rom),
            "max_lines": args.max_lines,
            "max_width": args.max_width,
            "total": len(results),
            "overflow_count": len(overflow),
            "moves": [_result_to_dict(r) for r in results],
        }
        args.json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Rapport JSON écrit : {args.json}")

    return 1 if overflow else 0


if __name__ == "__main__":
    raise SystemExit(main())
