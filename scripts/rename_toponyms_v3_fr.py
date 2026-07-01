#!/usr/bin/env python3
"""Apply the **v3** canon of Pokemon Unbound FR place names to combined_fr.txt.

The user delivered a *third* toponym list ("Traductions des lieux v2" follow-up)
that revises a subset of the v2 names already living in ``combined_fr.txt``. This
script is a **delta** pass: it rewrites the current v2 French forms into their v3
spellings (it does **not** re-derive names from English — the v2 rename already
ran and is committed).

v2 -> v3 changes
----------------
    Rive-d'Automne   -> Rivapolis      (Fallshore City)
    Bellinbourg      -> Bélenbourg     (Bellin Town)
    Cratéria         -> Cratéris       (Crater Town)
    Épidimi          -> Épidia         (Epidimy Town)
    Bourg-Tel        -> Automnia       (Tehl Town, vowel-initial: elide "de")
    Vivillis         -> Viville        (Vivill Town / warehouse)
      Bois de Vivillis     -> Bois Vivill      (Vivill Woods)
      Entrepôt de Vivillis -> Dépôt de Viville (Vivill Warehouse)
    Polder sur Rive  -> Polderive      (Polder Town)
    Cube Sarl        -> Cube SARL      (Cube Corp.)
    Bois Lugubres    -> Boissombre     (Grim Woods, articles consumed)
    Chenal Cuivré    -> Chenal Aubrun  (Auburn Waterway)
    Champs de Magnolia -> Champs Magnolia  (Magnolia Fields)
    Forêt de Rougebois -> Forêt Carmin     (Redwood Forest; village stays Rougebois)
    Île Pleine Lune  -> Île Pleinelune (Fullmoon Island)
    Île Nouvelle Lune-> Île Nouvellune (Newmoon Island)
    Volcan Cendreux  -> Volcan Cendré  (Cinder Volcano)
    Pic Grondant     -> Mont Foudroyant(Thundercap Mountain)
    Gouffre Glacial  -> Gouffre Gelé   (Icy Hole)
    Grotte Falaise   -> Grotte Faille  (Rift Cave)
    Autoroute KBT / SES Expressway -> Autoroute RBT  (KBT Expressway)
    S.S. Marine      -> Marine         (S.S. Marine)

Names that were already correct in v2 stay untouched (Cimistral, Naville,
Antésia, Daherapolis, Gurenbourg, Somnia — incl. « Manoir Somnia » —, Cimes
Gelées, Zone de Combat, Rougebois village, Base Ombre, ...).

Note: « Cinder Volcano Depths -> Tréfonds Cendrés » has no target string —
that zone label is absent from combined_fr.txt (and the English extraction), so
there is nothing to rename.

Design mirrors ``rename_toponyms_v2_fr.py``: ordered (regex, replacement) rules
applied to the **French text only**, spaces made line-break-escape flexible via
:data:`_SEP`, longer/qualified forms before bare stems, and idempotent targets.

Usage
-----
    python3 scripts/rename_toponyms_v3_fr.py            # rewrite in place
    python3 scripts/rename_toponyms_v3_fr.py --dry-run  # report only
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COMBINED = REPO_ROOT / "languages/fr/combined_fr.txt"

_LINE_RE = re.compile(r"^(0x[0-9A-Fa-f]+:\s?)(.*)$")

# A separator between two words of a place name may be a real space OR a CFRU
# line-break escape (``\n`` newline, ``\l`` line, ``\p`` page). Every literal
# space in a rule pattern is compiled to match either form (as in the v2 pass).
_SEP = r"(?:\\[nlp]|\s)"

# Leading boundary for article cleanup: start, a non-word char, a CFRU escape
# (\n/\l/\p) or a control digit — anything but a real letter.
_LB = r"(?:(?<=\\[nlp])|(?<=[0-9])|(?<![0-9A-Za-zÀ-ÿ]))"

# The « highlight » colour control that wraps in-text proper nouns, stored
# literally in combined_fr.txt as the three tokens below (no regex specials).
_COLOR6 = r"<0xFC><0x01><0x06>"


def C(pattern: str) -> "re.Pattern[str]":
    """Compile a rule pattern, making each literal space separator-flexible."""
    return re.compile(pattern.replace(" ", _SEP))


def A(pattern: str) -> "re.Pattern[str]":
    """Compile an article-consuming rule: leading boundary + separator-flexible."""
    return re.compile(_LB + pattern.replace(" ", _SEP))


# Ordered (regex, replacement, label). Applied to the FR text of every line, in
# order. Keep qualified/article-bearing forms before bare stems.
RULES: list[tuple[re.Pattern[str], str, str]] = [
    # ── Fallshore: Rive-d'Automne -> Rivapolis (straight + curly apostrophe). ──
    (C(r"Rive-d['’]Automne"), "Rivapolis", "Fallshore -> Rivapolis"),

    # ── Bellin: Bellinbourg -> Bélenbourg. ──
    (C(r"Bellinbourg"), "Bélenbourg", "Bellin -> Bélenbourg"),

    # ── Crater: Cratéria -> Cratéris. ──
    (C(r"Cratéria"), "Cratéris", "Crater -> Cratéris"),

    # ── Epidimy: Épidimi -> Épidia (fix a stray un-elided « de Épidimi »). ──
    (C(r"de Épidimi"), "d'Épidia", "Epidimy elide de"),
    (C(r"Épidimi"), "Épidia", "Epidimy -> Épidia"),

    # ── Tehl: Bourg-Tel -> Automnia (vowel-initial: « de » elides to « d' »). ──
    (C(r"de Bourg-Tel"), "d'Automnia", "Tehl elide de"),
    (C(r"Bourg-Tel"), "Automnia", "Tehl -> Automnia"),

    # ── Vivill: Woods & Warehouse keep a qualifier; town / bare -> Viville. ──
    (C(r"Bois de Vivillis"), "Bois Vivill", "Vivill Woods"),
    (C(r"Entrepôt de Vivillis"), "Dépôt de Viville", "Vivill Warehouse"),
    (C(r"Vivillis"), "Viville", "Vivill -> Viville"),

    # ── Polder: Polder sur Rive -> Polderive. ──
    (C(r"Polder sur Rive"), "Polderive", "Polder -> Polderive"),
    # Safety net: a bare « Polder » that escaped the qualified form. The negative
    # lookahead keeps « Polderive » from re-matching its own output.
    (re.compile(r"\bPolder\b(?!ive)"), "Polderive", "Polder (bare)"),

    # ── Cube Corp.: Cube Sarl -> Cube SARL (keeps a trailing period). ──
    (C(r"Cube Sarl"), "Cube SARL", "Cube Sarl -> SARL"),

    # ── Grim Woods: Bois Lugubres -> Boissombre (consume the plural articles;
    #    « Boissombre » behaves like a proper place name). ──
    (A(r"(?:du|des) Bois Lugubres"), "de Boissombre", "Grim Woods du/des"),
    (A(r"aux Bois Lugubres"), "à Boissombre", "Grim Woods aux"),
    (A(r"(?:les|Les|le|Le|la|La) Bois Lugubres"), "Boissombre", "Grim Woods article"),
    (C(r"Bois Lugubres"), "Boissombre", "Grim Woods (bare)"),

    # ── Auburn: Chenal Cuivré -> Chenal Aubrun. ──
    (C(r"Chenal Cuivré"), "Chenal Aubrun", "Auburn -> Chenal Aubrun"),

    # ── Magnolia Fields: Champs de Magnolia -> Champs Magnolia. ──
    (C(r"Champs de Magnolia"), "Champs Magnolia", "Magnolia Fields"),

    # ── Redwood Forest: Forêt de Rougebois -> Forêt Carmin (village stays). ──
    (C(r"Forêt de Rougebois"), "Forêt Carmin", "Redwood Forest (de)"),
    (C(r"Forêt Rougebois"), "Forêt Carmin", "Redwood Forest"),

    # ── Fullmoon / Newmoon: two-word -> single contracted word. ──
    (C(r"Île Pleine Lune"), "Île Pleinelune", "Fullmoon Island"),
    (C(r"Île Nouvelle Lune"), "Île Nouvellune", "Newmoon Island"),

    # ── Cinder Volcano: Volcan Cendreux -> Volcan Cendré. ──
    (C(r"Volcan Cendreux"), "Volcan Cendré", "Cinder Volcano"),

    # ── Thundercap: Pic Grondant -> Mont Foudroyant. ──
    (C(r"Pic Grondant"), "Mont Foudroyant", "Thundercap"),

    # ── Icy Hole: Gouffre Glacial -> Gouffre Gelé. ──
    (C(r"Gouffre Glacial"), "Gouffre Gelé", "Icy Hole"),

    # ── Rift Cave: Grotte Falaise -> Grotte Faille. ──
    (C(r"Grotte Falaise"), "Grotte Faille", "Rift Cave"),

    # ── KBT / SES Expressway -> Autoroute RBT. The engine labels the road
    #    « KBT » (FR) though the English source string reads « SES Expressway »;
    #    both spellings are collapsed to the new « RBT ». Colour-coded name
    #    references « <color>KBT Expressway<color> » drop « Expressway » and
    #    elide the feminine article (« du/de la » -> « de l' Autoroute »). ──
    (C(r"du " + _COLOR6 + r"KBT Expressway"), "de l'" + _COLOR6 + "Autoroute RBT", "KBT Expressway du (colored)"),
    (C(r"de la " + _COLOR6 + r"KBT Expressway"), "de l'" + _COLOR6 + "Autoroute RBT", "KBT Expressway de-la (colored)"),
    (C(_COLOR6 + r"KBT Expressway"), _COLOR6 + "Autoroute RBT", "KBT Expressway (colored)"),
    (C(r"de la SES Expressway"), "de l'Autoroute RBT", "SES Expressway de-la"),
    (C(r"SES Expressway"), "Autoroute RBT", "SES Expressway"),
    (C(r"Autoroute SES"), "Autoroute RBT", "Autoroute SES"),
    (C(r"Autoroute KBT"), "Autoroute RBT", "Autoroute KBT"),
    # The acronym expansion: « KBT = King Borrius the Third » (left in English by
    # the pipeline) becomes « RBT = Roi Borrius Troisième » (R.B.T.).
    (C(r"King Borrius the Third"), "Roi Borrius Troisième", "KBT expansion"),
    # Safety net for any bare « KBT » (uppercase acronym never collides with a
    # French word): « «KBT» », « au-dessus de KBT », « Murs KBT »...
    (re.compile(r"\bKBT\b"), "RBT", "KBT (bare)"),

    # ── S.S. Marine -> Marine. ──
    (re.compile(r"S\.S\.\s?Marine"), "Marine", "S.S. Marine"),
]


def transform(text: str, counts: dict[str, int]) -> str:
    for pattern, repl, label in RULES:
        new, n = pattern.subn(repl, text)
        if n:
            counts[label] = counts.get(label, 0) + n
            text = new
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_COMBINED)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    src = args.file.read_text(encoding="utf-8")
    counts: dict[str, int] = {}
    out_lines: list[str] = []
    changed_lines = 0
    for raw in src.splitlines(keepends=True):
        nl = ""
        line = raw
        if line.endswith("\n"):
            nl, line = "\n", line[:-1]
        m = _LINE_RE.match(line)
        if not m:
            out_lines.append(raw)
            continue
        prefix, body = m.group(1), m.group(2)
        new_body = transform(body, counts)
        if new_body != body:
            changed_lines += 1
        out_lines.append(prefix + new_body + nl)

    total = sum(counts.values())
    print(f"v3 toponym rename: {total} substitutions across {changed_lines} lines")
    for label in sorted(counts, key=lambda k: -counts[k]):
        print(f"  {counts[label]:4d}  {label}")

    if args.dry_run:
        print("(dry-run: file not written)")
        return 0

    args.file.write_text("".join(out_lines), encoding="utf-8")
    print(f"✓ wrote {args.file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
