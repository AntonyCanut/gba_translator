#!/usr/bin/env python3
"""Apply the **v2** canon of Pokemon Unbound FR place names to combined_fr.txt.

The user delivered a v2 toponym list (ticket "Traductions des lieux v2") that
supersedes the previous canon (Bellinville / Tarmigan / Ville Blizzard / Dehara
/ Ville Portuaire / Cube Corp ...). Each English location now maps to exactly
one French rendering — invented proper nouns (Cimistral, Daherapolis, Somnia,
Antesia -> Antésia, Naville, ...) plus a handful of descriptive standardisations
(Battle Frontier -> Zone de Combat, Crystal Peak -> Pic Cristal, ...).

Design
------
* Rules are an **ordered** list of (pattern, replacement). Longer / article-
  bearing forms run before the bare stem so "Bois Vivill" becomes
  "Bois de Vivillis" before the bare "Vivill" -> "Vivillis" rule fires.
* Replacement runs **only on the French text** of each line (after the
  ``0x<hex>: `` prefix), never on the offset.
* **Homonym guards**: the move « Blizzard », the flower « magnolias », the
  common nouns « cratère / faille / hauteurs » and the NPC « Cootes » are not
  touched — rules only match the multi-word location forms, never the bare
  ambiguous stem.
* **Idempotent**: every target form already contains no source stem, so a second
  run is a no-op (the bare rules use a negative lookahead to avoid re-matching
  their own output, e.g. ``Vivill(?!is)``).

Usage
-----
    python3 scripts/rename_toponyms_v2_fr.py            # rewrite in place
    python3 scripts/rename_toponyms_v2_fr.py --dry-run  # report only
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COMBINED = REPO_ROOT / "languages/fr/combined_fr.txt"

_LINE_RE = re.compile(r"^(0x[0-9A-Fa-f]+:\s?)(.*)$")

# A separator between two words of a place name may be a real space OR a CFRU
# line-break escape (``\n`` newline, ``\l`` line, ``\p`` page) — e.g. the file
# stores "Ville\nBlizzard" and "Forêt\nLugubre". Every literal space in a rule
# pattern is therefore compiled to match either form, so split names are caught.
_SEP = r"(?:\\[nlp]|\s)"


def C(pattern: str) -> "re.Pattern[str]":
    """Compile a rule pattern, making each literal space separator-flexible."""
    return re.compile(pattern.replace(" ", _SEP))


# Ordered (regex, replacement, label). Each regex is applied to the FR text of
# every line, in order. Keep multi-word forms before bare stems.
RULES: list[tuple[re.Pattern[str], str, str]] = [
    # ── Antisis -> Antésia (city / port / sewers). Specific forms first. ──
    (C(r"\bde la Ville d['’]Antisis"), "d'Antésia", "Antisis de-la"),
    (C(r"\bà la Ville d['’]Antisis"), "à Antésia", "Antisis a-la"),
    (C(r"\b[Ll]a Ville d['’]Antisis"), "Antésia", "Antisis la"),
    (C(r"Ville d['’]Antisis"), "Antésia", "Antisis City"),
    (C(r"Port d['’]Antisis"), "Port d'Antésia", "Antisis Port"),
    (C(r"Égouts d['’]Antisis"), "Égouts d'Antésia", "Antisis Sewers"),
    (C(r"d['’]Antisis"), "d'Antésia", "Antisis (elided)"),
    (C(r"Antisis"), "Antésia", "Antisis (bare)"),

    # ── Blizzard City -> Cimistral (consume the feminine article). ──
    (C(r"\bde la Ville Blizzard"), "de Cimistral", "Blizzard de-la"),
    (C(r"\bà la Ville Blizzard"), "à Cimistral", "Blizzard a-la"),
    (C(r"\b[Ll]a Ville Blizzard"), "Cimistral", "Blizzard la"),
    (C(r"Ville de Blizzard"), "Cimistral", "Blizzard ville-de"),
    (C(r"Ville Blizzard"), "Cimistral", "Blizzard City"),
    (C(r"Blizzard City"), "Cimistral", "Blizzard City (EN)"),

    # ── Fallshore City -> Rive-d'Automne. ──
    (C(r"\b[Ll]a Ville de Fallshore"), "Rive-d'Automne", "Fallshore la-ville"),
    (C(r"Ville de Fallshore"), "Rive-d'Automne", "Fallshore ville-de"),
    (C(r"Fallshore City"), "Rive-d'Automne", "Fallshore City (EN)"),
    (C(r"Fallshore"), "Rive-d'Automne", "Fallshore (bare)"),

    # ── Epidimy Town -> Épidimi. ──
    (C(r"\bde la Ville d['’]Epidimy"), "d'Épidimi", "Epidimy de-la"),
    (C(r"\bà la Ville d['’]Epidimy"), "à Épidimi", "Epidimy a-la"),
    (C(r"\b[Ll]a Ville d['’]Epidimy"), "Épidimi", "Epidimy la"),
    (C(r"Ville d['’]Epidimy"), "Épidimi", "Epidimy ville"),
    (C(r"Epidimy Town"), "Épidimi", "Epidimy Town (EN)"),
    (C(r"Epidimy"), "Épidimi", "Epidimy (bare)"),

    # ── Tehl Town -> Bourg-Tel. ──
    (C(r"\bde la Ville de Tehl"), "de Bourg-Tel", "Tehl de-la"),
    (C(r"\bà la Ville de Tehl"), "à Bourg-Tel", "Tehl a-la"),
    (C(r"\b[Ll]a Ville de Tehl"), "Bourg-Tel", "Tehl la"),
    (C(r"Ville de Tehl"), "Bourg-Tel", "Tehl ville-de"),
    (C(r"Tehl Town"), "Bourg-Tel", "Tehl Town (EN)"),
    # No leading \b: "Tehl" can abut a line-break escape ("\lTehl"), whose
    # trailing letter would defeat \b. "Tehl" is unique enough to need only the
    # trailing boundary.
    (C(r"Tehl\b"), "Bourg-Tel", "Tehl (bare)"),

    # ── Dehara City -> Daherapolis (drop "Ville de" like the other cities). ──
    (C(r"\bde la Ville de Dehara"), "de Daherapolis", "Dehara de-la"),
    (C(r"\bà la Ville de Dehara"), "à Daherapolis", "Dehara a-la"),
    (C(r"\b[Ll]a Ville de Dehara"), "Daherapolis", "Dehara la"),
    (C(r"Ville de Dehara"), "Daherapolis", "Dehara ville-de"),
    (C(r"Dehara City"), "Daherapolis", "Dehara City (EN)"),
    (C(r"Dehara"), "Daherapolis", "Dehara (bare)"),

    # ── Bellin Town -> Bellinbourg. ──
    (C(r"Bourg Bellin\b"), "Bellinbourg", "Bellin bourg-form"),
    (C(r"Bellin Town"), "Bellinbourg", "Bellin Town (EN)"),
    (C(r"Bellinville"), "Bellinbourg", "Bellinville"),

    # ── Crater Town -> Cratéria (only the multi-word location form). ──
    (C(r"Bourg Cratère"), "Cratéria", "Crater Town"),
    (C(r"Crater Town"), "Cratéria", "Crater Town (EN)"),

    # ── Frozen Heights -> Cimes Gelées. ──
    (C(r"Hauteurs Gelées"), "Cimes Gelées", "Frozen Heights"),
    (C(r"Frozen Heights"), "Cimes Gelées", "Frozen Heights (EN)"),

    # ── Tarmigan Town / Mansion -> Somnia / Manoir de Somnia. ──
    (C(r"Manoir de Tarmigan"), "Manoir de Somnia", "Tarmigan Mansion"),
    # Old town form "Tarmiganville" -> "Somnia" (not "Somniaville").
    (C(r"Tarmiganville"), "Somnia", "Tarmiganville"),
    (C(r"Tarmigan Town"), "Somnia", "Tarmigan Town (EN)"),
    (C(r"Tarmigan"), "Somnia", "Tarmigan (bare)"),

    # ── Gurun Town -> Gurenbourg. ──
    (C(r"Bourg Gurun"), "Gurenbourg", "Gurun bourg-form"),
    (C(r"Gurun Town"), "Gurenbourg", "Gurun Town (EN)"),
    (C(r"Gurun"), "Gurenbourg", "Gurun (bare)"),

    # ── Vivill -> Vivillis (woods / warehouse keep their qualifier). ──
    (C(r"Bois de Vivill\b"), "Bois de Vivillis", "Vivill Woods (de)"),
    (C(r"Bois Vivill\b"), "Bois de Vivillis", "Vivill Woods"),
    (C(r"Entrepôt de Vivill\b"), "Entrepôt de Vivillis", "Vivill Warehouse"),
    (C(r"Entrepôt Vivill\b"), "Entrepôt de Vivillis", "Vivill Warehouse (2)"),
    (C(r"Bourg Vivill\b"), "Vivillis", "Vivill Town"),
    # Guard the Pokémon « Vivillon »/« Vivillons » (not the town Vivill).
    (C(r"Vivill(?!is|on)"), "Vivillis", "Vivill (bare)"),

    # ── Seaport City -> Naville. ──
    (C(r"\bde la Ville Portuaire"), "de Naville", "Seaport de-la"),
    (C(r"\bà la Ville Portuaire"), "à Naville", "Seaport a-la"),
    (C(r"\b[Ll]a Ville Portuaire"), "Naville", "Seaport la"),
    (C(r"Ville Portuaire"), "Naville", "Seaport (Ville Portuaire)"),
    (C(r"Port-en-mer"), "Naville", "Seaport (Port-en-mer)"),
    (C(r"Seaport City"), "Naville", "Seaport City (EN)"),

    # ── Polder Town -> Polder sur Rive. ──
    (C(r"Bourg Polder"), "Polder sur Rive", "Polder Town"),
    (C(r"Polder Town"), "Polder sur Rive", "Polder Town (EN)"),
    (C(r"Polder(?! sur Rive)\b"), "Polder sur Rive", "Polder (bare)"),

    # ── Magnolia Town -> Magnolia ; Magnolia Fields -> Champs de Magnolia. ──
    (C(r"Champs Magnolia"), "Champs de Magnolia", "Magnolia Fields"),
    (C(r"Magnolia Fields"), "Champs de Magnolia", "Magnolia Fields (EN)"),
    (C(r"Bourg Magnolia"), "Magnolia", "Magnolia Town"),

    # ── Redwood Village/Forest -> Rougebois / Forêt de Rougebois. ──
    (C(r"Forêt Séquoia"), "Forêt de Rougebois", "Redwood Forest"),
    (C(r"Redwood Forest"), "Forêt de Rougebois", "Redwood Forest (EN)"),
    (C(r"Village Séquoia"), "Rougebois", "Redwood Village"),
    (C(r"Redwood Village"), "Rougebois", "Redwood Village (EN)"),
    (C(r"Bois-Rouge"), "Rougebois", "Redwood (Bois-Rouge)"),
    (C(r"Séquoia\b"), "Rougebois", "Redwood (Séquoia bare)"),

    # ── Cube Corp. -> Cube Sarl. ──
    (C(r"Cube Corp\."), "Cube Sarl.", "Cube Corp (dotted)"),
    (C(r"Cube Corp\b"), "Cube Sarl", "Cube Corp"),

    # ── Battle Frontier -> Zone de Combat. ──
    (C(r"Battle Frontier"), "Zone de Combat", "Battle Frontier (EN)"),

    # ── Thundercap Mountain -> Pic Grondant. ──
    (C(r"Mont Foudroyant"), "Pic Grondant", "Thundercap (Mont Foudroyant)"),
    (C(r"Thundercap Mt\.?"), "Pic Grondant", "Thundercap Mt (EN)"),
    (C(r"Thundercap Mountain"), "Pic Grondant", "Thundercap Mountain (EN)"),
    (C(r"Thundercap"), "Pic Grondant", "Thundercap (bare EN)"),

    # ── Icy Hole -> Gouffre Glacial. ──
    (C(r"Trou Glacé"), "Gouffre Glacial", "Icy Hole (Trou Glacé)"),
    (C(r"Icy Hole"), "Gouffre Glacial", "Icy Hole (EN)"),

    # ── Rift Cave -> Grotte Falaise. ──
    (C(r"Grotte Faille"), "Grotte Falaise", "Rift Cave"),
    (C(r"Rift Cave"), "Grotte Falaise", "Rift Cave (EN)"),

    # ── Crystal Peak -> Pic Cristal (standardise stragglers). ──
    (C(r"Crystal Peak"), "Pic Cristal", "Crystal Peak (EN)"),

    # ── Icicle Cave -> Grotte Glaçon. ──
    (C(r"Icicle Cave"), "Grotte Glaçon", "Icicle Cave (EN)"),
    (C(r"Grotte Glaçon"), "Grotte Glaçon", "Icicle Cave (noop)"),

    # ── Valley Cave -> Grotte Vallon. ──
    (C(r"Valley Cave"), "Grotte Vallon", "Valley Cave (EN)"),

    # ── Cinder Volcano Depths -> Gouffre Cendreux. ──
    (C(r"Cinder Volcano Depths"), "Gouffre Cendreux", "Cinder Depths (EN)"),
    (C(r"Profondeurs du Volcan Cendreux"), "Gouffre Cendreux", "Cinder Depths (FR)"),

    # ── Auburn Waterway -> Chenal Cuivré. ──
    (C(r"Voie d['’]Eau Auburn"), "Chenal Cuivré", "Auburn Waterway"),
    (C(r"Auburn Waterway"), "Chenal Cuivré", "Auburn Waterway (EN)"),

    # ── Cootes Bog -> Marais Fulica (guard the NPC « Cootes »). ──
    (C(r"Marais de Cootes"), "Marais Fulica", "Cootes Bog (de)"),
    (C(r"Marais Cootes"), "Marais Fulica", "Cootes Bog"),
    (C(r"Cootes Bog"), "Marais Fulica", "Cootes Bog (EN)"),

    # ── Grim Woods -> Bois Lugubres (gender shifts Forêt fem -> Bois masc). ──
    (C(r"\bde la Forêt Lugubres?"), "des Bois Lugubres", "Grim Woods de-la"),
    (C(r"\bà la Forêt Lugubres?"), "aux Bois Lugubres", "Grim Woods a-la"),
    (C(r"\b[Ll]a Forêt Lugubres?"), "les Bois Lugubres", "Grim Woods la"),
    (C(r"Forêt Lugubres?"), "Bois Lugubres", "Grim Woods (Forêt Lugubre)"),
    (C(r"Grim Woods"), "Bois Lugubres", "Grim Woods (EN)"),

    # ── Fullmoon / Newmoon Island labels. ──
    (C(r"Île de la Lune"), "Île Pleine Lune", "Fullmoon Island"),
    (C(r"Fullmoon Island"), "Île Pleine Lune", "Fullmoon Island (EN)"),
    (C(r"Île du Croissant"), "Île Nouvelle Lune", "Newmoon Island"),
    (C(r"Newmoon Island"), "Île Nouvelle Lune", "Newmoon Island (EN)"),

    # ── Misc English stragglers that are pure descriptive translations. ──
    (C(r"Flower Paradise"), "Paradis Floral", "Flower Paradise (EN)"),
    (C(r"Frozen Forest"), "Forêt Gelée", "Frozen Forest (EN)"),
    (C(r"Frost Mountain"), "Mont Givre", "Frost Mountain (EN)"),
    (C(r"Great Desert"), "Grand Désert", "Great Desert (EN)"),
    (C(r"Underground Pass"), "Passage Souterrain", "Underground Pass (EN)"),
    (C(r"Ruins of Void"), "Ruines du Néant", "Ruins of Void (EN)"),
    (C(r"Lost Tunnel"), "Tunnel Perdu", "Lost Tunnel (EN)"),
    (C(r"Victory Road"), "Route Victoire", "Victory Road (EN)"),
    (C(r"Tomb of Borrius"), "Tombeau de Borrius", "Tomb of Borrius (EN)"),
    (C(r"Distortion World"), "Monde Distorsion", "Distortion World (EN)"),
]


# ── Article cleanup ──────────────────────────────────────────────────────────
# City proper nouns never take a French article. After the main rules drop the
# "Ville …" noun, an orphan article can remain when it was prefixed by a CFRU
# escape / control glyph (e.g. "\nla Ville d'Antisis" -> "\nla Antésia", or the
# control-prefixed "9La Ville d'Epidimy" -> "9La Épidimi") that a plain \b never
# anchored. This pass strips the orphan article, with proper elision before a
# vowel-initial name. Geographic features (Grotte/Mont/Pic/Marais/Île/Bois…) are
# deliberately excluded — they legitimately take « la/le/les ».
_CITY_VOWEL = "Antésia|Épidimi"
_CITY_CONS = (
    "Naville|Bourg-Tel|Cimistral|Cratéria|Daherapolis|Somnia|Rougebois|"
    "Gurenbourg|Bellinbourg|Vivillis|Polder sur Rive"
)
# Leading boundary: start, a non-word char, a CFRU escape (\n/\l/\p) or a
# control digit — anything but a real letter (so "scala Cimistral" is safe).
_LB = r"(?:(?<=\\[nlp])|(?<=[0-9])|(?<![0-9A-Za-zÀ-ÿ]))"

CLEANUP: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(_LB + r"de" + _SEP + r"la" + _SEP + rf"({_CITY_VOWEL})"), r"d'\1", "la-cleanup de+vowel"),
    (re.compile(_LB + r"à" + _SEP + r"la" + _SEP + rf"({_CITY_VOWEL})"), r"à \1", "la-cleanup à+vowel"),
    (re.compile(_LB + r"de" + _SEP + r"la" + _SEP + rf"({_CITY_CONS})"), r"de \1", "la-cleanup de+cons"),
    (re.compile(_LB + r"à" + _SEP + r"la" + _SEP + rf"({_CITY_CONS})"), r"à \1", "la-cleanup à+cons"),
    (re.compile(_LB + r"[Ll]a" + _SEP + rf"({_CITY_VOWEL}|{_CITY_CONS})"), r"\1", "la-cleanup bare"),
]


def transform(text: str, counts: dict[str, int]) -> str:
    for pattern, repl, label in RULES:
        new, n = pattern.subn(repl, text)
        if n:
            counts[label] = counts.get(label, 0) + n
            text = new
    for pattern, repl, label in CLEANUP:
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
    print(f"v2 toponym rename: {total} substitutions across {changed_lines} lines")
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
