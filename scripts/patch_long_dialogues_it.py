#!/usr/bin/env python3
"""Inject Italian dialogues that exceed the extractor's length cap.

The pointer text extractor drops any string longer than
``max_text_length`` (1000 bytes — see
``src/extractors/pointer_text_extractor.py``). A handful of very long
Unbound dialogues (New Game+ intro, Battle Circus / Sands / Tower rules,
the champion congratulation) sit above that cap, so they never enter the
CSV/JSON flow and ship **English** even though ``combined_it.txt`` carries
a full Italian translation.

Those strings *do* have live pointers (unlike the fixed name tables), and
the generic pipeline leaves both the original text and its pointer
untouched (it never saw them). So the fix is a self-contained
relocate-and-repoint pass, identical in spirit to the RELOCATE branch of
``patch_intro_questions_it.py``:

    1. discover every over-cap offset dynamically — a ``combined_it.txt``
       entry in the main text region whose English source string is longer
       than the extractor cap;
    2. encode the full Italian text (always 0xFF-terminated → freeze-safe);
    3. write it into free space and repoint every live referrer.

This is a **cross-language** gap: FR and DE have the same over-cap
dialogues and no equivalent patch. This script is IT-specific for now; a
generic version would parameterise the combined file per language.

Usage:
    python3 scripts/patch_long_dialogues_it.py \\
        --rom output/roms/GenedRom-it.gba \\
        --combined languages/it/combined_it.txt \\
        --source input/roms/englishrom.gba
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.core.text_codec import TextEncoder  # noqa: E402
from src.core.text_reinserter import FreeSpaceAllocator  # noqa: E402

GBA_BASE = 0x08000000
MAIN_TEXT_START = 0x1F00000
# Must match src/extractors/pointer_text_extractor.py's default cap.
EXTRACTOR_MAX_TEXT_LENGTH = 1000

LINE_RE = re.compile(r'^\s*0x([0-9A-Fa-f]+)\s*:\s*(.*)$')

# combined_it.txt escapes → the form TextEncoder.encode expects.
#   \n -> line break   \l -> scroll (0xFA)   \p -> page break (0xFB)
#   \. -> '.'          \+ -> '+'   (escaped literals used by the translator)
_ESCAPES = (
    ("\\n", "\n"),
    ("\\l", "<0xFA>"),
    ("\\p", "<0xFB>"),
    ("\\.", "."),
    ("\\+", "+"),
)


def _normalize(text: str) -> str:
    for src, dst in _ESCAPES:
        text = text.replace(src, dst)
    return text


def _encode(text: str) -> bytes:
    return TextEncoder.encode(_normalize(text), "pokemon")


def _load_combined(path: Path) -> dict[int, str]:
    mapping: dict[int, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            match = LINE_RE.match(line.rstrip("\n"))
            if match:
                mapping[int(match.group(1), 16)] = match.group(2)
    return mapping


def _english_length(rom: bytes, offset: int, limit: int = 4000) -> int:
    """Length in bytes of the string at ``offset`` up to (excluding) 0xFF."""
    i = offset
    end = min(len(rom), offset + limit)
    while i < end and rom[i] != 0xFF:
        i += 1
    return i - offset


def _find_referrers(rom: bytes | bytearray, offset: int) -> list[int]:
    needle = struct.pack("<I", GBA_BASE + offset)
    return [m.start() for m in re.finditer(re.escape(needle), rom)]


def _write_ptr(rom: bytearray, cell: int, offset: int) -> None:
    struct.pack_into("<I", rom, cell, GBA_BASE + offset)


def find_overcap_offsets(source_rom: bytes, combined: dict[int, str]) -> list[int]:
    """combined_it offsets in the main text region whose EN source overflows
    the extractor cap (so the generic pipeline skips them)."""
    offsets = []
    for offset in sorted(combined):
        if offset < MAIN_TEXT_START or offset + 4 > len(source_rom):
            continue
        if _english_length(source_rom, offset) > EXTRACTOR_MAX_TEXT_LENGTH:
            offsets.append(offset)
    return offsets


def patch(rom: bytearray, combined: dict[int, str], source_rom: bytes) -> dict:
    stats = {"relocated": 0, "already": 0, "no_referrer": 0, "failed": 0}
    allocator = FreeSpaceAllocator(rom)

    for offset in find_overcap_offsets(source_rom, combined):
        encoded = _encode(combined[offset])
        referrers = _find_referrers(rom, offset)
        if not referrers:
            print(f"  0x{offset:08X}: no live pointer in ROM — skip")
            stats["no_referrer"] += 1
            continue

        # Idempotency: a referrer already pointing at a copy of the text.
        target = struct.unpack_from("<I", rom, referrers[0])[0] - GBA_BASE
        if 0 <= target < len(rom) and rom[target:target + len(encoded)] == encoded:
            print(f"  0x{offset:08X}: already translated at 0x{target:X} — skip")
            stats["already"] += 1
            continue

        new_offset = allocator.allocate(len(encoded))
        if new_offset is None:
            print(f"  0x{offset:08X}: free-space allocation failed "
                  f"({len(encoded)} bytes) — skip")
            stats["failed"] += 1
            continue

        rom[new_offset:new_offset + len(encoded)] = encoded
        for ref in referrers:
            _write_ptr(rom, ref, new_offset)
        print(f"  0x{offset:08X}: relocated {len(encoded)} bytes to "
              f"0x{new_offset:X}; repointed {len(referrers)} pointer(s)")
        stats["relocated"] += 1

    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path,
                        help="Built IT ROM to patch in place.")
    parser.add_argument("--combined", type=Path,
                        default=REPO_ROOT / "languages/it/combined_it.txt")
    parser.add_argument("--source", type=Path,
                        default=REPO_ROOT / "input/roms/englishrom.gba")
    args = parser.parse_args(argv)

    for label, path in (("ROM", args.rom), ("combined", args.combined),
                        ("source", args.source)):
        if not path.exists():
            print(f"✗ {label} not found: {path}", file=sys.stderr)
            return 1

    combined = _load_combined(args.combined)
    source_rom = args.source.read_bytes()
    rom = bytearray(args.rom.read_bytes())

    stats = patch(rom, combined, source_rom)
    args.rom.write_bytes(rom)

    print(
        "✓ long_dialogues_it: "
        f"{stats['relocated']} relocated, {stats['already']} already correct, "
        f"{stats['no_referrer']} without live pointer, {stats['failed']} failed"
    )
    if stats["failed"]:
        # Free-space exhaustion is a SOFT degradation, never a build breaker.
        # This step runs mid-pipeline (build_language.py invokes every step
        # with check=True), so a non-zero exit here aborts every later patch
        # — status_badges, hp_labels, dexnav_headers, … — and ships an
        # incomplete ROM. The generic IT builder can consume nearly all of
        # the ROM's free space, so a handful of these very long dialogues may
        # find no room; when that happens they stay English, exactly like the
        # `shop` / `cry_label` relocation steps (see their module docstrings).
        # We warn loudly but return 0 so the rest of the pipeline still runs.
        print(
            f"  WARN: {stats['failed']} long dialogue(s) left English — no free "
            "space to relocate them; the rest of the build continues."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
