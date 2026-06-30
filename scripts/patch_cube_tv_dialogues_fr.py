#!/usr/bin/env python3
"""Translate the Cube V3 prologue + Borrius TV-mission dialogues that the
generic pipeline leaves in English (B-98).

Root cause (found statically against the built French ROM):

Each target *is* present in the English extraction and *does* have a
``translation_ready.json`` entry, but the entry is ``too_long`` for its
in-place slot. The generic relocation pass (``--allow-relocate``) only
repoints pointer sites that ``_plausible_pointer_sites``
(:mod:`src.core.text_reinserter`) recognises as a genuine text reference —
4-byte aligned cells, or a small set of known script-opcode shapes
(``loadpointer``, ``bufferstring``, ``preparemsg``, ``trainerbattle``...).
That heuristic is intentionally conservative (a previous over-eager pass
corrupted the battle engine), so any other site is left untouched, still
holding the address of the original — English — string.

``0x1F01074`` (Mom's "Is that a Super Cube in your pocket?" prologue line)
and ``0x1FB052C`` (the TV-mission scientist's opening line) are already
fully migrated by the generic pass — their only referrer was a recognised
shape and now points at a relocated French copy. ``0x1FB07FE`` (the
TV-mission "you still have yet to gather data" follow-up) has *two*
referrers in the English ROM; the generic pass repointed one (a recognised
``loadpointer`` site) but left the other — preceded by an unrecognised
opcode byte — pointing at the dead English original, so the built ROM still
shows English there.

This post-build patch closes that gap the same way
:mod:`patch_meteorite_dialogue_fr` and :mod:`patch_worldmap_junction_panels_fr`
do: encode each ``combined_fr.txt`` value with the shared control-code
machinery, relocate one ``0xFF``-terminated copy into free space, and
repoint **every** live referrer to it. It is reference-driven (scans the
whole ROM for live pointers to each original offset) and idempotent — a
target whose original is no longer pointed at (already fully migrated, as
with the first two offsets above) is skipped.
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

# original English offset -> a short, contiguous French prefix used to prove
# the relocation landed (must appear verbatim before any line/page break).
TARGETS: dict[int, str] = {
    0x1F01074: "C'est un Super Cube dans ta",      # Mom, prologue
    0x1FB052C: "Qu'avez-vous dit ?",                 # TV-mission, opening line
    0x1FB07FE: "Vous n'avez pas encore rassemblé\nde données",  # TV-mission, follow-up
}

_OFFSET_LINE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")


def load_combined(path: Path) -> dict[int, str]:
    """original ROM offset -> French text (last entry wins, per combined_fr.txt)."""
    mapping: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _OFFSET_LINE.match(line)
        if m:
            mapping[int(m.group(1), 16)] = m.group(2)
    return mapping


def encode_relocated(text: str, source_rom: bytes, offset: int) -> bytes:
    """Encode a ``combined_fr.txt`` value to ROM bytes (incl. 0xFF terminator)."""
    english = _read_raw_entry(source_rom, offset, "pokemon")
    normalized = _normalize_text(text)
    if english:
        normalized = _apply_control_placeholders(
            normalized, english.get("decoded_text"), english.get("raw_bytes")
        )
    return TextEncoder.encode(normalized, "pokemon")


def find_referrers(rom: bytes, offset: int) -> list[int]:
    """Every ROM cell holding a 32-bit LE pointer to ``ROM_POINTER_BASE+offset``."""
    needle = struct.pack("<I", ROM_POINTER_BASE + offset)
    return [m.start() for m in re.finditer(re.escape(needle), rom)]


def apply(
    rom: bytearray,
    combined: dict[int, str],
    source_rom: bytes,
    reserved_rom: bytes | None = None,
) -> dict:
    allocator = FreeSpaceAllocator(rom, reserved_rom=reserved_rom)
    stats = {"targets": 0, "repointed": 0, "no_source": 0, "failed": 0, "skipped": 0}

    for offset in TARGETS:
        referrers = find_referrers(rom, offset)
        if not referrers:
            # Nothing points at the original string any more — already
            # relocated by the generic pass or a previous run.
            stats["skipped"] += 1
            continue
        text = combined.get(offset)
        if not text:
            stats["no_source"] += 1
            continue

        encoded = encode_relocated(text, source_rom, offset)
        new_offset = allocator.allocate(len(encoded))
        if new_offset is None:
            stats["failed"] += 1
            continue
        rom[new_offset : new_offset + len(encoded)] = encoded
        pointer = struct.pack("<I", new_offset + ROM_POINTER_BASE)
        for cell in referrers:
            rom[cell : cell + 4] = pointer
            stats["repointed"] += 1
        stats["targets"] += 1

    return stats


def verify(rom: bytes) -> list[tuple[int, str]]:
    """Return targets whose live pointer still reaches the English original."""
    bad: list[tuple[int, str]] = []
    for offset, prefix in TARGETS.items():
        if find_referrers(rom, offset):
            bad.append((offset, "still points to original"))
            continue
        encoded_prefix = TextEncoder.encode(prefix, "pokemon")[:-1]  # drop 0xFF
        if encoded_prefix not in rom:
            bad.append((offset, "French prefix not found in ROM"))
    return bad


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, help="Built French ROM to patch in place")
    parser.add_argument(
        "--source",
        default=str(REPO_ROOT / "input/roms/englishrom.gba"),
        help="English ROM (source of live control sequences)",
    )
    parser.add_argument(
        "--combined",
        default=str(DEFAULT_COMBINED),
        help="combined_fr.txt source of truth (offset -> FR text)",
    )
    parser.add_argument(
        "--reference-rom",
        default=None,
        help="Same-base ROM whose populated bytes must not be reused as free space",
    )
    args = parser.parse_args()

    rom_path = Path(args.rom)
    rom = bytearray(rom_path.read_bytes())
    source_rom = Path(args.source).read_bytes()
    combined = load_combined(Path(args.combined))
    reserved = Path(args.reference_rom).read_bytes() if args.reference_rom else None

    stats = apply(rom, combined, source_rom, reserved_rom=reserved)
    remaining = verify(rom)
    rom_path.write_bytes(rom)

    print("✓ Cube V3 prologue & TV-mission dialogues — relocation + repointing:")
    print(f"   - Targets relocated:      {stats['targets']}")
    print(f"   - Pointers repointed:     {stats['repointed']}")
    if stats["skipped"]:
        print(f"   - Already relocated (skip): {stats['skipped']}")
    if stats["no_source"]:
        print(f"   - No FR source:           {stats['no_source']}")
    if stats["failed"]:
        print(f"   - FAILED (free space):    {stats['failed']}")
        return 1
    if remaining:
        print("   - ✗ Verification failed:")
        for offset, why in remaining:
            print(f"       0x{offset:08X}: {why}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
