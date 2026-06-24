#!/usr/bin/env python3
"""Repair the legendary-ritual event script clobbered by the repointer pass.

ROOT CAUSE
----------
``scripts/repoint_stale_text_pointers.py`` rewrites "stale" text pointers by
scanning the ROM for every 4-byte window equal to a relocated string's old
GBA address and replacing it with the new (French) address. Its only veto is
for windows that overlap *translated text* — it does **not** protect event
*script bytecode*.

In the Ho-Oh / Lugia summoning cutscene (map "Ruines du Néant B2F", the
"Prison Bottle / Bouteille Prison" ritual) the script contains a run of
``setflag`` instructions:

    ... 29 E2 08   setflag 0x08E2
        29 F6 09   setflag 0x09F6
        29 F0 02   setflag 0x02F0 ...

The little-endian 4-byte window that starts at the high byte of ``setflag
0x08E2`` reads ``08 29 F6 09`` == ``0x09F62908`` — which is, by pure
coincidence, the English address of the unrelated string "I swam, of
course!". The repointer false-matched it and overwrote those script bytes
with the relocated French address of that string (``0x08C277E1`` →
``E1 77 C2 08``), turning ``setflag 0x08E2 / setflag 0x09F6`` into
``setflag 0xE1E2 / <0x77 0xC2 0x08>``.

EFFECT IN GAME
--------------
The corruption sits on the path the cutscene takes right before it issues
``setwildbattle`` + ``special 0x138`` (the legendary-battle launcher). With
the ``setflag`` chain mangled the script never reaches the battle: after
"Hoopa! Summon a Pokémon to crush this fool!" / "Hoo hoo hoo!" the Ho-Oh
simply stands in the overworld and **the battle never starts** — and because
the ritual never advances, Lugia never appears either. On the English ROM the
same save launches the battle normally, proving it is a build artifact and
not a translation choice. The identical corruption occurs at **13 sites**
across the legendary cutscene scripts — Groudon's Red-Orb summon (0x1E59D1F),
the Ho-Oh branch (0x1E8C677), the Lugia branch (0x1E8C782) and ~10 siblings.

THE FIX
-------
Restore the four canonical script bytes at each site from the English source
ROM. Sites are *discovered* by signature (CANON window preceded by a `setflag`
opcode), not enumerated — an earlier allow-list of just Ho-Oh/Lugia left the
Groudon summon (and 8 other sites) clobbered after every rebuild. This leaves
every legitimately-relocated French *string* pointer intact (the two genuine
relocated pointers 0x1E8738D / 0x1E873B4 share the bytes but lack the leading
`setflag` opcode, so discovery excludes them) and only undoes the false-positive
writes into script bytecode. Verified in-engine with mGBA: the legendary battle
auto-launches after the cutscene exactly as on the English ROM, with the French
dialogue preserved.

Usage:
    python3 scripts/patch_legendary_ritual_fr.py \
        --rom output/roms/GenedRom-fr.gba \
        --source input/roms/englishrom.gba
"""

from __future__ import annotations

import argparse
from pathlib import Path

GBA_BASE = 0x08000000

# The canonical 4-byte window at every clobbered site: the tail of
# `setflag 0x08E2` plus `setflag 0x09F6`. In little-endian it equals
# 0x09F62908 — the English address of "I swam, of course!" — which is exactly
# why the repointer false-matched script bytecode here.
CANON = bytes((0x08, 0x29, 0xF6, 0x09))
SETFLAG_OPCODE = 0x29

# The relocated French string the repointer wrongly pointed these windows at.
# Used only as a sanity signature so the patch is a strict no-op once correct.
CORRUPT_POINTER = 0x08C277E1

# Named branches kept for documentation/logging. Discovery (below) finds these
# AND the ~10 other cutscene scripts sharing the identical setflag-chain
# signature — an allow-list of just Ho-Oh/Lugia previously left Groudon (and 8
# others) clobbered after every rebuild, so the summon looped forever.
NAMED_SITES: dict[int, str] = {
    0x1E59D1F: "Groudon (Red Orb summon)",
    0x1E8C677: "Ho-Oh branch",
    0x1E8C782: "Lugia branch",
}


def discover_clobbered_sites(source: bytes) -> list[int]:
    """Every event-script `setflag` chain whose 4-byte window equals CANON.

    A genuine *relocated text pointer* also holds CANON in the English source
    (it really is a pointer to "I swam, of course!"), so the window alone is
    ambiguous. The discriminator is the preceding byte: a real setflag chain
    has the previous `setflag` opcode (0x29) two bytes before the window; a
    genuine pointer does not. This includes Groudon/Ho-Oh/Lugia + ~10 sibling
    cutscene scripts and excludes the two legitimate relocated pointers
    (0x1E8738D, 0x1E873B4) that must stay French.
    """
    sites: list[int] = []
    start = 0
    while True:
        off = source.find(CANON, start)
        if off == -1:
            break
        start = off + 1
        if off >= 2 and source[off - 2] == SETFLAG_OPCODE:
            sites.append(off)
    return sites


def patch(rom: bytearray, source: bytes) -> int:
    fixed = 0
    rom_end = GBA_BASE + len(rom)
    for offset in discover_clobbered_sites(source):
        label = NAMED_SITES.get(offset, "cutscene setflag chain")
        canonical = source[offset:offset + 4]
        current = bytes(rom[offset:offset + 4])
        if current == canonical:
            print(f"  {offset:#08x} ({label}): already canonical {canonical.hex()}")
            continue
        current_ptr = int.from_bytes(current, "little")
        # A discovered site is a `setflag` chain in the English source, so its
        # only legitimate FR value is the canonical one. Any difference is a
        # repointer/LZ77 false-match that overwrote the window with a relocated
        # string's GBA address — and that address varies with the free-space
        # layout (0x08C277E1 in older builds, anything in 0x08xxxxxx now). So
        # restore canonical whenever the window holds a GBA ROM pointer; only
        # refuse for content that is neither canonical nor a plausible pointer.
        if not (GBA_BASE <= current_ptr < rom_end):
            raise SystemExit(
                f"Refusing to patch {offset:#08x} ({label}): expected the "
                f"canonical bytes {canonical.hex()} or a clobbered GBA pointer, "
                f"found {current.hex()}"
            )
        rom[offset:offset + 4] = canonical
        print(
            f"  {offset:#08x} ({label}): restored {current.hex()} -> "
            f"{canonical.hex()} (script un-clobbered)"
        )
        fixed += 1
    return fixed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", type=Path, required=True, help="FR ROM to patch")
    ap.add_argument(
        "--source",
        type=Path,
        default=Path("input/roms/englishrom.gba"),
        help="English source ROM (canonical script bytes)",
    )
    args = ap.parse_args()

    for path in (args.rom, args.source):
        if not path.exists():
            raise SystemExit(f"Missing file: {path}")

    rom = bytearray(args.rom.read_bytes())
    source = args.source.read_bytes()
    print("Repairing legendary-ritual script (Ho-Oh/Lugia summon)...")
    fixed = patch(rom, source)
    if fixed:
        args.rom.write_bytes(rom)
    print(f"Legendary-ritual script sites repaired: {fixed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
