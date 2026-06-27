#!/usr/bin/env python3
"""Localise English Pokémon names left inside French dialogue text.

The EN→FR translator inherited the wording of each dialogue but, when an
NPC mentions a species by name, the English species name was frequently
left untranslated (``Tu as un beau Charizard !``). This reads as broken
French because every species has an official French name
(``Charizard`` → ``Dracaufeu``).

This script walks ``combined_fr.txt`` (the live FR translation source)
and, for every entry, replaces each English species name that appears as
a whole word with its French equivalent, using the authoritative map in
``data/pokemon_names_en_fr.json``.

Matching is conservative on purpose:

* **Case-sensitive, whole-word.** Species names are always capitalised in
  dialogue; matching case-sensitively with non-alphanumeric boundaries
  avoids hitting common lowercase words.
* **Tokens are never touched.** Brace placeholders (``{B_ATK_NAME…}``)
  and hex control codes (``<0xFD><0x10>``) are masked out before
  replacement, so a name is never injected inside a control sequence.
* **Identical names are skipped.** ~150 species share the same name in
  both languages (``Pikachu``, ``Arbok``…); they are no-ops.

Alert when the swap hurts the dialogue (the ticket's core requirement)
----------------------------------------------------------------------
French species names are often longer than their English source
(``Snorlax`` → ``Ronflex`` is shorter, but ``Gengar`` → ``Ectoplasma``
is far longer), and a vowel→consonant change can break an inherited
elision (``d'Oddish`` → ``de Mystherbe``). The name is always translated,
but the script also raises an alert when the substitution affects the
dialogue negatively, so the whole dialogue can be corrected by hand:

* **Overflow** — every visual line is re-measured with the FireRed
  glyph-width metrics (:mod:`src.core.dialogue_linewrap`); an entry is
  flagged when a line that fit before now exceeds
  ``DEFAULT_MAX_LINE_WIDTH`` (192 px).
* **Broken elision** — an entry is flagged when an elided article ends up
  glued to a consonant-initial French name (``d'Mystherbe``).

Alerts are written to ``output/reports/pokemon_name_overflow_fr.md``.

Usage
-----
    python3 scripts/translate_pokemon_names_in_dialogue_fr.py            # dry-run report
    python3 scripts/translate_pokemon_names_in_dialogue_fr.py --apply    # rewrite combined_fr.txt
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.dialogue_linewrap import (  # noqa: E402
    DEFAULT_MAX_LINE_WIDTH,
    line_width,
)

COMBINED = ROOT / "languages/fr/combined_fr.txt"
NAME_MAP = ROOT / "data" / "pokemon_names_en_fr.json"
REPORT = ROOT / "output" / "reports" / "pokemon_name_overflow_fr.md"

# English species names that collide with ordinary French/English words or
# are too ambiguous to swap safely as a bare capitalised token. Kept empty
# by default; add a name here if a false positive is ever observed.
DENYLIST: set = set()

# Organisation / gang proper nouns in Unbound are built from a species name
# (the antagonist gangs). They are named entities, not "a character mentioning
# a Pokémon", so the species word inside them must stay verbatim. The gang name
# shows up in two forms: the English ``Black Ferrothorn`` and the French
# ``Ferrothorn Noir`` / ``L'Emboar Noir``. A match is skipped when it carries
# one of these guard affixes.
PROTECTED_PREFIXES: Tuple[str, ...] = ("Black ",)
PROTECTED_SUFFIXES: Tuple[str, ...] = (" Noir",)

# Matches a brace placeholder ({B_ATK_NAME_WITH_PREFIX}) or a hex control
# token (<0xFD>). Replacement never runs inside these spans.
_TOKEN_RE = re.compile(r"\{[^}]*\}|<0x[0-9A-Fa-f]{2}>")


def load_name_map() -> Dict[str, str]:
    """Return the EN→FR map limited to names that actually change."""
    data = json.loads(NAME_MAP.read_text(encoding="utf-8"))
    names = data["pokemon_names"]
    return {
        en: fr
        for en, fr in names.items()
        if en != fr and en not in DENYLIST
    }


def build_matcher(name_map: Dict[str, str]) -> re.Pattern:
    """One case-sensitive, whole-word alternation over every EN name.

    Names are sorted longest-first so a longer name (``Charizard``) wins
    over any shorter prefix before the regex engine backtracks. Boundaries
    are non-alphanumeric so ``Onix`` never fires inside ``Onixome``.
    """
    alternatives = "|".join(
        re.escape(en) for en in sorted(name_map, key=len, reverse=True)
    )
    # Negative look-arounds keep gang proper nouns ("Black Ferrothorn",
    # "Ferrothorn Noir") untouched: a look-behind per fixed-width prefix and a
    # look-ahead per suffix.
    behind = "".join(f"(?<!{re.escape(p)})" for p in PROTECTED_PREFIXES)
    ahead = "".join(f"(?!{re.escape(s)})" for s in PROTECTED_SUFFIXES)
    return re.compile(
        rf"(?<![A-Za-z0-9]){behind}(?:{alternatives})(?![A-Za-z0-9]){ahead}"
    )


def translate_segment(
    text: str, matcher: re.Pattern, name_map: Dict[str, str], counts: Dict[str, int]
) -> str:
    """Translate names in ``text`` while leaving every token span intact."""
    out: List[str] = []
    pos = 0
    for token in _TOKEN_RE.finditer(text):
        out.append(_translate_plain(text[pos : token.start()], matcher, name_map, counts))
        out.append(token.group(0))  # token verbatim
        pos = token.end()
    out.append(_translate_plain(text[pos:], matcher, name_map, counts))
    return "".join(out)


def _translate_plain(
    chunk: str, matcher: re.Pattern, name_map: Dict[str, str], counts: Dict[str, int]
) -> str:
    def repl(m: re.Match) -> str:
        en = m.group(0)
        counts[en] = counts.get(en, 0) + 1
        return name_map[en]

    return matcher.sub(repl, chunk)


# --- width measurement -----------------------------------------------------
# combined_fr.txt keeps text in a high-level form (``{COLOR}Ç``, ``{STR_VAR_1}``,
# ``\p``/``\l``/``\n`` breaks). The FireRed glyph metrics in dialogue_linewrap
# measure *rendered* text, so the high-level tokens must be reduced to what the
# player actually sees before measuring, or every line reads far too wide.
_COLOR_RE = re.compile(r"\{COLOR\}.")  # control code + its 1-char palette arg
# Tokens that expand to runtime text (names, vars, items…) render at a variable
# width; the linewrap metrics model that as a single <0xFD> buffer glyph.
_BUFFER_RE = re.compile(
    r"\{[^}]*(?:NAME|PLAYER|RIVAL|STR_VAR|STRING|VAR|ITEM|MOVE|ABILITY|TEAM"
    r"|OPPONENT|TRAINER|DYNAMIC|UNKNOWN|VERSION)[^}]*\}|\{FD[0-9A-Fa-f]{2}\}"
)
_BRACE_RE = re.compile(r"\{[^}]*\}")  # remaining control tokens render nothing
_BREAK_RE = re.compile(r"\\[npl]")  # \n, \p, \l all start a new visual line


def line_pixel_widths(body: str) -> List[int]:
    """Rendered pixel width of each visual line of a combined_fr.txt body.

    A heuristic, not a byte-exact renderer: control tokens are dropped,
    runtime buffers counted as one variable-width glyph, and every structural
    break (``\\n``/``\\p``/``\\l``) splits a visual line. It is consistent
    before and after the name swap, so width *regressions* are reliable.
    """
    s = _COLOR_RE.sub("", body)
    s = _BUFFER_RE.sub("<0xFD>", s)
    s = _BRACE_RE.sub("", s)
    s = _BREAK_RE.sub("\n", s)
    return [line_width(line) for line in s.split("\n")]


def overflow_regression(before: str, after: str) -> Tuple[bool, List[int]]:
    """Detect a line that fit before the swap but overflows the box after it.

    Returns ``(regressed, widths_after)``. Comparing per line (the name swap
    never adds or removes a break, so the lists align) isolates the overflow
    *caused by the longer French name* from lines that were already wide.
    """
    bw = line_pixel_widths(before)
    aw = line_pixel_widths(after)
    regressed = any(
        b <= DEFAULT_MAX_LINE_WIDTH < a for b, a in zip(bw, aw)
    )
    return regressed, aw


# A vowel sound (incl. mute ``h`` and accented vowels) lets a French article
# elide: ``d'Oddish`` is valid, ``de Mystherbe`` is not. ``h``/``y`` count as
# vowel-initial for elision purposes.
_VOWELS = set("AEIOUYHÉÈÊËÀÂÎÏÔÛÜaeiouyhàâéèêëîïôûü")
_ELIDERS = "dlnjmtscqu"  # articles/pronouns that elide before a vowel sound


def _starts_vowel(word: str) -> bool:
    return bool(word) and word[0] in _VOWELS


def build_elision_matcher(name_map: Dict[str, str]) -> re.Pattern:
    """Match an elided article glued to an FR name that breaks the elision.

    Only French names whose *English* source was vowel-initial but whose
    French form is consonant-initial are risky: the inherited apostrophe
    (``d'Oddish``) becomes ungrammatical after the swap (``d'Mystherbe`` —
    should read ``de Mystherbe``).
    """
    risky = sorted(
        (fr for en, fr in name_map.items() if _starts_vowel(en) and not _starts_vowel(fr)),
        key=len,
        reverse=True,
    )
    if not risky:
        return re.compile(r"(?!x)x")  # matches nothing
    alt = "|".join(re.escape(fr) for fr in risky)
    return re.compile(rf"[{_ELIDERS}]['’](?:{alt})(?![A-Za-z0-9])")


def process(
    lines: List[str],
    name_map: Dict[str, str],
    matcher: re.Pattern,
    elision_matcher: re.Pattern,
) -> Tuple[List[str], Dict[str, int], List[dict]]:
    new_lines: List[str] = []
    counts: Dict[str, int] = {}
    alerts: List[dict] = []

    for raw in lines:
        if ":" not in raw:
            new_lines.append(raw)
            continue
        offset, sep, text = raw.partition(":")
        # Preserve the single space after the colon used throughout the file.
        leading = text[: len(text) - len(text.lstrip(" "))]
        body = text[len(leading):]
        # Bare species-name cells (the fixed species-name table / list dumps,
        # e.g. ``Vivillon`` on its own line) are not dialogue and are owned by
        # the dedicated fixed-table patches — out of scope here.
        if body.strip() in name_map:
            new_lines.append(raw)
            continue
        translated = translate_segment(body, matcher, name_map, counts)
        if translated == body:
            new_lines.append(raw)
            continue

        # The name is always translated (that is the point); when the swap
        # affects the dialogue negatively we still translate it but raise an
        # alert so the whole dialogue can be corrected by hand.
        reasons: List[str] = []
        regressed, widths_after = overflow_regression(body, translated)
        if regressed:
            reasons.append("overflow")
        if elision_matcher.search(translated):
            reasons.append("elision")  # broken « d'Mystherbe » etc.
        if reasons:
            alerts.append(
                {
                    "offset": offset,
                    "reasons": reasons,
                    "before": body,
                    "after": translated,
                    "widths_after": widths_after,
                    "max_width": DEFAULT_MAX_LINE_WIDTH,
                }
            )
        new_lines.append(f"{offset}{sep}{leading}{translated}")

    return new_lines, counts, alerts


_REASON_LABEL = {
    "overflow": "débordement de ligne (cadre dépassé)",
    "elision": "élision cassée (ex. « d'Mystherbe » → « de Mystherbe »)",
}


def write_report(alerts: List[dict], total_changed: int, counts: Dict[str, int]) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    n_over = sum(1 for a in alerts if "overflow" in a["reasons"])
    n_elide = sum(1 for a in alerts if "elision" in a["reasons"])
    lines = [
        "# Alertes : noms de Pokémon traduits affectant le dialogue",
        "",
        f"- Entrées de dialogue modifiées : **{total_changed}**",
        f"- Noms distincts traduits : **{len(counts)}**",
        f"- Entrées à corriger entièrement : **{len(alerts)}** "
        f"({n_over} débordement, {n_elide} élision)",
        f"- Budget largeur ligne : **{DEFAULT_MAX_LINE_WIDTH} px**",
        "",
    ]
    if not alerts:
        lines.append("✅ Aucun problème : toutes les substitutions tiennent dans le cadre.")
    else:
        lines.append(
            "⚠️ La traduction du nom affecte négativement les entrées ci-dessous. "
            "Le dialogue complet doit être corrigé à la main (re-balancer les "
            "retours à la ligne et/ou réparer l'élision de l'article)."
        )
        lines.append("")
        for a in alerts:
            tags = ", ".join(_REASON_LABEL[r] for r in a["reasons"])
            lines.append(f"## `{a['offset']}` — {tags}")
            lines.append(f"- largeurs (px) : {a['widths_after']} (max {a['max_width']})")
            lines.append("- avant : " + a["before"].replace("\\n", " ⏎ "))
            lines.append("- après : " + a["after"].replace("\\n", " ⏎ "))
            lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="write changes back to combined_fr.txt"
    )
    args = parser.parse_args()

    name_map = load_name_map()
    matcher = build_matcher(name_map)
    elision_matcher = build_elision_matcher(name_map)
    lines = COMBINED.read_text(encoding="utf-8").splitlines()

    new_lines, counts, alerts = process(lines, name_map, matcher, elision_matcher)
    total_changed = sum(
        1 for old, new in zip(lines, new_lines) if old != new
    )

    write_report(alerts, total_changed, counts)

    print(f"Pokémon names translated : {sum(counts.values())} occurrence(s)")
    print(f"Distinct species localised: {len(counts)}")
    print(f"Dialogue entries modified : {total_changed}")
    print(f"Alerts (overflow/elision) : {len(alerts)} -> {REPORT}")
    top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:15]
    if top:
        print("Top names:")
        for en, c in top:
            print(f"  {c:4d}  {en} -> {name_map[en]}")

    if args.apply:
        COMBINED.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        print(f"\nApplied to {COMBINED}")
    else:
        print("\n(dry-run; pass --apply to write combined_fr.txt)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
