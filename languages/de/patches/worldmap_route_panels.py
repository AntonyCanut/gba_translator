#!/usr/bin/env python3
"""Repoint DE World Map panels to exact source-controlled text.

The generic reinserter preserves the arrows but collapses the first ``\\n`` of
route panels, placing the route number and its nickname on one rendered line.
This late patch follows the stable English pointer cells, writes one exact
``combined_de.txt`` body, and repoints those cells after every generic pass.
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from languages.fr.patches.worldmap_junction_panels import (  # noqa: E402
    encode_relocated,
    load_combined,
)
from scripts.audit_arrow_line_start_fr import english_is_panel  # noqa: E402
from src.core.text_reinserter import FreeSpaceAllocator  # noqa: E402

GBA_BASE = 0x08000000
DE_COMBINED = REPO_ROOT / "languages/de/combined_de.txt"
EN_ROM = REPO_ROOT / "input/roms/englishrom.gba"


def _referrers(rom: bytes, offset: int) -> list[int]:
    needle = struct.pack("<I", GBA_BASE + offset)
    return [match.start() for match in re.finditer(re.escape(needle), rom)]


def _live_raw(rom: bytes, slot: int, limit: int = 512) -> bytes | None:
    pointer = struct.unpack_from("<I", rom, slot)[0]
    offset = pointer - GBA_BASE
    if not 0 <= offset < len(rom):
        return None
    end = rom.find(b"\xff", offset, min(len(rom), offset + limit))
    return None if end < 0 else rom[offset : end + 1]


def discover_panels(combined: dict[int, str], source_rom: bytes) -> tuple[int, ...]:
    return tuple(
        offset
        for offset in sorted(combined)
        if 0x1F70D00 <= offset <= 0x1F72950
        and english_is_panel(source_rom, offset)
    )


def apply(
    rom: bytearray,
    combined: dict[int, str],
    source_rom: bytes,
    panel_offsets: tuple[int, ...] | None = None,
) -> dict[str, int]:
    offsets = panel_offsets or discover_panels(combined, source_rom)
    allocator = FreeSpaceAllocator(rom, reserved_rom=None)
    stats = {"relocated": 0, "repointed": 0, "skipped": 0, "failed": 0}
    for offset in offsets:
        slots = _referrers(source_rom, offset)
        text = combined.get(offset)
        if not slots or not text:
            stats["skipped"] += 1
            continue
        expected = encode_relocated(text, source_rom, offset)
        if all(_live_raw(rom, slot) == expected for slot in slots):
            stats["skipped"] += 1
            continue
        target = allocator.allocate(len(expected))
        if target is None:
            stats["failed"] += 1
            continue
        rom[target : target + len(expected)] = expected
        pointer = struct.pack("<I", GBA_BASE + target)
        for slot in slots:
            rom[slot : slot + 4] = pointer
            stats["repointed"] += 1
        stats["relocated"] += 1
    return stats


def verify(
    rom: bytes,
    combined: dict[int, str],
    source_rom: bytes,
    panel_offsets: tuple[int, ...] | None = None,
) -> list[tuple[int, str]]:
    offsets = panel_offsets or discover_panels(combined, source_rom)
    failures: list[tuple[int, str]] = []
    for offset in offsets:
        text = combined.get(offset)
        slots = _referrers(source_rom, offset)
        if not text or not slots:
            failures.append((offset, "missing source text or live pointer"))
            continue
        expected = encode_relocated(text, source_rom, offset)
        for slot in slots:
            if _live_raw(rom, slot) != expected:
                failures.append((offset, f"pointer 0x{slot:08X} differs"))
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--source", type=Path, default=EN_ROM)
    parser.add_argument("--combined", type=Path, default=DE_COMBINED)
    args = parser.parse_args()
    rom = bytearray(args.rom.read_bytes())
    source = args.source.read_bytes()
    combined = load_combined(args.combined)
    stats = apply(rom, combined, source)
    failures = verify(rom, combined, source)
    args.rom.write_bytes(rom)
    print("✓ DE World-Map route panels — exact controls + repointing:")
    print(f"   - Panels relocated:  {stats['relocated']}")
    print(f"   - Pointers repointed: {stats['repointed']}")
    print(f"   - Already exact:      {stats['skipped']}")
    if stats["failed"] or failures:
        print(f"   - Failures:           {stats['failed'] + len(failures)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
