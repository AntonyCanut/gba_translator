#!/usr/bin/env python3
"""Kill the give-CS / move-info freeze by terminating **every** consumer of an
overflowing French move/field-move description.

Root cause (found in-engine from the user's frozen ``.ss9`` savestate, then
confirmed statically against the built ROM):

Pokémon Unbound reads move descriptions through several pointer tables and
structs that all index the same description string pool:

* the « Capacités connues » summary table ``0x0899F190`` (relocated +
  re-wrapped by :mod:`scripts.patch_move_descriptions_fr`),
* a second move-info table ``0x08488708``,
* a third move-info table ``0x08904000``,
* the **field-move structs** (``0x083DEA80`` / ``0x0887AD30`` …) read on the
  give-CS path — e.g. Coupe/Cut's description lives at ``0x00482BD5``, which is
  an **empty** ``0xFF`` slot in English but holds a long French sentence after
  the build.

The generic builder writes the longer French text in place, so a description
routinely overruns its slot and destroys the next entry's ``0xFF`` terminator,
fusing a multi-hundred-byte run with no terminator at all. When the engine
word-wraps such a description (``GetStringWidth`` scans byte-by-byte for the
``0xFF``) the scan never ends → the CPU spins forever → the game freezes on the
« Alors, prends cette CS… » box and ignores all input. English never freezes
because its slots stay terminated.

The fix is **reference-driven** so no consumer is missed: scan the whole ROM
for word-aligned pointers into the description pool, keep only those whose
target is a *genuine, overflowing French description* (a strict text filter
that rejects the font table at ``0x489A08``, the data struct at ``0x489F74``
and Thumb code that coincidentally points into the region — repointing those
would corrupt the ROM, which is why a region-blind repoint is unsafe), then
relocate one ``0xFF``-terminated copy of the authoritative ``combined_fr.txt``
text per target and repoint *every* referrer to it. After this pass no live
pointer can reach an unterminated description, so the wrap scan always halts.
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.text_codec import TextDecoder, TextEncoder
from src.core.text_reinserter import FreeSpaceAllocator

ROM_POINTER_BASE = 0x08000000
# Address range of the move / field-move description string pool.
POOL_LO = 0x00482000
POOL_HI = 0x0048A000
# A genuine description word-wraps to the move-info window in well under this
# many bytes; a longer run to the next 0xFF means the slot lost its terminator.
OVERFLOW_THRESHOLD = 160
# Window decoded to decide whether an (unterminated) target is real French text.
TEXT_WINDOW = 110
DEFAULT_COMBINED = Path(__file__).resolve().parent.parent / "combined_fr.txt"

_OFFSET_LINE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")


def load_combined(path: Path) -> dict[int, str]:
    """original ROM offset -> French text (last entry wins, per combined_fr.txt)."""
    mapping: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _OFFSET_LINE.match(line)
        if m:
            mapping[int(m.group(1), 16)] = m.group(2)
    return mapping


def encode_text(text: str) -> bytes:
    """Encode a combined_fr.txt value (literal ``\\n`` -> newline) + 0xFF."""
    return TextEncoder.encode_pokemon(text.replace("\\n", "\n"))


def is_overflow(rom: bytes, offset: int) -> bool:
    """True when no 0xFF terminator is reachable within the slot budget."""
    end = rom.find(b"\xff", offset, offset + OVERFLOW_THRESHOLD + 1)
    return end < 0


def is_french_description(rom: bytes, offset: int) -> bool:
    """Strict guard: does ``offset`` begin a real French description?

    Rejects the font/data tables and Thumb code that also point into the pool
    (textscore alone is fooled by sequential-charmap data, so we additionally
    require word spacing, a French vowel density and no single dominant glyph).
    """
    raw = bytes(rom[offset:offset + TEXT_WINDOW])
    text = TextDecoder.decode_pokemon(raw, preserve_unknown=True)
    if len(text) < 20:
        return False
    letters = sum(ch.isalpha() for ch in text)
    if letters / len(text) < 0.72:
        return False
    if (text.count(" ") + text.count("\n")) < 3:
        return False
    vowels = sum(text.lower().count(v) for v in "eaiou")
    if vowels / max(letters, 1) < 0.25:
        return False
    counts = Counter(ch for ch in text if ch not in " \n")
    if counts and counts.most_common(1)[0][1] / max(letters, 1) > 0.5:
        return False
    return True


def apply(rom: bytearray, combined: dict[int, str],
          reserved_rom: bytes | None = None) -> dict:
    allocator = FreeSpaceAllocator(rom, reserved_rom=reserved_rom)
    stats = {"referrers": 0, "targets": 0, "repointed": 0,
             "no_source": 0, "rejected": 0, "failed": 0}

    # 1) Collect every word-aligned pointer into the pool whose target is a
    #    genuine, overflowing French description -> {target: [referrer cells]}.
    referrers: dict[int, list[int]] = {}
    rejected: set[int] = set()
    base, end = 0, len(rom) - 4
    for cell in range(base, end, 4):
        value = int.from_bytes(rom[cell:cell + 4], "little")
        if not (ROM_POINTER_BASE + POOL_LO <= value < ROM_POINTER_BASE + POOL_HI):
            continue
        target = value - ROM_POINTER_BASE
        if not is_overflow(rom, target):
            continue
        if not is_french_description(rom, target):
            rejected.add(target)
            continue
        referrers.setdefault(target, []).append(cell)

    stats["rejected"] = len(rejected)
    stats["targets"] = len(referrers)
    stats["referrers"] = sum(len(v) for v in referrers.values())

    # 2) Relocate one terminated copy per target and repoint all its referrers.
    for target, cells in referrers.items():
        text = combined.get(target)
        if text is None:
            # Genuine description with no authoritative text. Its only referrers
            # are scattered singletons (likely code constants), never the dense
            # tables/structs read on the give-CS path, so skipping it cannot
            # reintroduce the freeze. Leave it untouched rather than relocate an
            # unknown-length blob.
            stats["no_source"] += 1
            continue

        encoded = encode_text(text)
        new_offset = allocator.allocate(len(encoded))
        if new_offset is None:
            stats["failed"] += 1
            continue
        rom[new_offset:new_offset + len(encoded)] = encoded
        pointer = struct.pack("<I", new_offset + ROM_POINTER_BASE)
        for cell in cells:
            rom[cell:cell + 4] = pointer
            stats["repointed"] += 1

    return stats


def verify(rom: bytes, combined: dict[int, str]) -> list[tuple[int, int]]:
    """Return any remaining (cell, target) where a live pointer still reaches an
    overflowing description that we had authoritative text for (must be empty)."""
    bad = []
    for cell in range(0, len(rom) - 4, 4):
        value = int.from_bytes(rom[cell:cell + 4], "little")
        if not (ROM_POINTER_BASE + POOL_LO <= value < ROM_POINTER_BASE + POOL_HI):
            continue
        target = value - ROM_POINTER_BASE
        if (is_overflow(rom, target)
                and is_french_description(rom, target)
                and target in combined):
            bad.append((cell, target))
    return bad


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, help="Built French ROM to patch in place")
    parser.add_argument("--combined", default=str(DEFAULT_COMBINED),
                        help="combined_fr.txt source of truth (offset -> FR text)")
    parser.add_argument("--reference-rom", default=None,
                        help="Same-base ROM whose populated bytes must not be reused as free space")
    args = parser.parse_args()

    rom_path = Path(args.rom)
    rom = bytearray(rom_path.read_bytes())
    combined = load_combined(Path(args.combined))
    reserved = Path(args.reference_rom).read_bytes() if args.reference_rom else None

    stats = apply(rom, combined, reserved_rom=reserved)

    remaining = verify(rom, combined)
    rom_path.write_bytes(rom)

    print("✓ Descriptions d'attaque dupliquées / structs CS (anti-freeze give-CS):")
    print(f"   - Cibles débordantes:   {stats['targets']}")
    print(f"   - Pointeurs trouvés:    {stats['referrers']}")
    print(f"   - Pointeurs repointés:  {stats['repointed']}")
    print(f"   - Rejetées (data/code): {stats['rejected']}")
    if stats["no_source"]:
        print(f"   - Sans source (skip):  {stats['no_source']}")
    if stats["failed"]:
        print(f"   - ÉCHECS (free space): {stats['failed']}")
        return 1
    if remaining:
        print(f"   - ✗ RESTE {len(remaining)} pointeurs vers une description non terminée:")
        for cell, target in remaining[:10]:
            print(f"       0x{cell + ROM_POINTER_BASE:08x} -> 0x{target:08x}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
