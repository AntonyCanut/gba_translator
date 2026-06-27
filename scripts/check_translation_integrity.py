#!/usr/bin/env python3
"""
Garde anti-régression des traductions FR (combined_fr.txt).

Empêche la reproduction du bug c7c1ede : une réécriture en masse de
``combined_fr.txt`` qui « ramène » silencieusement des labels carte du monde à
leur forme anglaise/périmée (Fallshore → Ville de Fallshore, Île de la Lune →
Fullmoon Island, etc.).

Principe de la vérification (cf. ``docs/20_TRANSLATION_PRESERVATION.md``)
------------------------------------------------------------------------
1. On parse ``combined_fr.txt`` avec la **même règle que la chaîne de build** :
   un offset présent plusieurs fois → **la dernière entrée gagne**
   (``apply_combined_fr.py`` fait ``mapping[offset] = text``). Le bloc hexa
   minuscule en bas de fichier est donc la version vivante.
2. Pour chaque offset critique, on contrôle la valeur **résolue** (last-wins) :
   - PRÉSENCE   : l'offset doit résoudre vers un texte non vide ;
   - NON-RÉGRESSION : la valeur ne doit pas être une forme anglaise/périmée connue.

Un simple ``grep -c`` ne suffit PAS : c7c1ede n'a pas supprimé les lignes, il a
réécrit leur **valeur**. La garde contrôle donc la valeur résolue, pas la
présence d'une ligne.

Sortie : code 0 si tout est conforme, code 1 si au moins une régression.

Usage
-----
    python3 scripts/check_translation_integrity.py
    python3 scripts/check_translation_integrity.py --file chemin/combined_fr.txt
    python3 scripts/check_translation_integrity.py --json   # rapport machine
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# Format d'une ligne : « 0x<hex>: <texte FR> » (identique à apply_combined_fr.py).
LINE_RE = re.compile(r"^\s*0x([0-9A-Fa-f]+)\s*:\s*(.*)$")

DEFAULT_COMBINED = Path(__file__).resolve().parents[1] / "languages/fr/combined_fr.txt"


@dataclass(frozen=True)
class CriticalLabel:
    """Un label de la carte du monde à protéger contre la régression EN/périmée."""

    offset: int
    name: str
    expected_fr: str
    # Formes anglaises ou périmées qui constituent une régression (insensible à la casse).
    forbidden_forms: tuple[str, ...]


# Les 13 labels carte du monde sauvés par B-52 (commit c7c1ede les avait écrasés).
# Ces offsets 0xB5xxxx / 0x72xxxx ne vivent QUE dans combined_fr.txt : ils sont
# absents du CSV trilingue, donc invisibles aux autres garde-fous.
CRITICAL_LABELS: tuple[CriticalLabel, ...] = (
    CriticalLabel(0xB500A0, "Bourg Gurun", "Bourg Gurun", ("ourg Gurum", "Bourg Gurum")),
    CriticalLabel(0x721304, "Trou Glacé", "Trou Glacé", ("Icy Hole",)),
    CriticalLabel(0x7214E8, "Île Scintillante", "Île Scintillante", ("Glimmer Island",)),
    CriticalLabel(0x721968, "Ville d'Epidimy", "Ville d'Epidimy", ("Epidimy Town",)),
    CriticalLabel(0xB50214, "Égouts d'Antisis", "Égouts d'Antisis", ("Antisis Sewers",)),
    CriticalLabel(0xB503CC, "Volcan Cendreux", "Volcan Cendreux", ("Cinder Volcano",)),
    CriticalLabel(0xB514E4, "Dehara", "Dehara", ("Dehara City", "Ville de Dehara")),
    CriticalLabel(0xB52274, "Pension Pokémon", "Pension Pokémon", ("Pokemon Day Care", "Pokémon Day Care")),
    CriticalLabel(0xB522A4, "Bourg Polder", "Bourg Polder", ("Polder Town",)),
    CriticalLabel(0xB531D8, "Île du Croissant", "Île du Croissant", ("Newmoon Island",)),
    CriticalLabel(0xB535C8, "Île de la Lune", "Île de la Lune", ("Fullmoon Island",)),
    CriticalLabel(0xB537AC, "Bois-Rouge", "Bois-Rouge", ("Redwood Village", "Redwood village")),
    CriticalLabel(0x720E74, "Fallshore", "Fallshore", ("Ville de Fallshore",)),
)


@dataclass
class LabelResult:
    """Résultat de la vérification d'un label critique."""

    label: CriticalLabel
    resolved: Optional[str]
    ok: bool
    reason: str


@dataclass
class IntegrityReport:
    """Bilan global de la garde d'intégrité."""

    total_entries: int
    distinct_offsets: int
    duplicate_offsets: int
    results: List[LabelResult] = field(default_factory=list)

    @property
    def failures(self) -> List[LabelResult]:
        return [r for r in self.results if not r.ok]

    @property
    def ok(self) -> bool:
        return not self.failures


def load_last_wins(path: Path) -> tuple[Dict[int, str], int]:
    """Parse combined_fr.txt en appliquant la règle last-wins de la chaîne de build.

    Retourne ``(mapping, total_entries)`` où ``mapping[offset]`` est la **dernière**
    valeur rencontrée (insensible à la casse de l'offset, car l'offset est un int).
    """

    mapping: Dict[int, str] = {}
    total = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            match = LINE_RE.match(line.rstrip("\n"))
            if not match:
                continue
            offset = int(match.group(1), 16)
            mapping[offset] = match.group(2).strip()
            total += 1
    return mapping, total


def check_label(label: CriticalLabel, mapping: Dict[int, str]) -> LabelResult:
    """Contrôle présence + non-régression d'un label critique."""

    resolved = mapping.get(label.offset)
    if resolved is None:
        return LabelResult(label, None, False, "offset absent de combined_fr.txt")
    if not resolved.strip():
        return LabelResult(label, resolved, False, "traduction vide (ne sera pas écrite en ROM)")
    for bad in label.forbidden_forms:
        if resolved.casefold() == bad.casefold():
            return LabelResult(label, resolved, False, f"régression vers la forme interdite « {bad} »")
    return LabelResult(label, resolved, True, "ok")


def build_report(path: Path) -> IntegrityReport:
    """Construit le rapport d'intégrité pour un combined_fr.txt donné."""

    mapping, total = load_last_wins(path)
    distinct = len(mapping)
    results = [check_label(label, mapping) for label in CRITICAL_LABELS]
    return IntegrityReport(
        total_entries=total,
        distinct_offsets=distinct,
        duplicate_offsets=total - distinct,
        results=results,
    )


def _render_human(report: IntegrityReport) -> str:
    lines = [
        "Garde d'intégrité des traductions FR (combined_fr.txt)",
        f"  entrées totales   : {report.total_entries}",
        f"  offsets distincts : {report.distinct_offsets}",
        f"  doublons (last-wins): {report.duplicate_offsets}",
        f"  labels carte protégés : {len(report.results)}",
        "",
    ]
    for result in report.results:
        mark = "OK  " if result.ok else "FAIL"
        value = result.resolved if result.resolved is not None else "<absent>"
        lines.append(f"  [{mark}] 0x{result.label.offset:06X} {result.label.name:<18} → « {value} »")
        if not result.ok:
            lines.append(f"         ↳ {result.reason}")
    lines.append("")
    if report.ok:
        lines.append("✅ Aucun label carte régressé — combined_fr.txt conforme.")
    else:
        lines.append(f"❌ {len(report.failures)} label(s) régressé(s) — voir docs/20_TRANSLATION_PRESERVATION.md")
    return "\n".join(lines)


def _render_json(report: IntegrityReport) -> str:
    payload = {
        "ok": report.ok,
        "total_entries": report.total_entries,
        "distinct_offsets": report.distinct_offsets,
        "duplicate_offsets": report.duplicate_offsets,
        "labels": [
            {
                "offset": f"0x{r.label.offset:06X}",
                "name": r.label.name,
                "resolved": r.resolved,
                "ok": r.ok,
                "reason": r.reason,
            }
            for r in report.results
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_COMBINED,
        help="chemin vers combined_fr.txt (défaut : racine du dépôt)",
    )
    parser.add_argument("--json", action="store_true", help="émettre un rapport JSON machine")
    args = parser.parse_args(argv)

    if not args.file.exists():
        print(f"erreur : fichier introuvable : {args.file}", file=sys.stderr)
        return 2

    report = build_report(args.file)
    print(_render_json(report) if args.json else _render_human(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
