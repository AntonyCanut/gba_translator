#!/usr/bin/env python3
"""Audit hard-coded table offsets in the DE/IT/FR post-build patch scripts
against the clean vanilla base ROM.

Background (R-17 / T-38): ``input/roms/englishrom.gba`` used to be a
French-*patched* Unbound ROM. The FR build had **relocated** several
fixed-width tables into free space and repointed the engine's code references
there, so tables such as the move-name table appeared to "live" at low free-
space offsets (e.g. 0x1B2980). Patch scripts reverse-engineered against that
contaminated base hard-coded those relocation targets. After R-17 the shared
base is a genuinely clean vanilla ROM (the old file survives as
``patchedfrenchrom.gba``, used only by ``build-fr``), where those relocation
targets are unreferenced 0xFF free space and the tables sit at their stock
addresses again.

This tool flags every hard-coded offset whose *pointer liveness inverted*
between the two bases — i.e. an offset that IS referenced by a 32-bit ROM
pointer on the old patched base but is NOT on the clean base. Those are the
patches that silently write to dead free space on the clean base and must be
fixed (see ``languages/fr/patches/move_names.py`` for the canonical fix:
resolve the live base from the ROM pointer instead of hard-coding it).

A "dead on both bases" offset is NOT flagged: it is either a code/ASM patch
site, LZ77 graphics data, or a fixed-table *field* offset the engine reaches by
index arithmetic from a base pointer — none of which moved between the two
bases, so the patch behaves identically on either.

Usage::

    python3 scripts/audit_clean_base_offsets.py
    python3 scripts/audit_clean_base_offsets.py \\
        --clean input/roms/englishrom.gba \\
        --patched input/roms/patchedfrenchrom.gba

Exit status is non-zero if any inverted (broken-on-clean) offset is found, so
the script doubles as a CI guard against a future contaminated base sneaking
back in.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ROM_BASE = 0x08000000

# Directories whose *.py hold the post-build patch scripts.
PATCH_DIRS = [
    "languages/fr/patches",
    "languages/it/patches",
    "languages/de/patches",
    "src/i18n",
]

# Only offsets >= this are plausible table/data addresses; smaller hex literals
# are strides, field lengths, colour values, glyph indices, etc.
MIN_TABLE_OFFSET = 0x100000

_HEX_RE = re.compile(r"0x([0-9A-Fa-f]{5,8})")

# Offsets that grep as "inverted" (referenced on the patched base, dead on the
# clean base) but have been reviewed and are NOT bugs. Keeping them here lets
# the script exit 0 today while still failing loudly if a NEW hard-coded
# relocation target is introduced. Map: offset -> reviewed justification.
REVIEWED_INVERTED: dict[int, str] = {
    # move_names.py still *names* the patched-base relocation target as a
    # constant, but no longer writes to it blindly: resolve_live_base() follows
    # the ROM's own pointer (clean -> 0xA40A10, patched -> 0x1B2980). T-38.
    0x1B2980: "move_names.py resolves the live base dynamically (T-38)",
    # fr/item_names.py ITEM_DESC_OVERRIDES entry for the FR 'Muscle+' item
    # description. FR-only: build-fr runs against patchedfrenchrom.gba, where
    # item struct 0x876ECC still points here, so it stays live. IT's copy of
    # ITEM_DESC_OVERRIDES is empty; DE has no such override. T-38.
    0xB40FC0: "fr-only override; build-fr uses the patched base where it is live (T-38)",
}


def collect_candidate_offsets(rom_size: int) -> dict[int, set[str]]:
    """Map each hard-coded offset (>= MIN_TABLE_OFFSET, < rom_size) to the set
    of patch files that mention it."""
    cand: dict[int, set[str]] = {}
    for rel in PATCH_DIRS:
        d = REPO_ROOT / rel
        if not d.exists():
            continue
        for f in sorted(d.glob("*.py")):
            label = f.name if rel == "languages/fr/patches" else f"{rel.split('/')[1]}/{f.name}"
            # fr core files: tag with fr/ to disambiguate from same-named ports.
            if rel == "languages/fr/patches":
                label = f"fr/{f.name}"
            elif rel == "src/i18n":
                label = f"i18n/{f.name}"
            for m in _HEX_RE.finditer(f.read_text(errors="replace")):
                v = int(m.group(1), 16)
                if MIN_TABLE_OFFSET <= v < rom_size:
                    cand.setdefault(v, set()).add(label)
    return cand


def is_pointed_to(rom: bytes, offset: int) -> bool:
    """True if a 32-bit LE pointer (0x08000000 + offset) appears anywhere in rom."""
    return rom.find((ROM_BASE + offset).to_bytes(4, "little")) >= 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clean", type=Path, default=REPO_ROOT / "input/roms/englishrom.gba")
    parser.add_argument("--patched", type=Path, default=REPO_ROOT / "input/roms/patchedfrenchrom.gba")
    parser.add_argument("--verbose", action="store_true", help="also list live-on-clean and dead-on-both offsets")
    args = parser.parse_args()

    clean = args.clean.read_bytes()
    patched = args.patched.read_bytes() if args.patched.exists() else None

    cand = collect_candidate_offsets(len(clean))

    broken: list[tuple[int, list[str]]] = []
    reviewed: list[tuple[int, list[str]]] = []
    live_clean: list[int] = []
    dead_both: list[int] = []
    for off, files in sorted(cand.items()):
        lc = is_pointed_to(clean, off)
        lp = is_pointed_to(patched, off) if patched is not None else False
        if not lc and lp:
            if off in REVIEWED_INVERTED:
                reviewed.append((off, sorted(files)))
            else:
                broken.append((off, sorted(files)))
        elif lc:
            live_clean.append(off)
        else:
            dead_both.append(off)

    print(f"Scanned {len(cand)} distinct hard-coded offsets (>= 0x{MIN_TABLE_OFFSET:X}) "
          f"across {len(PATCH_DIRS)} patch dirs.")
    print(f"  live on clean base            : {len(live_clean)}")
    print(f"  dead on both (code/gfx/field) : {len(dead_both)}")
    print(f"  inverted, reviewed & OK       : {len(reviewed)}")
    print(f"  INVERTED (broken on clean)    : {len(broken)}")
    print()

    if reviewed:
        print("Inverted but reviewed as OK (see REVIEWED_INVERTED):")
        for off, files in reviewed:
            print(f"   0x{off:07X}  {', '.join(files)}")
            print(f"            -> {REVIEWED_INVERTED[off]}")
        print()

    if broken:
        print("!! Offsets referenced on the patched base but DEAD on the clean base")
        print("!! (patch writes to free space on the clean base — must be fixed):")
        for off, files in broken:
            print(f"   0x{off:07X}  {', '.join(files)}")
        print()

    if args.verbose:
        print("live-on-clean offsets:", ", ".join(f"0x{o:X}" for o in live_clean))
        print("dead-on-both offsets:", ", ".join(f"0x{o:X}" for o in dead_both))

    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
