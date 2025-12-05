#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

DEFAULT_ROM = Path("totranslate.gba")
DEFAULT_CHARMAP = Path("charmap_firered.txt")
DEFAULT_OUTPUT = Path("extracted_text.txt")


def load_charmap(path: Path) -> Tuple[Dict[Tuple[int, ...], str], int]:
    """Return mapping of byte sequences to text plus the longest sequence length.

    The FireRed charmap includes many multi-byte values for music/SFX that
    collide with normal text (e.g., letter + 0x00). Those entries are filtered
    out because they produce noisy decodes. We keep multi-byte sequences only
    when they start with control prefixes or represent the special PK glyphs.
    """
    mapping: Dict[Tuple[int, ...], str] = {}
    max_len = 1
    control_prefixes = {0xFC, 0xFD, 0xF8, 0xF9}
    keep_names = {"PK", "PKMN"}

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("@", 1)[0].strip()
        if not line or "=" not in line:
            continue

        left, right = [part.strip() for part in line.rsplit("=", 1)]
        seq = tuple(int(h, 16) for h in right.split())
        if seq == (0xFF,):  # terminator
            continue

        if left.startswith("'") and left.endswith("'"):
            value = left[1:-1]
        else:
            value = "{" + left + "}"

        keep = True
        if len(seq) > 1:
            first = seq[0]
            if first not in control_prefixes and left not in keep_names:
                keep = False
        if keep and seq not in mapping:
            mapping[seq] = value
            max_len = max(max_len, len(seq))

    return mapping, max_len


def is_letterlike(token: str) -> bool:
    if token.startswith("{") or token.startswith("\\"):
        return False
    return all(
        c.isascii() and (c.isalpha() or c.isdigit() or c in "'-,.!? ")
        for c in token
    )


def looks_text(tokens: Sequence[str]) -> bool:
    if not tokens:
        return False

    text = "".join(tokens)
    plain = re.sub(r"\{[^}]+}", " ", text)
    plain = plain.replace("\\n", " ").replace("\\p", " ").replace("\\l", " ")
    plain = " ".join(plain.split())

    if len(plain) < 4:
        return False

    ascii_letters = sum(c.isascii() and c.isalpha() for c in plain)
    non_ascii_letters = sum((not c.isascii()) and c.isalpha() for c in plain)
    if ascii_letters < 4:
        return False
    if non_ascii_letters and non_ascii_letters / (ascii_letters + non_ascii_letters) > 0.3:
        return False

    letterlike = sum(1 for t in tokens if is_letterlike(t))
    ratio = letterlike / len(tokens)
    if ratio < 0.75:
        return False

    if len(plain) > 12 and " " not in plain:
        return False
    if len(plain) > 6 and not any(ch.lower() in "aeiou" for ch in plain if ch.isalpha()):
        return False

    return True


def decode_segment(seg: memoryview, mapping: Dict[Tuple[int, ...], str], max_len: int) -> List[str] | None:
    tokens: List[str] = []
    pos = 0
    size = len(seg)
    while pos < size:
        matched = False
        max_step = min(max_len, size - pos)
        for step in range(max_step, 0, -1):
            seq = tuple(seg[pos : pos + step])
            if seq in mapping:
                tokens.append(mapping[seq])
                pos += step
                matched = True
                break
        if not matched:
            return None
    return tokens


def iter_segments(data: bytes) -> Iterable[Tuple[int, memoryview]]:
    start = 0
    mv = memoryview(data)
    for idx, b in enumerate(mv):
        if b == 0xFF:
            if idx > start:
                yield start, mv[start:idx]
            start = idx + 1


def extract_text(rom_path: Path, charmap_path: Path, output_path: Path) -> None:
    mapping, max_len = load_charmap(charmap_path)
    data = rom_path.read_bytes()

    results: List[Tuple[int, str]] = []
    for offset, segment in iter_segments(data):
        tokens = decode_segment(segment, mapping, max_len)
        if tokens and looks_text(tokens):
            text = "".join(tokens)
            results.append((offset, text))

    lines = [f"0x{offset:06X}: {text}" for offset, text in results]
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Extracted {len(results)} strings to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract text strings from a FireRed-based GBA ROM.")
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM, help="Path to the .gba ROM")
    parser.add_argument("--charmap", type=Path, default=DEFAULT_CHARMAP, help="Charmap to use for decoding")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Where to write the extracted text",
    )
    args = parser.parse_args()

    extract_text(args.rom, args.charmap, args.output)


if __name__ == "__main__":
    main()
