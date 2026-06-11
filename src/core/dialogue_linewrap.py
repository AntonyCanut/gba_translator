#!/usr/bin/env python3
"""Pixel-aware line re-wrapping for Gen III / CFRU dialogue text.

French translations inherit their line-break positions from the English
source. French words are longer, so an inherited break often leaves the
first visual line nearly empty while the second runs past the right edge
of the message box (e.g. ``Et`` / ``enfin, comment t'appelles-tu ?``).

This module re-positions the soft breaks so each display segment reads
naturally, without changing the wording or any control code:

* Text is split into *display segments* on the structural codes
  ``<0xFB>`` (paragraph: clears the window) and ``<0xFA>`` (scroll one
  line). Those codes are preserved verbatim and in place.
* Within a segment the existing ``\n`` breaks are removed and the words
  re-flowed greedily: each line is filled as close to the box edge as
  possible before breaking, which also uses the fewest lines. Short
  dialogues inherit breaks from longer English lines (``Non ! Mon\n
  Sepiatop !``) and read better on a single line; longer ones must not
  break while space remains on the current line. Buffer-bearing
  segments (player/Pokémon names) keep their source line count,
  balanced, because a buffer can render wider than its estimate. If the
  words genuinely cannot fit, extra lines are added; the Gen III break
  rule below turns them into scrolls.
* Breaks are then normalised to the Gen III dialogue rule: the message
  box shows two lines, so the first break after the start of text or a
  ``<0xFB>`` is ``\n`` (0xFE) and every later break must scroll
  (``<0xFA>``) until the next ``<0xFB>`` clears the window. ``\n`` and
  ``<0xFA>`` are both one encoded byte, so the fix never changes length.

Texts handled here use this pipeline's decoded form: plain characters,
real newlines, and ``<0xNN>`` hex tokens for control bytes. A
``<0xFD><0xNN>`` pair is a runtime buffer (player name, species name…)
and is counted at a conservative pixel width so name-bearing lines do
not overflow (Unbound player names run up to 9 characters).

Glyph widths are the authoritative FireRed normal-font advances
(``sFontNormalLatinGlyphWidths`` from the pret/pokefirered disassembly),
indexed by the encoded byte value. Unbound is a CFRU/FireRed hack and
uses the same font metrics.
"""

from __future__ import annotations

import re
from typing import List, Optional

from src.core.text_codec import ENCODE_ALIASES, TextEncoder

# FireRed normal-font glyph advance widths in pixels, indexed by encoded
# byte (glyph id). Source: pret/pokefirered src/text.c
# sFontNormalLatinGlyphWidths. The advance already includes inter-glyph
# spacing, so a line's pixel width is the sum of its glyph widths.
GLYPH_WIDTHS: tuple = (
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     8,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  8,  6,  6,  6,  6,  6,  6,  9,  8,  8,  6,
     6,  6,  6,  6, 10,  8,  5,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  8,  8,  8,  8,  8,  8,  4,  6,  8,  5,  5,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6, 12, 12, 12, 12,  6,  6,  6,
     6,  6,  6,  6,  8,  8,  8,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     8,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  5,  6,  5,
     6,  6,  6,  3,  3,  6,  6,  8,  5,  9,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  5,  6,  6,  4,  6,  5,
     5,  6,  5,  6,  6,  6,  5,  5,  5,  6,  6,  6,  6,  6,  6,  8,
     5,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
)

# Usable text width of the FireRed message box, in pixels. The interior
# is wider, but the rightmost pixels are reserved for the scroll arrow,
# so wrapping a couple of pixels short keeps text clear of it.
DEFAULT_MAX_LINE_WIDTH = 192

# Estimated rendered width of a <0xFD><0xNN> runtime buffer (player or
# Pokémon name). Unbound player names run up to 9 characters (~6px each).
VARIABLE_WIDTH = 54

SPACE_WIDTH = GLYPH_WIDTHS[0x00]

_TOKEN_RE = re.compile(r'<0x([0-9A-Fa-f]{2})>')
_BREAK_RE = re.compile(r'<0xF[ABab]>|\n')
_SEGMENT_SPLIT = re.compile(r'(<0xF[ABab]>)')
_PAGE_SPLIT = re.compile(r'(<0xF[Bb]>)')
_SCROLL_RE = re.compile(r'<0xF[Aa]>')
_STRUCT_RE = re.compile(r'<0xF[ABab]>')
_BLANK_RUN_SPLIT = re.compile(r'(\n{2,})')
_SCROLL = '<0xFA>'
_PAGE = '<0xFB>'


def _char_width(ch: str) -> int:
    """Pixel advance of one printable character (after font aliasing)."""
    if ch == ' ':
        return SPACE_WIDTH
    mapped = ENCODE_ALIASES.get(ch, ch)
    width = 0
    for c in mapped:
        byte = TextEncoder.POKEMON_TABLE.get(c)
        width += GLYPH_WIDTHS[byte] if byte is not None else 6
    return width


def word_width(word: str) -> int:
    """Pixel width of a word token that may embed ``<0xNN>`` codes."""
    width = 0
    i = 0
    while i < len(word):
        match = _TOKEN_RE.match(word, i)
        if match:
            if match.group(1).upper() == 'FD':
                width += VARIABLE_WIDTH
            i = match.end()
            continue
        width += _char_width(word[i])
        i += 1
    return width


def line_width(line: str) -> int:
    """Pixel width of one visual line (words joined by single spaces)."""
    words = [w for w in line.split(' ') if w]
    if not words:
        return 0
    return sum(word_width(w) for w in words) + SPACE_WIDTH * (len(words) - 1)


_PUNCT_ONLY_RE = re.compile(r'[!?:;.,"»«…-]+$')


def _split_words(segment: str) -> List[str]:
    """Split a segment into words, gluing ``<0xNN>`` codes to neighbours.

    French spaced punctuation (`` !``, `` ?``, `` :``) must never start
    a line: a token made only of punctuation is glued to the previous
    word (space included) so no break can ever orphan it (``Sepiatop\n!``).
    """
    words: List[str] = []
    buf: List[str] = []

    def flush() -> None:
        if not buf:
            return
        token = ''.join(buf)
        buf.clear()
        if words and _PUNCT_ONLY_RE.fullmatch(token):
            words[-1] += ' ' + token
        else:
            words.append(token)

    i = 0
    while i < len(segment):
        match = _TOKEN_RE.match(segment, i)
        if match:
            buf.append(match.group(0))
            i = match.end()
            continue
        ch = segment[i]
        if ch in ' \n\t':
            flush()
        else:
            buf.append(ch)
        i += 1
    flush()
    return words


def _segment_width(widths: List[int], i: int, j: int) -> int:
    return sum(widths[i:j]) + SPACE_WIDTH * max(0, j - i - 1)


def _trace(cut: List[List[int]], k: int, n: int) -> List[int]:
    cuts: List[int] = []
    j = n
    for kk in range(k, 1, -1):
        i = cut[kk][j]
        cuts.append(i)
        j = i
    cuts.reverse()
    return cuts


def _feasible_partition(
    widths: List[int], k: int, max_width: int
) -> Optional[List[int]]:
    """Cut words into ``k`` lines, all within ``max_width``.

    Minimises raggedness (sum of squared slack). Returns ``None`` when no
    layout keeps every line inside ``max_width``.
    """
    n = len(widths)
    inf = float('inf')
    dp = [[inf] * (n + 1) for _ in range(k + 1)]
    cut = [[0] * (n + 1) for _ in range(k + 1)]
    dp[0][0] = 0.0
    for kk in range(1, k + 1):
        for j in range(1, n + 1):
            for i in range(kk - 1, j):
                if dp[kk - 1][i] == inf:
                    continue
                lw = _segment_width(widths, i, j)
                if lw > max_width:
                    continue
                slack = max_width - lw
                cost = dp[kk - 1][i] + slack * slack
                if cost < dp[kk][j]:
                    dp[kk][j] = cost
                    cut[kk][j] = i
    if dp[k][n] == inf:
        return None
    return _trace(cut, k, n)


def _minimax_partition(widths: List[int], k: int) -> List[int]:
    """Cut words into ``k`` lines minimising the widest line (fallback)."""
    n = len(widths)
    inf = float('inf')
    dp = [[inf] * (n + 1) for _ in range(k + 1)]
    cut = [[0] * (n + 1) for _ in range(k + 1)]
    dp[0][0] = 0.0
    for kk in range(1, k + 1):
        for j in range(1, n + 1):
            for i in range(kk - 1, j):
                if dp[kk - 1][i] == inf:
                    continue
                widest = max(dp[kk - 1][i], float(_segment_width(widths, i, j)))
                if widest < dp[kk][j]:
                    dp[kk][j] = widest
                    cut[kk][j] = i
    return _trace(cut, k, n)


# How many extra lines a segment may gain when its words cannot fit the
# original line count. Extra breaks become scrolls, so the box layout is
# preserved; the cap only guards against pathological growth.
_MAX_EXTRA_LINES = 4


def _greedy_partition(widths: List[int], max_width: int) -> List[int]:
    """Fill each line as full as ``max_width`` allows, left to right.

    Returns the cut indices (same convention as ``_feasible_partition``).
    Greedy filling uses the fewest possible lines and pushes every break
    as far right as it can go — lines run to the edge of the box instead
    of being balanced half/half.
    """
    cuts: List[int] = []
    current = 0
    count = 0
    for i, width in enumerate(widths):
        added = width if count == 0 else SPACE_WIDTH + width
        if count and current + added > max_width:
            cuts.append(i)
            current = width
            count = 1
        else:
            current += added
            count += 1
    return cuts


def rewrap_segment(segment: str, max_width: int = DEFAULT_MAX_LINE_WIDTH) -> str:
    """Re-flow the ``\n`` breaks inside one display segment.

    Plain segments are wrapped greedily: each line is filled as close to
    the box edge as possible, which also yields the fewest lines — a
    short dialogue whose words fit on a single line is merged onto one
    line, and a break never happens while space remains on the current
    line. Single-line segments are returned unchanged.
    """
    line_count = segment.count('\n') + 1
    if line_count < 2:
        return segment

    words = _split_words(segment)
    if len(words) <= line_count:
        # One word per line is a deliberate list-like layout — leave it.
        return segment

    widths = [word_width(w) for w in words]
    # Runtime buffers (<0xFD><0xNN>) can render wider than their 54px
    # estimate (battle prefixes, 10-char nicknames): packing their line
    # full risks clipping at the box edge, so buffer-bearing segments
    # keep their source line count, balanced.
    if '<0xFD>' not in segment:
        cuts = _greedy_partition(widths, max_width)
    else:
        cuts = None
        for k in range(line_count, min(len(words), line_count + _MAX_EXTRA_LINES) + 1):
            cuts = _feasible_partition(widths, k, max_width)
            if cuts is not None:
                break
    if cuts is None:
        # A single word/buffer wider than the box — best effort.
        cuts = _minimax_partition(widths, line_count)

    lines: List[str] = []
    start = 0
    for cut in [*cuts, len(words)]:
        lines.append(' '.join(words[start:cut]))
        start = cut
    return '\n'.join(lines)


_BREAK_RUN_RE = re.compile(r'(?:(?:<0xF[ABab]>|\n)[ \t]*){2,}')


def has_empty_break_run(text: str) -> bool:
    """True when ``text`` contains consecutive breaks with no text between."""
    return bool(_BREAK_RUN_RE.search(text))


def collapse_empty_breaks(text: str) -> str:
    """Merge runs of consecutive breaks that enclose no text.

    A translation shorter than its English source can inherit more breaks
    than it has lines (``réagisse !<0xFA><0xFA><0xFB>``), which renders as
    blank lines in the message box. Each run keeps its strongest token —
    ``<0xFB>`` (wait + clear) over ``<0xFA>`` (wait + scroll) over ``\n``
    — so the pacing of the dialogue is preserved without the blanks.
    """

    def strongest(match: re.Match) -> str:
        run = match.group(0).upper()
        if '<0XFB>' in run:
            return _PAGE
        if '<0XFA>' in run:
            return _SCROLL
        return '\n'

    return _BREAK_RUN_RE.sub(strongest, text)


def normalize_breaks(text: str) -> str:
    """Enforce the Gen III dialogue break rule on ``text``.

    The message box displays two lines: the first break after the start
    of text or a ``<0xFB>`` page clear is ``\n``; once the box is full,
    every further break must scroll (``<0xFA>``). Both encode to one
    byte, so the rewrite never changes the encoded length.
    """
    out: List[str] = []
    pos = 0
    box_full = False
    for match in _BREAK_RE.finditer(text):
        out.append(text[pos:match.start()])
        token = match.group(0)
        if token != '\n':
            # <0xFA> scroll or <0xFB> page (hex digits at positions 3-4).
            box_full = token[3:5].upper() != 'FB'
            out.append(token)
        elif box_full:
            out.append(_SCROLL)
        else:
            box_full = True
            out.append('\n')
        pos = match.end()
    out.append(text[pos:])
    return ''.join(out)


def is_multiline_layout(text: str) -> bool:
    """True when ``text`` lays out a multi-line window, not a dialogue box.

    Intro screens, cinematics, credits, letters and other fullscreen
    texts render every line at once: their English source uses two or
    more ``\n`` breaks and never a scroll (``<0xFA>``) or page
    (``<0xFB>``) code. The Gen III two-line dialogue rule must NOT be
    applied to them — turning their breaks into scrolls truncates the
    display to two lines and pauses mid-sentence.
    """
    return not _STRUCT_RE.search(text) and text.count('\n') >= 2


def rewrap_multiline(text: str, reference: str) -> str:
    """Re-fit a translation into the multi-line window of its source.

    ``reference`` is the English layout: its widest line is taken as the
    usable window width. Blank-line runs are structural (vertical
    centring in the credits, paragraph gaps in the intro) and are kept
    verbatim, as are all ``\n`` breaks — no scroll/page codes are ever
    introduced. A paragraph is re-balanced only when one of its lines
    overflows the window, gaining extra lines if the words need them.
    """
    ref_width = max((line_width(line) for line in reference.split('\n')), default=0)
    cap = ref_width if ref_width > 0 else DEFAULT_MAX_LINE_WIDTH

    parts = _BLANK_RUN_SPLIT.split(text)
    out: List[str] = []
    for part in parts:
        if not part or _BLANK_RUN_SPLIT.fullmatch(part):
            out.append(part)
            continue
        lines = part.split('\n')
        if all(line_width(line) <= cap for line in lines):
            out.append(part)
            continue
        words = _split_words(part)
        widths = [word_width(w) for w in words]
        cuts = None
        max_k = min(len(words), len(lines) + _MAX_EXTRA_LINES)
        for k in range(len(lines), max_k + 1):
            cuts = _feasible_partition(widths, k, cap)
            if cuts is not None:
                break
        if cuts is None:
            cuts = _minimax_partition(widths, max(1, len(lines)))
        rebuilt: List[str] = []
        start = 0
        for cut in [*cuts, len(words)]:
            rebuilt.append(' '.join(words[start:cut]))
            start = cut
        out.append('\n'.join(rebuilt))
    return ''.join(out)


def rewrap(text: str, max_width: int = DEFAULT_MAX_LINE_WIDTH) -> str:
    """Re-balance line breaks across every display segment of ``text``.

    Only ``<0xFB>`` (page: wait + clear the window) is a hard boundary —
    it paces the dialogue and is kept in place. ``<0xFA>`` scrolls are
    mechanical: the box shows two lines, so their positions follow from
    the wrapping. Inside a page they are dissolved into ordinary breaks
    and the words re-flowed greedily across them, otherwise a 3+ line
    message keeps short lines on both sides of every inherited scroll.
    ``normalize_breaks`` then re-emits the canonical ``\n``/scroll
    structure. Pages holding a ``<0xFD>`` runtime buffer keep their
    scroll positions: the buffer can render wider than its estimate, so
    words must not be pulled across its boundary. Word order and wording
    are preserved; texts without any break are returned untouched.
    """
    if not _BREAK_RE.search(text):
        return text
    text = collapse_empty_breaks(text)
    out: List[str] = []
    for page in _PAGE_SPLIT.split(text):
        if _PAGE_SPLIT.fullmatch(page):
            out.append(page)
        elif '<0xFD>' not in page:
            out.append(rewrap_segment(_SCROLL_RE.sub('\n', page), max_width))
        else:
            out.append(''.join(
                part if _SEGMENT_SPLIT.fullmatch(part)
                else rewrap_segment(part, max_width)
                for part in _SEGMENT_SPLIT.split(page)
            ))
    return normalize_breaks(''.join(out))


def line_widths(text: str) -> List[int]:
    """Pixel width of each visual line in ``text`` (diagnostics/tests)."""
    flat = _SEGMENT_SPLIT.sub('\n', text)
    return [line_width(line) for line in flat.split('\n')]
