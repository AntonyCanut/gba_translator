#!/usr/bin/env python3
"""Restore the in-battle defeat-speech / switch-out battle-string templates (DE).

Same fix as ``patch_battle_string_templates_fr.py`` (tickets B-78 / B-81),
ported to German. ``gBattleStringsTable[0]`` (STRINGID 0, the in-battle
trainer-defeat-speech slot) has its body at the FIXED ROM offset 0x3FB219;
the table pointer at 0x3FDF3C is 0x083FB219 and is NEVER repointed (identical
across every language build).

The cluster 0x3FB219..0x3FB264 packs several language-neutral control-code
templates ({FD24}/{FD2E}/{FD25}/{FD2F}) together with the three trainer
"come back!" switch-out string bodies. The generic (DE/IT) translation
pipeline injects verbose translations in place over this tightly-packed
cluster and can overflow it, shifting every entry so STRINGID 0 no longer
reads ``{FD24}`` (the pure "print the defeat quote the engine already
loaded" template) — producing garbled trainer-name/class text instead of the
defeat quote, exactly as documented for French.

Fix (class-3, post-build, idempotent): these bodies are control-code
templates, not real language text, so the only consistent byte layout that
keeps every fixed pointer landing on the right string is the English one. We
restore the EN bytes for the whole cluster in place. The trainer Pokémon
switch-out lines revert to English here; translating them properly is
handled by the separate ``battle_recall_strings`` patch, which relocates them
via the external pointer table instead of touching this packed cluster.

Idempotent and self-healing: it only writes when the cluster differs from
EN, and refuses to run if the EN reference cluster is not the expected
``{FD24}``-led template (guards against an unexpected source ROM).
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

GBA_BASE = 0x08000000

# gBattleStringsTable[0] entry (4-byte pointer) and the body it must point at.
STRINGID0_PTR_OFF = 0x3FDF3C
STRINGID0_BODY_OFF = 0x3FB219

# The control-code / switch-out cluster restored from EN, inclusive of the
# trailing {FD2F} template. End is the start of the next entry (Exp-points).
CLUSTER_START = 0x3FB219
CLUSTER_END = 0x3FB265  # exclusive

# What STRINGID 0's body must be after the fix (the lose-text template).
EXPECTED_TEMPLATE = bytes.fromhex("fd24ff")  # {FD24} + terminator


def apply_to_rom(rom: bytearray, en: bytes, dry_run: bool = False) -> int:
    """Restore the EN battle-string cluster into `rom`. Returns change count."""
    # Sanity: the table entry must point at the known body offset (EN & target).
    for name, blob in (("target", rom), ("english", en)):
        ptr = struct.unpack_from("<I", blob, STRINGID0_PTR_OFF)[0]
        if ptr != GBA_BASE + STRINGID0_BODY_OFF:
            print(
                f"  WARN STRINGID0 pointer in {name} is 0x{ptr:08X}, expected "
                f"0x{GBA_BASE + STRINGID0_BODY_OFF:08X} — skip",
                file=sys.stderr,
            )
            return 0

    en_cluster = en[CLUSTER_START:CLUSTER_END]
    # Guard: the EN reference must be the canonical {FD24}-led template, else we
    # are looking at an unexpected source ROM and must not blindly copy.
    if en_cluster[:3] != EXPECTED_TEMPLATE:
        print(
            f"  WARN english cluster does not start with {EXPECTED_TEMPLATE.hex()} "
            f"(got {en_cluster[:3].hex()}) — skip",
            file=sys.stderr,
        )
        return 0

    cur = rom[CLUSTER_START:CLUSTER_END]
    if cur == en_cluster:
        return 0  # already correct (idempotent)

    if not dry_run:
        rom[CLUSTER_START:CLUSTER_END] = en_cluster

    print(
        f"  0x{CLUSTER_START:06X}..0x{CLUSTER_END - 1:06X}  STRINGID0 "
        f"{cur[:6].hex()} → {en_cluster[:3].hex()} ({{FD24}} defeat-speech template restored)"
    )
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path, help="pristine EN ROM")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rom = bytearray(args.rom.read_bytes())
    en = args.source.read_bytes()
    n = apply_to_rom(rom, en, dry_run=args.dry_run)
    if not args.dry_run and n:
        args.rom.write_bytes(rom)
    suffix = " (dry-run)" if args.dry_run else ""
    print(f"patch_battle_string_templates_de: {n} patch(es) applied{suffix}")


if __name__ == "__main__":
    main()
