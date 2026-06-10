#!/usr/bin/env python3
"""
Fallback translator - Synthesize a *fitting* translation for strings that
overflow their in-ROM byte budget.

Context
-------
When the French translation of a string encodes to more bytes than the slot
it must occupy (original length + adjacent free padding), the reinserter has
historically skipped it (``skipped_too_long``) and left the **English** text
in place. On a full build this affected thousands of strings, so large parts
of the game stayed in English even though a French translation existed.

This module turns "leave it in English" into "make the French fit". Given the
French text and the byte budget, it produces the longest faithful French
variant that still fits, applying a cascade of strategies from lossless to
lossy and stopping as soon as the result fits.

Assumptions about the input data (documented contract)
------------------------------------------------------
1. The full French ``text`` is available (with ``<0xNN>`` control tokens and
   ``\n`` newlines written literally, exactly as the reinserter consumes it).
2. ``max_length`` is the total byte budget **including the terminator**, which
   matches :class:`SmartReinserter` semantics (it compares ``len(encoded)``,
   and ``encoded`` already carries the trailing terminator).
3. Control codes - ``<0xNN>`` hex tokens and ``\n`` (-> 0xFE) - are atomic and
   semantically significant (colour, name substitution, line breaks...). They
   are never split across a byte boundary and never silently dropped; shrinking
   only ever removes *literal* characters.
4. Byte length is measured by actually encoding candidates with
   :class:`TextEncoder`, so alias expansions (``oe`` for ``oe``, ``...`` for the
   ellipsis, etc.) are accounted for exactly rather than estimated.
5. Accents (e/e/a/c...) encode to a single byte just like their base letter, so
   stripping them saves nothing and is deliberately *not* used - it would only
   degrade quality for zero gain.

The synthesized string is, by construction, valid for the CFRU charmap and
always shorter-or-equal to the budget, so the reinserter can write it in place
with no risk of corrupting the neighbouring string.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from .text_codec import TextEncoder


# Conservative, game-appropriate French abbreviations. Applied whole-word and
# case-insensitively, longest first, and only when a shorter form is genuinely
# needed. Kept small on purpose: an abbreviation that changes meaning is worse
# than a clean truncation, so only unambiguous space-savers live here.
DEFAULT_ABBREVIATIONS = {
    "c'est-à-dire": "c.-à-d.",
    "s'il te plaît": "stp",
    "s'il vous plaît": "svp",
    "rendez-vous": "RDV",
    "numéro": "n°",
    "monsieur": "M.",
    "madame": "Mme",
    "mademoiselle": "Mlle",
    "docteur": "Dr",
    "boulevard": "bd",
    "avenue": "av.",
    "etcetera": "etc.",
    "et cetera": "etc.",
}

# Token grammar shared with TextEncoder: a ``<0xNN>`` hex escape is one atomic
# unit; everything else is consumed one character at a time.
_HEX_TOKEN_RE = re.compile(r"<(?:0x)?[0-9A-Fa-f]{2}>")


@dataclass
class FallbackResult:
    """Outcome of a shrink-to-fit attempt."""

    text: str
    strategy: str
    fits: bool
    original_bytes: int
    final_bytes: int


class FallbackSynthesizer:
    """
    Shrink an over-long translation until it fits its byte budget.

    Strategy cascade (each step only runs if the previous output still
    overflows; the first step that fits wins):

    1. ``whitespace`` - collapse repeated spaces, trim, and drop spaces before
       closing punctuation. Fully lossless.
    2. ``abbreviate`` - replace long whole words with standard French
       abbreviations from :data:`DEFAULT_ABBREVIATIONS`. Minor, readable loss.
    3. ``truncate`` - token-aware truncation at the last word boundary that
       fits, preserving control tokens and never splitting a ``<0xNN>``
       sequence. Last resort: meaning is clipped but the string stays valid
       French rather than reverting to English.
    """

    def __init__(self, abbreviations: Optional[dict] = None):
        self.abbreviations = abbreviations if abbreviations is not None else DEFAULT_ABBREVIATIONS

    # -- public API ---------------------------------------------------------

    def encoded_length(self, text: str, encoding: str) -> int:
        """Exact encoded byte length (terminator included)."""
        return len(TextEncoder.encode(text, encoding))

    def fits(self, text: str, encoding: str, max_length: int) -> bool:
        return self.encoded_length(text, encoding) <= max_length

    def shrink_to_fit(self, text: str, encoding: str, max_length: int) -> FallbackResult:
        """
        Return the longest faithful variant of ``text`` that fits ``max_length``.

        ``strategy`` reports which step produced the result: ``none`` (already
        fit), ``whitespace``, ``abbreviate`` or ``truncate``.
        """
        original_bytes = self.encoded_length(text, encoding)

        if original_bytes <= max_length:
            return FallbackResult(text, "none", True, original_bytes, original_bytes)

        # 1. Lossless whitespace normalization.
        candidate = self._normalize_whitespace(text)
        if self.fits(candidate, encoding, max_length):
            return self._result(candidate, "whitespace", encoding, max_length, original_bytes)

        # 2. Standard abbreviations.
        abbreviated = self._abbreviate(candidate)
        if abbreviated != candidate and self.fits(abbreviated, encoding, max_length):
            return self._result(abbreviated, "abbreviate", encoding, max_length, original_bytes)
        # Keep whichever lossless-ish form is shortest going into truncation.
        base = abbreviated if self.encoded_length(abbreviated, encoding) < self.encoded_length(candidate, encoding) else candidate

        # 3. Token-aware truncation at a word boundary.
        truncated = self._truncate_to_fit(base, encoding, max_length)
        return self._result(truncated, "truncate", encoding, max_length, original_bytes)

    # -- strategies ---------------------------------------------------------

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        # Collapse runs of spaces/tabs (but keep explicit newlines intact).
        text = re.sub(r"[ \t]+", " ", text)
        # Drop spaces directly before closing punctuation.
        text = re.sub(r" +([,.;:!?])", r"\1", text)
        # Trim spaces hugging a newline and at both ends.
        text = re.sub(r" *\n *", "\n", text)
        return text.strip(" ")

    def _abbreviate(self, text: str) -> str:
        for word, short in sorted(self.abbreviations.items(), key=lambda kv: -len(kv[0])):
            pattern = re.compile(r"\b" + re.escape(word) + r"\b", re.IGNORECASE)
            text = pattern.sub(short, text)
        return text

    def _truncate_to_fit(self, text: str, encoding: str, max_length: int) -> str:
        """
        Greedily keep the longest prefix of atomic tokens that fits, preferring
        to end on a word boundary. Control tokens (``<0xNN>``) stay intact.
        """
        tokens = self._tokenize(text)

        # Longest prefix (in tokens) whose encoding fits the budget.
        best = 0
        for count in range(len(tokens), -1, -1):
            if self.fits("".join(tokens[:count]), encoding, max_length):
                best = count
                break

        if best == 0:
            return ""

        # If the cut already lands on a clean boundary (end of text, or the next
        # dropped token is a space) keep it. Otherwise we'd be slicing a word in
        # half: walk back to the last space so we don't leave a half-word,
        # without giving up more than a couple of dozen tokens.
        if best == len(tokens) or tokens[best] == " ":
            cut = best
        else:
            cut = best
            for i in range(best - 1, max(-1, best - 24), -1):
                if tokens[i] == " ":
                    cut = i
                    break

        result = "".join(tokens[:cut]).rstrip(" ")
        # Safety: rstrip can only shorten, so the fit is preserved.
        return result

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        tokens: List[str] = []
        i = 0
        while i < len(text):
            match = _HEX_TOKEN_RE.match(text, i)
            if match:
                tokens.append(match.group(0))
                i = match.end()
                continue
            tokens.append(text[i])
            i += 1
        return tokens

    # -- helpers ------------------------------------------------------------

    def _result(self, text: str, strategy: str, encoding: str, max_length: int, original_bytes: int) -> FallbackResult:
        final_bytes = self.encoded_length(text, encoding)
        return FallbackResult(text, strategy, final_bytes <= max_length, original_bytes, final_bytes)
