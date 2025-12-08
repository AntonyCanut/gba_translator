#!/usr/bin/env python3
"""
Extract the one-byte charmap from a GBA ROM.

The ROM in chargemap/extractchargemap.gba contains a block that lists every
byte value (0x00-0xFF) used by the text engine. We locate the smallest window
that contains all 256 byte values, keep the first occurrence order inside that
window, and pair those bytes with labels from an existing charmap file
(default: charmap_firered.txt). Multi-byte control codes are copied verbatim
from the base charmap so the output stays compatible with the translation
tools already in this repo.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

DEFAULT_ROM = Path("chargemap/extractchargemap.gba")
DEFAULT_CHARMAP = Path("charmap_firered.txt")
DEFAULT_OUTPUT = Path("chargemap/extracted_charmap.txt")


def parse_charmap(path: Path) -> Tuple[Dict[int, str], List[Tuple[str, Tuple[int, ...]]]]:
    """Return (single_byte_labels, multi_byte_entries)."""
    singles: Dict[int, str] = {}
    multi: List[Tuple[str, Tuple[int, ...]]] = []

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("@", 1)[0].strip()
        if not line or "=" not in line:
            continue

        left, right = [part.strip() for part in line.rsplit("=", 1)]
        try:
            seq = tuple(int(tok, 16) for tok in right.split())
        except ValueError:
            continue

        if not seq:
            continue
        if len(seq) == 1:
            # Keep the first label we see for a given byte value.
            singles.setdefault(seq[0], left)
        else:
            multi.append((left, seq))

    return singles, multi


def find_charmap_window(data: bytes) -> Tuple[int, bytes, List[int]]:
    """Find the smallest slice that contains all 256 byte values.

    Returns (start_offset, window_bytes, order_of_first_occurrences).
    """
    counts: defaultdict[int, int] = defaultdict(int)
    unique = 0
    best_start = best_len = None
    start = 0

    for end, value in enumerate(data):
        if counts[value] == 0:
            unique += 1
        counts[value] += 1

        while unique == 256:
            length = end - start + 1
            if best_len is None or length < best_len:
                best_start, best_len = start, length
            # Slide the window
            left_val = data[start]
            counts[left_val] -= 1
            if counts[left_val] == 0:
                unique -= 1
            start += 1

    if best_start is None or best_len is None:
        raise ValueError("Impossible de trouver une fenetre contenant les 256 valeurs.")

    window = data[best_start : best_start + best_len]
    seen: set[int] = set()
    order: List[int] = []
    for b in window:
        if b not in seen:
            seen.add(b)
            order.append(b)

    if len(order) != 256:
        raise ValueError(f"Fenetre trouvee mais seulement {len(order)} valeurs uniques detectees.")

    return best_start, window, order


def format_hex(seq: Sequence[int]) -> str:
    return " ".join(f"{b:02X}" for b in seq)


def build_output_lines(
    single_labels: Dict[int, str],
    multi_entries: List[Tuple[str, Tuple[int, ...]]],
    byte_order: List[int],
) -> List[str]:
    # Bytes that serve as prefixes for multi-byte control codes; if they have
    # no explicit single-byte label we skip them to avoid noisy placeholders.
    prefix_bytes = {entry[1][0] for entry in multi_entries if entry[1]}

    singles: List[Tuple[int, str]] = []
    for code in byte_order:
        label = single_labels.get(code)
        if label is None:
            if code in prefix_bytes:
                continue
            label = f"UNK_{code:02X}"
        singles.append((code, label))

    # Sort by code for readability (matches charmap_firered style).
    singles.sort(key=lambda item: item[0])

    max_left = max(
        [len(lbl) for _, lbl in singles]
        + [len(lbl) for lbl, _ in multi_entries]
        + [8]
    )

    lines = [
        f"{label.ljust(max_left)} = {code:02X}" for code, label in singles
    ]
    lines.extend(
        f"{label.ljust(max_left)} = {format_hex(seq)}" for label, seq in multi_entries
    )
    return lines


def extract_charmap(rom_path: Path, base_charmap: Path, output_path: Path) -> None:
    data = rom_path.read_bytes()
    start, window, order = find_charmap_window(data)

    single_labels, multi_entries = parse_charmap(base_charmap)
    lines = build_output_lines(single_labels, multi_entries, order)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        f"Charmap extraite depuis {rom_path} (fenetre 0x{start:X}-0x{start+len(window):X}, "
        f"{len(window)} octets) vers {output_path}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrait la charmap 1 octet depuis une ROM GBA.")
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM, help="ROM source (.gba)")
    parser.add_argument(
        "--base-charmap",
        type=Path,
        default=DEFAULT_CHARMAP,
        help="Charmap de reference (sert a nommer les codes et inclure les sequences multi-octets).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Fichier charmap de sortie.",
    )
    args = parser.parse_args()

    extract_charmap(args.rom, args.base_charmap, args.output)


if __name__ == "__main__":
    main()
