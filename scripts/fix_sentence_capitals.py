#!/usr/bin/env python3
"""Auto-fix sentence capitalization in combined_fr.txt.

Rules applied:
1. After . ! ? followed by any combination of \\n, \\p, \\l tokens, the next
   visible French letter must be uppercase (ignoring variable tokens {VAR}).
   Exception: . followed by linebreaks when the preceding word is a known
   abbreviation (Spe., Att., Def., K.O., Exp., etc.).

2. Entries where the first non-token character is a subject pronoun (je, tu,
   il, elle, on, nous, vous, ils, elles) are capitalized at the start.

Usage:
    python3 scripts/fix_sentence_capitals.py [--dry-run]
    python3 scripts/fix_sentence_capitals.py --dry-run   # preview only
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMBINED = ROOT / "combined_fr.txt"

# ---------------------------------------------------------------------------
# Character sets
# ---------------------------------------------------------------------------
FR_LOWER = "a-z\xe0\xe2\xe4\xe9\xe8\xea\xeb\xee\xef\xf4\xf9\xfb\xfc\xe7œ"
FR_LOWER_RE = re.compile("[" + FR_LOWER + "]")

# Linebreak tokens as they appear literally in the file: \n  \p  \l
LINEBREAK = r"(?:\\[npl])+"

# Sentence-ending punctuation followed by linebreaks then a lowercase letter
# Groups: (punct)(linebreaks)(first_lower_letter)
AFTER_PUNCT = re.compile(r"([.!?])(" + LINEBREAK + r")([" + FR_LOWER + r"])")

# Variable / control tokens.
# {COLOR}X is a two-part token: the named part {COLOR} plus exactly one byte
# (the color index), so we match them together with r"\{COLOR\}.".
TOKEN_RE = re.compile(r"\{COLOR\}.|<0x[0-9A-Fa-f]{2}>|\{[^}]+\}")

# Garbage / binary entry indicators - skip these lines entirely
GARBAGE_RE = re.compile(r"[%♀♂\xb7]")

# ---------------------------------------------------------------------------
# Abbreviation protection
# ---------------------------------------------------------------------------
ABBREV_WORDS = {
    # Pokemon stat abbreviations
    "Spe", "Sp\xe9", "Sp", "Att", "D\xe9f", "D\xe9fense",
    # Status / combat
    "K.O", "K",
    # Exp / PP / PV
    "Exp", "EXP", "PP", "PV", "PS",
    # Company / proper
    "Corp", "Inc", "Ltd",
    # Geographic compass
    "N", "S", "E", "O",
    # Common French
    "etc", "Prof", "Mme", "Mr", "Dr",
    # CS/HM
    "CS", "cs",
}

_LAST_WORD_RE = re.compile(r"([a-zA-Z\xc0-\xff.]+)$")


def _is_abbreviation_before_dot(text, dot_pos):
    """Return True if the '.' at dot_pos ends an abbreviation."""
    before = text[:dot_pos]
    # Ellipsis: ".." or "..." before this dot
    if dot_pos > 0 and text[dot_pos - 1] == ".":
        return True
    # Strip tokens and linebreak codes, then find last word
    clean = TOKEN_RE.sub(" ", before)
    clean = re.sub(r"\\[npl]|\s", " ", clean).rstrip()
    m = _LAST_WORD_RE.search(clean)
    if not m:
        return False
    last_word = m.group(1).rstrip(".")
    # Remove leading contraction (d', l', etc.) - handle both curly and ASCII
    last_word = re.split(r"['‘’]", last_word)[-1]
    return last_word in ABBREV_WORDS or (last_word.isupper() and len(last_word) <= 4)


def fix_after_punctuation(text):
    """Capitalize the letter after sentence-ending punctuation + linebreaks."""
    changes = []
    result = list(text)
    for m in reversed(list(AFTER_PUNCT.finditer(text))):
        punct = m.group(1)
        char_pos = m.start(3)
        lower = m.group(3)
        upper = lower.upper()
        if upper == lower:
            continue
        # For '.': protect abbreviations
        if punct == "." and _is_abbreviation_before_dot(text, m.start(1)):
            continue
        result[char_pos] = upper
        ctx = repr(text[max(0, m.start() - 15): m.end() + 15])
        changes.append("after-punct (%s): %s" % (punct, ctx))
    return "".join(result), changes


# ---------------------------------------------------------------------------
# Entry-start capitalization
# ---------------------------------------------------------------------------
SENTENCE_STARTER_PRONOUNS = {
    "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles",
}

_FIRST_WORD_RE = re.compile(r"([a-zA-Z\xc0-\xff]+)")


def _first_word(text):
    m = _FIRST_WORD_RE.match(text)
    return m.group(1).lower() if m else ""


def fix_entry_start(text):
    """Capitalize first letter if entry starts with a subject pronoun."""
    changes = []
    if not text:
        return text, changes
    if TOKEN_RE.match(text):
        return text, changes
    if not FR_LOWER_RE.match(text[0]):
        return text, changes
    first = _first_word(text)
    if not first or first not in SENTENCE_STARTER_PRONOUNS:
        return text, changes
    # Skip reflexive / emphatic forms like "vous-meme", "elles-memes"
    after_first = text[len(first):]
    if after_first.startswith("-"):
        return text, changes
    # Require at least 3 words to be a sentence
    if len(text.split()) < 3:
        return text, changes
    upper = text[0].upper()
    if upper == text[0]:
        return text, changes
    changes.append("entry-start: %s" % repr(text[:50]))
    return upper + text[1:], changes


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def process_line(line):
    """Process one line; return (new_line, list_of_change_descriptions)."""
    raw = line.rstrip("\n")
    if ": " not in raw:
        return line, []
    offset, text = raw.split(": ", 1)

    if GARBAGE_RE.search(text):
        return line, []
    # Skip entries that look like binary (no spaces, no token, > 8 chars)
    if len(text) > 8 and " " not in text and not TOKEN_RE.search(text):
        return line, []

    all_changes = []

    text, ch = fix_entry_start(text)
    all_changes.extend(ch)

    text, ch = fix_after_punctuation(text)
    all_changes.extend(ch)

    if all_changes:
        return offset + ": " + text + "\n", all_changes
    return line, []


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="Print changes without writing the file")
    args = parser.parse_args()

    lines = COMBINED.read_text(encoding="utf-8").splitlines(keepends=True)
    new_lines = []
    total_fixes = 0
    fixed_entries = 0

    for line in lines:
        new_line, changes = process_line(line)
        new_lines.append(new_line)
        if changes:
            fixed_entries += 1
            total_fixes += len(changes)
            if args.dry_run:
                raw = line.rstrip("\n")
                off = raw.split(": ", 1)[0] if ": " in raw else "?"
                print("[%s]" % off)
                for c in changes:
                    print("  " + c)

    print("\nTotal: %d fix(es) in %d entr(y/ies)" % (total_fixes, fixed_entries))
    if args.dry_run:
        print("(dry-run: no changes written)")
        return 0

    COMBINED.write_text("".join(new_lines), encoding="utf-8")
    print("Written: %s" % COMBINED)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
