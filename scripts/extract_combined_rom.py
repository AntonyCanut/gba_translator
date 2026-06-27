#!/usr/bin/env python3
"""
Extract text from a GBA ROM at the offsets defined in a combined_*.txt reference file.

Reads each offset from the reference, decodes the CFRU/Pokémon string at that position
in the target ROM, and writes a new combined_*.txt in the same format.

Usage:
    python3 scripts/extract_combined_rom.py \\
        --rom input/roms/englishrom.gba \\
        --ref languages/fr/combined_fr.txt \\
        --out languages/en/combined_en.txt \\
        [--lang EN]

The output preserves every line (including duplicate offsets) so the line count
matches the reference.  Control bytes that have no named mapping are written as
<0xNN> hex tokens.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.text_codec import TextDecoder

POKEMON_TERMINATOR = 0xFF
MAX_STRING_LENGTH = 512  # safety cap to avoid reading garbage


def read_cfru_string(rom: bytes, offset: int) -> str:
    """Read a CFRU-encoded string from *rom* starting at *offset*.

    Returns the decoded string with unknown/control bytes as <0xNN> tokens.
    Multi-byte CFRU control sequences (FD xx, FC xx [yy], F8/F9/F7 xx) are
    preserved as consecutive <0xNN> tokens — sufficient for a reference file.
    """
    end = min(offset + MAX_STRING_LENGTH, len(rom))
    raw = bytearray()
    pos = offset
    while pos < end:
        b = rom[pos]
        if b == POKEMON_TERMINATOR:
            break
        raw.append(b)
        pos += 1
    return TextDecoder.decode_pokemon(bytes(raw), preserve_unknown=True)


def parse_combined(path: Path) -> list[tuple[str, str | None]]:
    """Return list of (raw_line, offset_or_None) for every line in a combined file.

    Comment lines and blank lines are kept as-is (offset=None).
    Translation lines yield the original offset string (e.g. '0x028780').
    """
    result = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r'^(0x[0-9a-fA-F]+):\s*', raw_line)
        if m:
            result.append((raw_line, m.group(1)))
        else:
            result.append((raw_line, None))
    return result


def extract(
    rom_path: Path,
    ref_path: Path,
    out_path: Path,
    lang: str = "EN",
) -> int:
    rom = rom_path.read_bytes()
    rom_size = len(rom)
    ref_lines = parse_combined(ref_path)

    out_lines: list[str] = []
    translated = 0
    errors = 0

    for raw_line, offset_str in ref_lines:
        if offset_str is None:
            # Blank / comment line — preserve as-is unless it's the header comment
            out_lines.append(raw_line)
            continue

        offset = int(offset_str, 16)
        if offset >= rom_size:
            out_lines.append(f"{offset_str}: <out-of-range>")
            errors += 1
            continue

        text = read_cfru_string(rom, offset)
        # Normalise newlines to \n escape (same convention as combined_fr.txt)
        text = text.replace("\n", "\\n")
        out_lines.append(f"{offset_str}: {text}")
        translated += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")

    print(
        f"  {lang}: wrote {translated} entries, {errors} errors → {out_path}",
        file=sys.stderr,
    )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path, help="GBA ROM to extract from")
    parser.add_argument(
        "--ref",
        default=Path("languages/fr/combined_fr.txt"),
        type=Path,
        help="Reference combined file that supplies the offset list",
    )
    parser.add_argument("--out", required=True, type=Path, help="Output combined_*.txt path")
    parser.add_argument("--lang", default="", help="Language label for progress output")
    args = parser.parse_args()

    if not args.rom.exists():
        print(f"ERROR: ROM not found: {args.rom}", file=sys.stderr)
        return 1
    if not args.ref.exists():
        print(f"ERROR: Reference file not found: {args.ref}", file=sys.stderr)
        return 1

    errors = extract(args.rom, args.ref, args.out, lang=args.lang or args.out.stem)
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
