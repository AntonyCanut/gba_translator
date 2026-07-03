#!/usr/bin/env python3
"""Re-wrap every German Pokédex description to the 3-line info window.

Port of ``patch_pokedex_fr.py``. The Pokédex info screen shows a species
description in a window that fits at most three lines (see
:mod:`src.core.pokedex`). Generic-build translations inherit the English
break positions and routinely spill onto a fourth line; this is entirely
language-agnostic logic — it re-wraps whatever text the German build already
translated (from ``combined_de.txt`` via the generic pipeline), it does not
carry any German-specific wording itself.

This post-build step fixes both, working directly on the built ROM so it
is immune to the repair/repoint passes that run before it:

1. For every Pokédex entry it takes the authoritative German text — a
   curated short rewrite from ``languages/de/data/pokedex_de_overrides.json``
   when the description is too verbose to fit three lines, otherwise the
   full translation from the translation JSON.
2. It re-wraps that text to <= 3 lines within the window width and encodes
   it.
3. It writes the result at the entry's current description pointer when it
   fits the slot, otherwise relocates it into ROM free space and repoints
   the struct — exactly the lossless strategy the builder uses elsewhere.

Re-wrapping never changes a description's wording, only its line breaks;
shortening only ever applies the human-reviewed overrides.

A description that is too *dense* to also stay within the reference line
width is never a build failure: ``rewrap`` still guarantees at most three
lines (it can never spill onto a fourth), so the entry renders inside the
box. The width overflow is counted separately and reported as a warning —
the remedy is to add a curated short rewrite in
``languages/de/data/pokedex_de_overrides.json``. The build only aborts on a
genuine *structural* failure (an unreadable description pointer).
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core import pokedex
from src.core.text_codec import TextDecoder, TextEncoder
from src.core.text_reinserter import FreeSpaceAllocator

ROM_POINTER_BASE = 0x08000000
DEFAULT_OVERRIDES = (
    Path(__file__).resolve().parent.parent
    / "languages" / "de" / "data" / "pokedex_de_overrides.json"
)


def _deref(rom, offset: int):
    if offset + 4 > len(rom):
        return None
    value = int.from_bytes(rom[offset:offset + 4], "little")
    if ROM_POINTER_BASE <= value < ROM_POINTER_BASE + 0x02000000:
        return value - ROM_POINTER_BASE
    return None


def _slot_capacity(data, offset: int, limit: int = 400) -> int:
    """Bytes available at ``offset`` up to and including the 0xFF terminator."""
    end = data.find(b"\xff", offset)
    if end < 0 or end - offset > limit:
        return 0
    return end - offset + 1


def load_text_map(translations_path: Path) -> dict:
    """offset -> full German translation, from the build's translation JSON."""
    payload = json.loads(translations_path.read_text(encoding="utf-8"))
    items = payload["translations"] if isinstance(payload, dict) else payload
    return {item["offset"]: item["translation"] for item in items}


def apply(
    rom: bytearray,
    source: bytes,
    text_map: dict,
    overrides: dict,
    reserved_rom: bytes | None = None,
) -> dict:
    """Re-wrap/relocate every Pokédex description in ``rom`` (mutated)."""
    allocator = FreeSpaceAllocator(rom, reserved_rom=reserved_rom)
    stats = {"total": 0, "rewrapped": 0, "relocated": 0, "shortened": 0,
             "skipped": 0, "skip_no_space": 0, "failed": 0, "unchanged": 0,
             "overflow": 0}

    for entry in pokedex.iter_entries(source):
        stats["total"] += 1
        offset = entry.text_offset

        # Authoritative German text: a curated short rewrite first, then the
        # full translation when it is a real description, and finally the
        # source description. The translation JSON occasionally maps a dex
        # offset to a non-description (an ability/move name that shares the
        # extracted offset); the dex struct still points at the species
        # text in the source ROM, so fall back to it.
        override = overrides.get(str(offset))
        if override is None:
            override = overrides.get(offset)
        json_text = text_map.get(offset)
        shortened = override is not None
        if override is not None:
            text = override
        elif json_text is not None and pokedex.is_description(json_text):
            text = json_text
        else:
            text = entry.text  # source species description

        wrapped = pokedex.rewrap(text)
        # ``rewrap`` always lays the text out in at most DEX_MAX_LINES lines, so
        # a description can never spill onto a fourth line. When the wording is
        # too dense to also stay within the reference line width, ``fits`` is
        # False: this is a width overflow, not a display *failure*. We still
        # write the best-effort 3-line layout (far better than leaving the
        # English break positions, which spill vertically) and only flag it so
        # the build completes and the length work is tracked separately. A
        # curated short rewrite in the overrides JSON is the way to bring such
        # an entry fully within the width.
        overflow = not pokedex.fits(wrapped)
        if overflow:
            stats["overflow"] += 1

        encoded = TextEncoder.encode_pokemon(wrapped)

        target = _deref(rom, entry.struct_offset)
        if target is None:
            stats["failed"] += 1
            continue

        # Only overwrite the slot in place when it genuinely still holds a
        # species description that fits. A slot now holding a shorter shared
        # string (collision) or an over-long fused run must be relocated so
        # the in-place write never clobbers a neighbour.
        current_end = rom.find(b"\xff", target)
        current = rom[target:current_end + 1] if 0 <= current_end - target <= 400 else b""
        if current == encoded:
            stats["unchanged"] += 1
            if shortened:
                stats["shortened"] += 1
            continue

        slot_holds_description = bool(current) and pokedex.is_description(
            TextDecoder.decode_pokemon(current[:-1], preserve_unknown=True)
        )

        if target == offset:
            capacity = _slot_capacity(source, offset)
        else:
            capacity = _slot_capacity(rom, target)

        if slot_holds_description and len(encoded) <= capacity:
            rom[target:target + len(encoded)] = encoded
        else:
            new_offset = allocator.allocate(len(encoded))
            if new_offset is None:
                # Insufficient free space to relocate. We cannot improve the
                # entry, so leave whatever the build already wrote in place and
                # record a benign skip — the build is never failed over free
                # space (any overflow is already tracked via ``overflow``).
                stats["skip_no_space"] += 1
                continue
            rom[new_offset:new_offset + len(encoded)] = encoded
            pointer = struct.pack("<I", new_offset + ROM_POINTER_BASE)
            rom[entry.struct_offset:entry.struct_offset + 4] = pointer
            stats["relocated"] += 1

        stats["rewrapped"] += 1
        if shortened:
            stats["shortened"] += 1

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, help="Built German ROM to patch in place")
    parser.add_argument("--source", required=True, help="Source English ROM (description layout)")
    parser.add_argument("--translations", required=True, help="Build translation_ready.json")
    parser.add_argument("--overrides", default=str(DEFAULT_OVERRIDES),
                        help="Curated short-description overrides JSON")
    parser.add_argument("--reference-rom", default=None,
                        help="Same-base ROM whose populated bytes must not be reused as free space")
    args = parser.parse_args()

    rom_path = Path(args.rom)
    rom = bytearray(rom_path.read_bytes())
    source = Path(args.source).read_bytes()
    text_map = load_text_map(Path(args.translations))
    overrides_path = Path(args.overrides)
    overrides = json.loads(overrides_path.read_text(encoding="utf-8")) if overrides_path.exists() else {}
    reserved = Path(args.reference_rom).read_bytes() if args.reference_rom else None

    stats = apply(rom, source, text_map, overrides, reserved_rom=reserved)
    rom_path.write_bytes(rom)

    print("✓ Pokédex 3-line rewrap (DE):")
    print(f"   - Entries processed:  {stats['total']}")
    print(f"   - Rewrapped (<=3l):   {stats['rewrapped']}")
    print(f"   - Already compliant:  {stats['unchanged']}")
    print(f"   - Relocated:          {stats['relocated']}")
    print(f"   - Shortened (data):   {stats['shortened']}")
    if stats["skipped"]:
        print(f"   - No translation:     {stats['skipped']}")
    if stats["skip_no_space"]:
        print(f"   - Kept in place (no space): {stats['skip_no_space']}")
    if stats["overflow"]:
        # Width-only overflow: rendered on <=3 lines but a line is wider than
        # the reference width. Not a build failure — tracked so the wording can
        # be shortened later via languages/de/data/pokedex_de_overrides.json.
        print(f"   - Width overflow (<=3l, tracked): {stats['overflow']}")
    if stats["failed"]:
        # Reserved for genuine structural failures (an unreadable description
        # pointer), which must still abort the build.
        print(f"   - FAILED (structural): {stats['failed']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
