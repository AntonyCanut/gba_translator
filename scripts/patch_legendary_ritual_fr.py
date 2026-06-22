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
not a translation choice. The identical corruption exists three times: on the
Ho-Oh branch (0x1E8C677), the Lugia branch (0x1E8C782), and — same false match,
same corrupt pointer 0x08C277E1 — in the Groudon/Red-Orb summoning script at
0x1E59D1F, right before its own ``setwildbattle`` + ``special 0x138`` launcher.
On the Groudon site the looping dialogue "Groudon ! Réponds à mon Orbe Rouge !"
never advances because the mangled ``setflag`` chain stops the script before the
battle launches.

THE FIX
-------
Restore the four canonical script bytes at each site from the English source
ROM. This leaves every legitimately-relocated French *string* pointer intact
(those are real pointers and are correctly French) and only undoes the two
false-positive writes into script bytecode. Verified in-engine with mGBA: the
Ho-Oh battle auto-launches after the cutscene exactly as on the English ROM,
with the French dialogue (incl. the "Hoo hoo hoo !" cry) preserved.

Usage:
    python3 scripts/patch_legendary_ritual_fr.py \
        --rom output/roms/GenedRom-fr.gba \
        --source input/roms/englishrom.gba
"""

from __future__ import annotations

import argparse
from pathlib import Path

GBA_BASE = 0x08000000

# File offsets of the three clobbered script windows. Each sits inside a
# legendary-ritual event script and, in English, holds the canonical bytes
# 08 29 F6 09 (the tail of `setflag 0x08E2` plus `setflag 0x09F6`). The
# corruption rewrites them to a French-text pointer
# (0x08C277E1 -> "J'ai nagé, bien sûr !"), which is the signature we expect.
# Ho-Oh/Lugia live in the Ruines du Néant ritual (0x1E8B000-0x1E8D400); the
# Groudon/Red-Orb summon lives in its own ritual script around 0x1E59xxx.
RITUAL_SCRIPT_FIXES: tuple[tuple[int, str], ...] = (
    (0x1E8C677, "Ho-Oh branch"),
    (0x1E8C782, "Lugia branch"),
    (0x1E59D1F, "Groudon branch"),
)

# The relocated French string the repointer wrongly pointed these windows at.
# Used only as a sanity signature so the patch is a strict no-op once correct.
CORRUPT_POINTER = 0x08C277E1


def patch(rom: bytearray, source: bytes) -> int:
    fixed = 0
    for offset, label in RITUAL_SCRIPT_FIXES:
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
