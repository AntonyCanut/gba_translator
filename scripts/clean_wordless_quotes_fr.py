#!/usr/bin/env python3
"""Remove wordless quote glyphs from the FR dialogue (ticket R-09 follow-up).

Background
----------
In the CFRU/FireRed font, byte ``0xB0`` renders as the ellipsis glyph "…".
The English source uses ``0xB0`` heavily for pauses / hesitation
("You………", "Ngh… take… my Pokémon…").  When that text was decoded into
``combined_fr.txt`` the decoder mapped ``0xB0`` to a *straight* double quote
``"`` (U+0022), whereas the genuine quote bytes ``0xB1`` / ``0xB2`` decode to
the *curly* quotes “ / ”.

After the encoder was fixed (commit 3ab66ad) straight ``"`` now re-encodes to a
real curly quote glyph (0xB1/0xB2) instead of back to the ellipsis 0xB0.  As a
result every one of those ex-ellipsis quotes now renders in-game as a stray
quote with nothing meaningful inside it (e.g. a bare run of quotes after
"Meurs", "perdu" or "Ngh ... prends ... mes Pokemon").  The user asked:
"Les guillemets a outrance sans mots a l'interieur peuvent etre simplement
supprimes." -> remove them.

Strategy (English source is the ground truth)
---------------------------------------------
For every ``combined_fr.txt`` entry that contains a straight ``"`` we decode the
matching English string and look at which special bytes it used:

* ``0xB0``  → ellipsis  (decodes to straight ``"``)
* ``0xB1`` / ``0xB2`` → real curly quotes (decode to “ ”)

Per-entry decision:

* English had **only** ellipses (no real quotes)        → every straight ``"`` is
  an ex-ellipsis            → REMOVE them all.
* English had **only** real quotes (no ellipsis)        → the straight ``"`` are
  genuine quotations         → KEEP them.
* English had **both**: a tiny, hand-verified set (6 entries).  In 3 of them the
  real quote is already stored as raw ``<0xB1>…<0xB2>`` bytes and every straight
  ``"`` is an ellipsis (REMOVE); in the other 3 the straight ``"`` *are* the real
  quotation (KEEP).

Only straight ``"`` (U+0022) are ever touched.  Curly “ ” and guillemets « » are
left untouched (they always enclose a word or a name variable).

The transform only ever *shortens* a string, so pointers can never overflow.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.core.text_codec import TextDecoder  # noqa: E402

COMBINED = REPO / "combined_fr.txt"
ENGLISH_ROM = REPO / "input" / "roms" / "englishrom.gba"

STRAIGHT = '"'  # U+0022

# Hand-verified "both" entries (English used both ellipsis 0xB0 and real quotes).
# In these the straight " are all ex-ellipses (real quote stored as raw bytes).
BOTH_REMOVE = {"0x1f4afa2", "0x1f4cc4b", "0x1f50bd0"}
# In these the straight " ARE the real quotation -> keep.
BOTH_KEEP = {"0x418c83", "0x7768a4", "0x7d6bd9"}

_WORDCHAR = r"[A-Za-zÀ-ÿœŒ0-9]"


def _decode_english(decoder: TextDecoder, rom: bytes, offset: int) -> str:
    raw = rom[offset : offset + 4000]
    end = raw.find(b"\xff")
    seg = raw[: end if end >= 0 else 4000]
    try:
        return decoder.decode(seg, "pokemon")
    except Exception:
        return ""


def classify(decoder: TextDecoder, rom: bytes, offset_hex: str) -> str:
    """Return 'remove', 'keep' or 'skip' for an entry's straight quotes."""
    key = offset_hex.lower()
    if key in BOTH_REMOVE:
        return "remove"
    if key in BOTH_KEEP:
        return "keep"
    try:
        offset = int(offset_hex, 16)
    except ValueError:
        return "skip"
    en = _decode_english(decoder, rom, offset)
    en_ellipsis = en.count('"')          # 0xB0
    en_quotes = en.count("“") + en.count("”")  # 0xB1 / 0xB2
    if en_quotes == 0 and en_ellipsis > 0:
        return "remove"
    if en_quotes > 0 and en_ellipsis == 0:
        return "keep"
    # Anything else (no special bytes, or an un-handled mix) -> leave untouched.
    return "skip"


def strip_quotes(text: str) -> str:
    """Remove every straight " from *text*, keeping words readable.

    A " sitting directly between two word characters becomes a single space so
    adjacent words are not glued together ("Euh"go" -> "Euh go"); otherwise it
    is deleted and any whitespace it leaves behind is tidied up.
    """
    # 1. word"word -> word word  (avoid merging two words)
    text = re.sub(rf"(?<={_WORDCHAR}){STRAIGHT}(?={_WORDCHAR})", " ", text)
    # 2. drop all remaining straight quotes
    text = text.replace(STRAIGHT, "")
    # 3. tidy whitespace introduced by the removal
    text = re.sub(r"  +", " ", text)              # collapse doubled spaces
    text = re.sub(r" +(\\[nlp])", r"\1", text)    # no space before \n \l \p
    text = re.sub(r" +$", "", text)               # no trailing space
    return text


def run(apply: bool) -> int:
    decoder = TextDecoder()
    rom = ENGLISH_ROM.read_bytes()
    lines = COMBINED.read_text(encoding="utf-8").splitlines(keepends=True)

    changed = 0
    removed_quotes = 0
    report = []
    for i, line in enumerate(lines):
        if ":" not in line:
            continue
        offset_hex, rest = line.split(":", 1)
        offset_hex = offset_hex.strip()
        # preserve trailing newline
        nl = "\n" if rest.endswith("\n") else ""
        body = rest[:-1] if nl else rest
        if STRAIGHT not in body:
            continue
        if classify(decoder, rom, offset_hex) != "remove":
            continue
        new_body = strip_quotes(body)
        if new_body == body:
            continue
        removed_quotes += body.count(STRAIGHT)
        changed += 1
        report.append((offset_hex, body.strip(), new_body.strip()))
        lines[i] = f"{offset_hex}:{new_body}{nl}"

    for off, before, after in report:
        print(f"{off}\n  - {before[:90]!r}\n  + {after[:90]!r}")
    print(f"\n{changed} entries cleaned, {removed_quotes} straight quotes removed.")

    if apply and changed:
        COMBINED.write_text("".join(lines), encoding="utf-8")
        print(f"Written to {COMBINED}")
    elif not apply:
        print("(dry-run — pass --apply to write)")
    return changed


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write changes to combined_fr.txt")
    args = ap.parse_args()
    run(args.apply)
