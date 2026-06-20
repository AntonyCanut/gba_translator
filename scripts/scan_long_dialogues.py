#!/usr/bin/env python3
"""Find pointer-referenced Pokemon-text strings in the English ROM whose 0xFF
terminator is more than CAP bytes away — i.e. dropped by the pointer extractor's
``max_text_length`` cap, the root cause behind the long dialogues that stay
English in the built ROM (Borrius meteorite monologues, New Game+, Battle
facilities, the Guardian portal errand…).

For each maximal long string it reports whether the built French ROM still shows
the English text, so ``patch_long_dialogues_fr.TARGETS`` can be kept in sync.
Run from the repo root: ``python3 scripts/scan_long_dialogues.py``.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from src.core.text_codec import TextDecoder, TextEncoder  # noqa: E402

CAP = 1000
BASE = 0x08000000
POKEMON_BYTES = set(TextEncoder.POKEMON_TABLE.values()) | {0xFE}

en = Path(REPO / "input/roms/englishrom.gba").read_bytes()
fr_path = REPO / "output/roms/GenedRom-fr.gba"
fr = fr_path.read_bytes() if fr_path.exists() else None
romsize = len(en)


def measure(rom: bytes, off: int, maxscan: int = 4000):
    """Return (length_incl_terminator, pokemon_ratio) or None if no terminator/garbage."""
    if off < 0 or off + 4 > len(rom):
        return None
    end = min(len(rom), off + maxscan)
    data = rom[off:end]
    idx = data.find(b"\xff")
    if idx == -1:
        return None
    body = data[:idx]
    if not body:
        return None
    pk = sum(1 for b in body if b in POKEMON_BYTES) / len(body)
    return idx + 1, pk


# Collect every live pointer target (all 4 alignments), dedup offsets.
targets: dict[int, list[int]] = {}
for align in range(4):
    pos = align
    while pos + 4 <= romsize:
        ptr = struct.unpack_from("<I", en, pos)[0]
        if BASE <= ptr < BASE + romsize:
            off = ptr - BASE
            targets.setdefault(off, []).append(pos)
        pos += 4

print(f"distinct pointer targets: {len(targets)}")

import re as _re

# Legit dialogue control-code markers the decoder renders as <0xNN>; not garbage.
_CTRL_MARKER = _re.compile(r"<0x(F[789ABCDE])>")


def prose_score(decoded: str):
    """Heuristics that separate real English prose from tile/graphics noise."""
    decoded = _CTRL_MARKER.sub("", decoded)
    n = len(decoded)
    if n == 0:
        return None
    unknown = decoded.count("<0x")
    lower = sum(1 for c in decoded if c.islower())
    alpha = sum(1 for c in decoded if c.isalpha())
    space = decoded.count(" ") + decoded.count("\n")
    if alpha == 0:
        return None
    return {
        "unknown_ratio": unknown / n,
        "space_ratio": space / n,
        "lower_alpha": lower / alpha,
        "alpha_ratio": alpha / n,
        "words": [w for w in decoded.replace("\n", " ").split(" ") if w],
    }


def is_prose(decoded: str) -> bool:
    s = prose_score(decoded)
    if not s:
        return False
    words = s["words"]
    if len(words) < 20:
        return False
    avg_w = sum(len(w) for w in words) / len(words)
    return (
        s["unknown_ratio"] < 0.01
        and 0.10 <= s["space_ratio"] <= 0.35
        and s["lower_alpha"] >= 0.55
        and s["alpha_ratio"] >= 0.55
        and 2.0 <= avg_w <= 9.0
    )


candidates = []
for off, refs in targets.items():
    m = measure(en, off)
    if not m:
        continue
    length, pk = m
    if length <= CAP:
        continue
    decoded = TextDecoder.decode_pokemon(en[off:off + length], preserve_unknown=True)
    if is_prose(decoded):
        candidates.append((off, length, pk, refs))

candidates.sort(key=lambda x: x[0])

# Dedup to MAXIMAL strings: drop any candidate whose start lies inside an earlier
# candidate's [start, start+len) range (those are mid-string false-positive pointers).
maximal = []
for off, length, pk, refs in candidates:
    if any(s <= off < s + l for s, l, _, _ in maximal):
        continue
    maximal.append((off, length, pk, refs))

print(f"\nMaximal long (> {CAP} bytes) prose strings: {len(maximal)}\n")


def fr_is_english(off: int, length: int) -> bool:
    """True if the FR ROM bytes at this offset still decode to the English text."""
    if fr is None:
        return False
    data = fr[off:off + length + 200]
    idx = data.find(b"\xff")
    seg = fr[off:off + (idx + 1 if idx >= 0 else 60)]
    dec = TextDecoder.decode_pokemon(seg, preserve_unknown=True)
    # English markers: starts the same as EN and contains no accented FR letters.
    en_dec = TextDecoder.decode_pokemon(en[off:off + length], preserve_unknown=True)
    return dec[:40] == en_dec[:40]


for off, length, pk, refs in sorted(maximal, key=lambda x: -x[1]):
    en_txt = TextDecoder.decode_pokemon(en[off:off + length], preserve_unknown=True)
    preview = en_txt.replace("\n", " ").replace("\x00", " ")[:64]
    state = "STILL-ENGLISH" if fr_is_english(off, length) else "french/ok"
    print(f"0x{off:06X} len={length:5d} refs={len(refs):2d}  {state}")
    print(f"        EN: {preview!r}")
