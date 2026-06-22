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
not a translation choice. The same false match recurs **everywhere** the byte
run ``08 29 F6 09`` appears as the tail of a ``setflag X / setflag 0x09F6``
pair — at least a dozen event-script sites, including:
  * Ho-Oh branch   0x1E8C677
  * Lugia branch   0x1E8C782
  * Groudon/Red-Orb summon  0x1E59D1F (looping "Groudon ! Réponds à mon Orbe
    Rouge !" — the script never reaches its own ``setwildbattle`` +
    ``special 0x138`` launcher)
  * plus ~10 further setflag-chain windows across other cutscene scripts.
The two windows at 0x1E8738D / 0x1E873B4 hold the *same* bytes but are genuine
relocated text pointers (preceded by pointer bytes, not a ``setflag`` opcode),
so they are correctly French and must NOT be reverted.

THE FIX
-------
Auto-discover every clobbered site and restore the four canonical script bytes
from the English source ROM. A site is a script clobber (not a legit pointer)
iff the FR ROM holds the corrupt pointer 0x08C277E1, the English ROM holds the
canonical ``08 29 F6 09`` window, AND that window is the operand tail of a
``setflag`` chain (the byte two before it is the 0x29 ``setflag`` opcode). This
leaves every legitimately-relocated French *string* pointer intact and only
undoes the false-positive writes into script bytecode. Verified in-engine with
mGBA on the Ho-Oh branch: the battle auto-launches after the cutscene exactly
as on the English ROM, with the French dialogue (incl. "Hoo hoo hoo !")
preserved; the other sites are byte-identical-to-English restorations of the
same proven signature.

Usage:
    python3 scripts/patch_legendary_ritual_fr.py \
        --rom output/roms/GenedRom-fr.gba \
        --source input/roms/englishrom.gba
"""

from __future__ import annotations

import argparse
from pathlib import Path

GBA_BASE = 0x08000000

# Named script clobber sites kept for documentation / sanity. These are the
# legendary-ritual cutscenes the bug was reported against; the patch also
# auto-discovers every other site with the same signature. Ho-Oh/Lugia live in
# the Ruines du Néant ritual (0x1E8B000-0x1E8D400); the Groudon/Red-Orb summon
# lives in its own ritual script around 0x1E59xxx.
RITUAL_SCRIPT_FIXES: tuple[tuple[int, str], ...] = (
    (0x1E8C677, "Ho-Oh branch"),
    (0x1E8C782, "Lugia branch"),
    (0x1E59D1F, "Groudon branch"),
)

# The relocated French string the repointer wrongly pointed these windows at.
# Used as a strict signature so the patch is a no-op once correct, and never
# touches a site holding anything else.
CORRUPT_POINTER = 0x08C277E1

# Canonical script bytes: little-endian 0x09F62908 == `<...>08` + `setflag
# 0x09F6` (29 F6 09). The repointer false-matched this run as the English
# address of the string "I swam, of course!" and overwrote it.
CANONICAL_WINDOW = bytes([0x08, 0x29, 0xF6, 0x09])

# CFRU `setflag` opcode. A canonical window that is the operand tail of a
# `setflag` chain is script bytecode (its byte two-before is this opcode), not a
# genuine relocated text pointer — that is what distinguishes a clobber from a
# legitimate relocation that happens to share the same bytes.
SETFLAG_OPCODE = 0x29


def discover_clobbered_sites(rom: bytes, source: bytes) -> list[int]:
    """Find every offset where the FR ROM holds the corrupt pointer, the English
    source holds the canonical `setflag`-chain window, and that window sits in a
    `setflag` chain (byte two-before == 0x29). Those are false-positive script
    clobbers; sites that merely share the bytes as a real relocated pointer
    (different preceding byte) are excluded."""
    needle = CORRUPT_POINTER.to_bytes(4, "little")
    sites: list[int] = []
    start = 0
    while True:
        i = rom.find(needle, start)
        if i == -1:
            break
        start = i + 1
        if i < 2 or i + 4 > len(source):
            continue
        if source[i:i + 4] == CANONICAL_WINDOW and source[i - 2] == SETFLAG_OPCODE:
            sites.append(i)
    return sites


def patch(rom: bytearray, source: bytes) -> int:
    fixed = 0
    labels = {off: name for off, name in RITUAL_SCRIPT_FIXES}
    targets = set(labels) | set(discover_clobbered_sites(rom, source))
    for offset in sorted(targets):
        label = labels.get(offset, "discovered setflag-chain site")
        canonical = source[offset:offset + 4]
        current = bytes(rom[offset:offset + 4])
        if current == canonical:
            print(f"  {offset:#08x} ({label}): already canonical {canonical.hex()}")
            continue
        current_ptr = int.from_bytes(current, "little")
        if current_ptr != CORRUPT_POINTER:
            # Unexpected content: refuse to guess. Better to fail loudly than
            # to silently overwrite a legitimately-different build.
            raise SystemExit(
                f"Refusing to patch {offset:#08x} ({label}): expected the "
                f"corrupt pointer {CORRUPT_POINTER:#010x} or the canonical "
                f"bytes {canonical.hex()}, found {current.hex()}"
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
