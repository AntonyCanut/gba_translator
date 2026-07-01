#!/usr/bin/env python3
"""Translate zone-name and fly-banner texts that the generic pipeline cannot deliver.

Root cause
----------
The zone-name / fly-banner texts below are **not discovered by the pointer-text
extractor** (they live in address regions the extractor does not scan) and are
**too long to write in-place** (French text > English bytes available).  The
main builder therefore leaves them in English.  All correct French translations
already live in ``combined_fr.txt``.

This patch script closes the gap the same way
``patch_worldmap_junction_panels_fr.py`` does: encode each
``combined_fr.txt`` value, relocate it into free space, and repoint every
live referrer.

TARGETS
-------
==========  ==================  =================  ========  =======
ROM offset  English text        French text        EN bytes  FR bytes
==========  ==================  =================  ========  =======
0x071FC80   Blizzard City       Ville Blizzard     13        14
0x0B51EAC   Antisis Port        Port d'Antisis     12        14
0x078D811   Crater Town         Bourg Cratère      11        13
0x078D851   Blizzard City       Ville Blizzard     13        14
==========  ==================  =================  ========  =======

The patch is reference-driven (scans the whole ROM for live pointers to each
original offset) and idempotent: if all pointers to an offset have already been
repointed (i.e. ``find_referrers`` returns an empty list), the offset is
silently skipped.
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from src.core.text_codec import TextEncoder  # noqa: E402
from src.core.text_reinserter import FreeSpaceAllocator  # noqa: E402

from apply_inline_overrides_fr import (  # noqa: E402
    _apply_control_placeholders,
    _normalize_text,
    _read_raw_entry,
)

ROM_POINTER_BASE = 0x08000000
DEFAULT_COMBINED = REPO_ROOT / "languages/fr/combined_fr.txt"

# Offsets whose French translations are too long to write in-place and whose
# texts are not in the EN pointer extraction.  Value = short FR fragment used
# to verify the relocation landed correctly.
TARGETS: dict[int, str] = {
    0x071FC80: "Cimistral",        # Blizzard City  (zone-name table)
    0x0B51EAC: "Port d'Antésia",   # Antisis Port   (zone-name table)
    0x078D811: "Cratéris",         # Crater Town    (fly-banner cluster)
    0x078D851: "Cimistral",        # Blizzard City  (fly-banner cluster)
}

_OFFSET_LINE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")


def load_combined(path: Path) -> dict[int, str]:
    """Return last-wins offset → FR text mapping from ``combined_fr.txt``."""
    mapping: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _OFFSET_LINE.match(line)
        if m:
            mapping[int(m.group(1), 16)] = m.group(2)
    return mapping


def encode_relocated(text: str, source_rom: bytes, offset: int) -> bytes:
    """Encode a ``combined_fr.txt`` value to CFRU ROM bytes (incl. 0xFF)."""
    english = _read_raw_entry(source_rom, offset, "pokemon")
    normalized = _normalize_text(text)
    if english:
        normalized = _apply_control_placeholders(
            normalized, english.get("decoded_text"), english.get("raw_bytes")
        )
    return TextEncoder.encode(normalized, "pokemon")


def find_referrers(rom: bytes, offset: int) -> list[int]:
    """Return every cell in *rom* that holds a GBA pointer to *offset*."""
    needle = struct.pack("<I", ROM_POINTER_BASE + offset)
    return [m.start() for m in re.finditer(re.escape(needle), rom)]


def apply(
    rom: bytearray,
    combined: dict[int, str],
    source_rom: bytes,
    reserved_rom: bytes | None = None,
) -> dict:
    """Relocate each target and repoint all live referrers. Returns stats."""
    allocator = FreeSpaceAllocator(rom, reserved_rom=reserved_rom)
    stats = {
        "targets": 0,
        "repointed": 0,
        "no_source": 0,
        "failed": 0,
        "skipped": 0,
    }

    for offset in TARGETS:
        referrers = find_referrers(rom, offset)
        if not referrers:
            stats["skipped"] += 1
            continue
        text = combined.get(offset)
        if not text:
            stats["no_source"] += 1
            continue

        encoded = encode_relocated(text, source_rom, offset)
        new_offset = allocator.allocate(len(encoded))
        if new_offset is None:
            print(f"  ✗ 0x{offset:08X}: insufficient free space", file=sys.stderr)
            stats["failed"] += 1
            continue

        rom[new_offset: new_offset + len(encoded)] = encoded
        pointer = struct.pack("<I", new_offset + ROM_POINTER_BASE)
        for cell in referrers:
            rom[cell: cell + 4] = pointer
            stats["repointed"] += 1
        stats["targets"] += 1

    return stats


def verify(rom: bytes) -> list[tuple[int, str]]:
    """Return (offset, reason) for targets whose original is still referenced."""
    bad: list[tuple[int, str]] = []
    for offset, prefix in TARGETS.items():
        if find_referrers(rom, offset):
            bad.append((offset, "still points to original English text"))
            continue
        encoded_prefix = TextEncoder.encode(prefix, "pokemon")[:-1]  # drop 0xFF
        if encoded_prefix not in rom:
            bad.append((offset, f"French fragment {repr(prefix)} not found in ROM"))
    return bad


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rom",
        required=True,
        help="Built French ROM to patch in place",
    )
    parser.add_argument(
        "--source",
        default=str(REPO_ROOT / "input/roms/englishrom.gba"),
        help="English ROM (source of live control sequences)",
    )
    parser.add_argument(
        "--combined",
        default=str(DEFAULT_COMBINED),
        help="combined_fr.txt source of truth (offset → FR text)",
    )
    parser.add_argument(
        "--reference-rom",
        default=None,
        help="Reference ROM whose populated bytes must not be reused as free space",
    )
    args = parser.parse_args()

    rom_path = Path(args.rom)
    if not rom_path.exists():
        print(f"ROM not found: {rom_path}", file=sys.stderr)
        return 1

    rom = bytearray(rom_path.read_bytes())
    source_rom = Path(args.source).read_bytes()
    combined = load_combined(Path(args.combined))
    reserved = Path(args.reference_rom).read_bytes() if args.reference_rom else None

    stats = apply(rom, combined, source_rom, reserved_rom=reserved)
    remaining = verify(rom)
    rom_path.write_bytes(rom)

    print("✓ Zone-name & fly-banner texts — relocation + repointing:")
    print(f"   - Targets relocated:         {stats['targets']}")
    print(f"   - Pointers repointed:        {stats['repointed']}")
    if stats["skipped"]:
        print(f"   - Already relocated (skip):  {stats['skipped']}")
    if stats["no_source"]:
        print(f"   - No FR source in combined:  {stats['no_source']}")
    if stats["failed"]:
        print(f"   - FAILED (free space):       {stats['failed']}")
        return 1
    if remaining:
        print("   ✗ Verification failed:")
        for offset, why in remaining:
            print(f"     0x{offset:08X}: {why}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
