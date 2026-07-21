#!/usr/bin/env python3
"""Move the POKEDOLLAR symbol after every dynamic French amount.

The engine builds several money strings (Trainer Card, shop, PC, mart, bag…)
from a shared rodata template at file offset 0x41697A:

    B7 FD 02 FF   ->  "¥" + {STR_VAR_1} + terminator   (English order: ¥1234)

Official French Pokémon games print the amount *before* the currency glyph
(1234¥), unlike English. This template lives well below the main text
region (0x1F00000-0x1F80000), so it is never captured by the translation
pipeline (absent from `combined_fr.txt`, the injection JSON and the Spanish
extract) — a class-3 fix, patched in place exactly like
`patch_status_abbrevs_fr.py`.

The swap is a straight byte permutation of the same 4-byte cell — no pointer
relocation needed, since "{STR_VAR_1}¥" is exactly as long as "¥{STR_VAR_1}":

    FD 02 B7 FF   ->  {STR_VAR_1} + "¥" + terminator   (French order: 1234¥)

Some scripted French messages embed their own amount variable instead of using
that template, including messages without a pointer that bypass the translation
injector.  They can contain formatting control codes between the POKEDOLLAR
glyph and the variable, for example ``¥{COLOR}{STR_VAR_2}{COLOR}``.  Those
byte sequences are patched in the final ROM as well, preserving the formatting
around the amount.

Content guard (ticket « Capture reset game »)
---------------------------------------------
The inline pass MUST NOT scan the ROM blindly: the byte pattern
``B7 [FC 01 xx]* FD 0[234]`` also occurs where 0xB7/0xFD are halves of Thumb
``BL`` instruction pairs (0x104C58, 0x10E75C, 0xA2B7BA — the last one is CFRU
code run by the wild-capture flow) and inside compressed graphics (0x52D32F,
0x1BFEA39, 0x1C26653). A previous blind version reordered those bytes and the
game rebooted to the title screen after every wild capture (new-species Pokédex
page → reset). Every candidate match is therefore only rewritten when it lies
inside a genuine 0xFF-terminated CFRU *text* string: the enclosing bytes (the
money pattern itself excluded) must decode to French text — letters, digits,
punctuation and dialogue control codes — at a >= 80 % ratio. Thumb code and
compressed data never pass this gate (calibrated on all 48 matches of a real
build: 42 text sites accepted, the 6 code/graphics sites rejected).

Idempotent: skips sequences that already use French order.
"""

from __future__ import annotations

import argparse
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.text.charmap_data import CHAR_TO_BYTE

TEMPLATE_OFFSET = 0x41697A
ENGLISH_ORDER = bytes([0xB7, 0xFD, 0x02, 0xFF])
FRENCH_ORDER = bytes([0xFD, 0x02, 0xB7, 0xFF])

POKEDOLLAR = 0xB7
EXT_CTRL = 0xFC
VAR_CTRL = 0xFD
MONEY_VARIABLES = {0x02, 0x03, 0x04}
TERMINATOR = 0xFF

# --- content guard ----------------------------------------------------------
# Byte alphabet of real French dialogue text, derived from the charmap.
_FRENCH_CHARS = set(
    string.ascii_letters + "0123456789¥éèêëàâçîïôùûüœÉÈÀÂÇÊÎÔŒ' .,:;!?…«»-–"
)
TEXT_BYTES = frozenset(b for c, b in CHAR_TO_BYTE.items() if c in _FRENCH_CHARS)
# Multi-byte control codes (skipped structurally, counted neutral) and
# single-byte dialogue codes (newline/scroll/pause — legitimate text content).
_SKIP_CODES = {0xFC: 3, 0xFD: 2, 0xF8: 2, 0xF9: 2}
_SINGLE_TEXT_CODES = frozenset({0x00, 0xFA, 0xFB, 0xFE})
_GUARD_BACKWARD_CAP = 400   # max bytes to look back for the string start
_GUARD_FORWARD_CAP = 220    # max bytes to the string terminator
_GUARD_FALLBACK_WINDOW = 64  # context window when no terminator precedes
_GUARD_MIN_RATIO = 0.8


def _variable_after_formatting(data: bytearray, start: int) -> int | None:
    """Return the variable-control offset following a POKEDOLLAR glyph.

    The only permitted bytes between the glyph and a money variable are
    ``FC 01 xx`` formatting controls.  Limiting the match to those controls
    prevents accidental rewrites of arbitrary binary data.
    """
    cursor = start + 1
    while cursor + 2 < len(data) and data[cursor] == EXT_CTRL:
        if data[cursor + 1] != 0x01:
            return None
        cursor += 3
    if (
        cursor + 1 < len(data)
        and data[cursor] == VAR_CTRL
        and data[cursor + 1] in MONEY_VARIABLES
    ):
        return cursor
    return None


def _text_counts(data: bytearray, start: int, end: int) -> tuple[int, int]:
    """Count (text, non-text) bytes in ``data[start:end]``, skipping controls."""
    text = other = 0
    i = start
    while i < end:
        byte = data[i]
        if byte in _SKIP_CODES:
            i += _SKIP_CODES[byte]
            continue
        if byte in _SINGLE_TEXT_CODES or byte in TEXT_BYTES:
            text += 1
        else:
            other += 1
        i += 1
    return text, other


def _match_is_inside_french_string(
    data: bytearray, offset: int, variable_offset: int
) -> bool:
    """True when the money pattern at ``offset`` sits inside real French text.

    The enclosing 0xFF-terminated string — minus the matched money pattern
    itself — must be made of French text bytes. Thumb code and compressed
    graphics that happen to contain the byte pattern never look like that.
    """
    end = data.find(bytes([TERMINATOR]), offset, offset + _GUARD_FORWARD_CAP)
    if end < 0:
        return False
    start = data.rfind(
        bytes([TERMINATOR]), max(0, offset - _GUARD_BACKWARD_CAP), offset
    )
    lo = start + 1 if start >= 0 else max(0, offset - _GUARD_FALLBACK_WINDOW)

    before = _text_counts(data, lo, offset)
    after = _text_counts(data, variable_offset + 2, end)
    text = before[0] + after[0]
    other = before[1] + after[1]

    if text + other == 0:
        # Pure money-template cell (nothing but the pattern between two
        # terminators) — only trusted when a real terminator bounds it.
        return start >= 0
    return text >= 1 and other == 0 or (
        text + other >= 2 and text / (text + other) >= _GUARD_MIN_RATIO
    )


def apply_inline_money_orders(data: bytearray) -> int:
    """Move currency glyphs after formatted money variables in-place.

    Only matches proven to sit inside a genuine French text string are
    rewritten — see ``_match_is_inside_french_string``.
    """
    patched = 0
    for offset, value in enumerate(data):
        if offset == TEMPLATE_OFFSET or value != POKEDOLLAR:
            continue
        variable_offset = _variable_after_formatting(data, offset)
        if variable_offset is None:
            continue
        if not _match_is_inside_french_string(data, offset, variable_offset):
            continue
        variable = data[variable_offset:variable_offset + 2]
        # Remove the leading glyph, then insert it immediately after FD xx.
        # The formatting controls stay around both the value and the glyph.
        data[offset:variable_offset + 2] = (
            data[offset + 1:variable_offset] + variable + bytes([POKEDOLLAR])
        )
        patched += 1
    return patched


def apply(data: bytearray) -> int:
    current = bytes(data[TEMPLATE_OFFSET:TEMPLATE_OFFSET + len(FRENCH_ORDER)])
    if current == ENGLISH_ORDER:
        data[TEMPLATE_OFFSET:TEMPLATE_OFFSET + len(FRENCH_ORDER)] = FRENCH_ORDER
        template_patches = 1
    elif current == FRENCH_ORDER:
        template_patches = 0
    else:
        raise ValueError(
            f"money template at 0x{TEMPLATE_OFFSET:06X} unexpected: {current.hex()}"
        )
    return template_patches + apply_inline_money_orders(data)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", type=Path, required=True)
    args = ap.parse_args()
    data = bytearray(args.rom.read_bytes())
    n = apply(data)
    if n:
        args.rom.write_bytes(data)
    print(f"patch_money_amount_order_fr: {n} patch(es) applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
