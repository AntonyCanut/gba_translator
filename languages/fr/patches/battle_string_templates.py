#!/usr/bin/env python3
"""Restore the in-battle defeat-speech / switch-out battle-string templates.

Symptom (ticket B-78 "Combats & Dialogues")
-------------------------------------------
When the player wins a trainer battle the FR ROM flashed a nonsensical
**"Mike Campeur"** (the trainer name + an unrelated class name) where the
trainer's defeat quote should appear — e.g. EN "I ran out of energy to fight!".
It also had no wait code, so it flashed by ("il manque le attente bouton").

Root cause
----------
`gBattleStringsTable[0]` (STRINGID 0, the in-battle trainer-defeat-speech slot)
has its body at the FIXED ROM offset 0x3FB219; the table pointer at 0x3FDF3C is
0x083FB219 and is NEVER repointed (identical EN/FR). Its EN body is the pure
control-code template ``{FD24}`` (= B_TXT_TRAINER1_LOSE_TEXT — print the defeat
quote the engine already loaded into the lose-text buffer).

The FR build pipeline mis-encodes that buffer token: `09_csv_to_json_v2.py`
emits ``{FD24}`` → ``<0xFD><0x1D>`` (FD1D = trainer NAME) and ``{FD25}`` → FD1D
too, while leaving ``{FD2E}``/``{FD2F}`` as un-encoded literal tokens. Injected
in place over a tightly-packed cluster of short control-code templates and the
"come back!" switch-out strings (0x3FB219..0x3FB264), this overflows and shifts
every entry, so STRINGID 0 ends up reading ``{FD1D} {FD2E}`` → name + class →
"Mike Campeur". Spanish leaves the whole cluster byte-intact (its "regresa."
fits), proving this is an FR-pipeline in-place overflow, not source data.

Fix (class-3, post-build, idempotent)
-------------------------------------
These bodies are *language-neutral* control-code templates ({FD24}/{FD2E}/
{FD25}/{FD2F}) interleaved with switch-out strings; the only consistent byte
layout that keeps every fixed pointer landing on the right string is the
English one. We restore the EN bytes for the whole cluster
0x3FB219..0x3FB264 in place — exactly the family of fixed-offset, never-
repointed slots that `patch_fixed_table_names.py` / `patch_status_abbrevs_fr.py`
own. STRINGID 0 becomes ``{FD24}`` again, so the engine prints the FR defeat
quote it loaded (verified in mGBA: "Plus d'énergie pour me battre !<FC09>",
which now also waits for a button).

The trainer Pokémon switch-out lines ("{name}: {mon}, come back!") revert to
English here; their FR translation was already incomplete/corrupt in this
cluster. Translating them properly requires relocate+repoint and is tracked as
a follow-up.

Idempotent and self-healing: it only writes when the cluster differs from EN,
and refuses to run if the EN reference cluster is not the expected
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
    print(f"patch_battle_string_templates_fr: {n} patch(es) applied{suffix}")


if __name__ == "__main__":
    main()
