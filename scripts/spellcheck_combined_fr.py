#!/usr/bin/env python3
"""Spell-check the French translations in combined_fr.txt.

Parses every ``0xOFFSET: text`` line, strips game control codes
(\\n, \\l, \\p, {PLACEHOLDER}, <0xNN>), tokenizes French words and
reports the ones unknown to the French dictionary (pyspellchecker),
sorted by frequency, with sample offsets and context.

Usage:
    python3 scripts/spellcheck_combined_fr.py [--combined combined_fr.txt]
        [--whitelist scripts/spellcheck_whitelist_fr.txt] [--min-count 1]
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

LINE_RE = re.compile(r"^(0x[0-9A-Fa-f]+):\s?(.*)$")
PLACEHOLDER_RE = re.compile(r"\{[^}]*\}|<0x[0-9A-Fa-f]{2}>|\[[^\]]*\]")
BREAK_RE = re.compile(r"\\[nlp]")
# French words: letters (incl. accents) with optional internal hyphens/apostrophes
WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿŒœ]+(?:[-'’][A-Za-zÀ-ÖØ-öø-ÿŒœ]+)*")
# Elision prefixes to strip before dictionary lookup (l'ennemi -> ennemi)
ELISION_RE = re.compile(
    r"^(?:l|d|j|n|m|s|t|c|qu|jusqu|lorsqu|puisqu|quoiqu|presqu|quelqu)['’]",
    re.IGNORECASE,
)


def clean_text(text: str) -> str:
    text = BREAK_RE.sub(" ", text)
    text = PLACEHOLDER_RE.sub(" ", text)
    return text


def candidate_forms(word: str) -> list[str]:
    """Forms to try against the dictionary, most specific first."""
    forms = [word]
    stripped = ELISION_RE.sub("", word)
    if stripped != word:
        forms.append(stripped)
    # hyphenated compounds: valid if every part is valid
    return forms


def load_whitelist(path: Path) -> set[str]:
    words: set[str] = set()
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                words.add(line.lower())
    return words


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--combined", default="combined_fr.txt")
    parser.add_argument(
        "--whitelist", default="scripts/spellcheck_whitelist_fr.txt"
    )
    parser.add_argument("--min-count", type=int, default=1)
    parser.add_argument("--max-context", type=int, default=3)
    args = parser.parse_args()

    try:
        from spellchecker import SpellChecker
    except ImportError:
        print("pyspellchecker missing: python3 -m pip install pyspellchecker")
        return 2

    spell = SpellChecker(language="fr")
    whitelist = load_whitelist(Path(args.whitelist))

    unknown: dict[str, int] = defaultdict(int)
    contexts: dict[str, list[tuple[str, str]]] = defaultdict(list)

    def known(word: str) -> bool:
        lw = word.lower()
        if lw in whitelist:
            return True
        for form in candidate_forms(lw):
            # pyspellchecker normalizes curly apostrophes poorly; use straight
            form = form.replace("’", "'")
            if spell.known([form]):
                return True
            # hyphen compounds: every chunk known => known (peut-être, etc.)
            if "-" in form:
                chunks = [c for c in form.split("-") if c]
                if chunks and all(
                    spell.known([ELISION_RE.sub("", c)]) for c in chunks
                ):
                    return True
        return False

    path = Path(args.combined)
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = LINE_RE.match(raw)
        if not match:
            continue
        offset, text = match.groups()
        for word in WORD_RE.findall(clean_text(text)):
            if len(word) < 2:
                continue
            if known(word):
                continue
            unknown[word.lower()] += 1
            if len(contexts[word.lower()]) < args.max_context:
                snippet = text.replace("\\n", " ").replace("\\l", " ")
                snippet = snippet.replace("\\p", " ")
                contexts[word.lower()].append((offset, snippet[:120]))

    items = sorted(unknown.items(), key=lambda kv: (-kv[1], kv[0]))
    shown = 0
    for word, count in items:
        if count < args.min_count:
            continue
        shown += 1
        print(f"{count:5d}  {word}")
        for offset, snippet in contexts[word]:
            print(f"           {offset}: {snippet}")
    print(f"\n{shown} unknown words ({sum(unknown.values())} occurrences)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
