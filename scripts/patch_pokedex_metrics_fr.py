#!/usr/bin/env python3
"""Convert Pokédex height/weight displays from imperial to metric (FR build).

The English ROM displays Pokémon height as feet/inches ("X'Y\"") and weight
as pounds ("X.Y lbs.").  For the French translation, this post-build step
patches the built ROM to show:

  - height: "X.Ym"  (X = dm÷10 = whole metres, Y = dm%10 = decimal digit;
    no floating-point required — the game already stores height in decimetres)
  - weight: "X.Y kg"  (the CFRU lookup table is an identity: value returned
    equals hg, so X.Y = hg÷10 = kg; only the unit label needs changing)

Labels in the Pokédex info panel are updated in-place:
  - "Ht"   → "Ta"  (Taille)
  - "Wt"   → "Po"  (Poids)
  - "lbs." → "kg"

──────────────────────────────────────────────────────────────────────────
How the height routine (PrintMonHeight at 0x1058C4) is converted
──────────────────────────────────────────────────────────────────────────

The English routine computes feet/inches by scaling the stored decimetre
value into tenth-inches (× 10000 / 254), then dividing by 120 (feet) and
10 (inches), and finally formatting "F'II\"".  Three ROM helper routines are
called along the way:

  0x1E4018  signed divide   → quotient in r0
  0x1E460C  unsigned divide → quotient in r0  (r1 is NOT a clean remainder;
                              on its dividend<divisor fast-path r1 is left
                              equal to the divisor — this is the trap that
                              broke every earlier attempt)
  0x1E4684  unsigned modulo → remainder in r0

For metric we only need:  metres = dm÷10  and  decimal = dm mod 10.
The stored decimetre value stays in r4 for the whole routine, so the
decimal digit is computed directly with `dm − 10·metres` — no helper call,
no reliance on a "remainder register".

Patch map (offsets are file offsets = ROM addr − 0x08000000):

  1. 0x10597C  literal pool 10000 → 1   (dm × 1 = dm; kills the inch scaling)
  2. 0x105926  MOVS r1,#254 → MOVS r1,#10  (first divide now yields dm÷10 = metres,
               stored in r5 by the untouched `adds r5,r0,#0` at 0x10592C)
  3. 0x10592E  38-byte clean block replacing the English feet/inch arithmetic:
                 adds r6,r5,#0   ; r6 = metres
                 movs r0,#10
                 muls r0,r6      ; r0 = 10·metres
                 subs r0,r4,r0   ; r0 = dm − 10·metres = decimal digit (0-9)
                 adds r5,r0,#0   ; r5 = decimal digit
                 (28 bytes of NOP padding)
               After this block r6 = metres and r5 = decimal.  The untouched
               tail at 0x105954 (`adds r0,r6 / movs r1,#10 / bl 0x1E460C /
               adds r2,r0`) then puts tens-of-metres (metres÷10) in r2 for the
               single-digit vs two-digit branch decision — correct for any
               height, not just Gen-3 values.
  4. 0x10599C  feet-mark 0xB4 → period 0xAD  (the "." in "X.Ym")
  5. 0x1059A4  decimal-digit write: strip the helper call, write r5 directly
                 adds r0,r5,#0 / adds r0,#0xA1 / strb r0,[r4] / NOP×3
  6. 0x1059B0  unit write: 'm' (0xE1) instead of the imperial inch digit
                 add r4,sp,#0x10 / movs r0,#0xE1 / strb r0,[r4] / NOP×4
  7. 0x1059C2  inch-mark 0xB2 → blank 0x00  (trailing char after "X.Ym")

The two-digit-metres branch (0x105980, e.g. Wailord 14.5 m) is left as the
English original: it already writes tens = r2 and ones = metres mod 10 from
the 0x1E4684 modulo helper (remainder in r0) — both correct.  Earlier code
"fixed" a non-bug here by reading r1 instead of r0; that is intentionally NOT
reintroduced.

Every patch verifies the bytes it expects (English original) and is
idempotent (already-patched cells are skipped without error).

The full conversion is validated end-to-end by executing the patched Thumb
code under an emulator in tests/test_patch_pokedex_metrics_fr.py.

Usage:
    python3 scripts/patch_pokedex_metrics_fr.py --rom output/roms/GenedRom-fr.gba
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Clean metres/decimal block written over the English feet/inch arithmetic at
# 0x10592E (38 bytes).  See module docstring, patch 3.
_HEIGHT_BLOCK_NEW = (
    bytes.fromhex("2e1c0a207043201a051c")   # adds r6,r5 / movs r0,#10 / muls r0,r6 / subs r0,r4,r0 / adds r5,r0
    + b"\xc0\x46" * 14                        # NOP padding to fill the 38-byte span
)
_HEIGHT_BLOCK_OLD = bytes.fromhex(
    "0a21def0a8fe042800d90a35281c7821def065fe061c3001801bc000281a0a21def05dfe051c"
)
assert len(_HEIGHT_BLOCK_NEW) == len(_HEIGHT_BLOCK_OLD) == 0x105954 - 0x10592E

# (offset, expected_old_bytes, replacement_new_bytes)
PATCHES: list[tuple[int, bytes, bytes]] = [
    # ── Height function at 0x1058C4 ─────────────────────────────────────────
    # 1. Literal pool: multiplier 10000 (0x00002710) → 1 (0x00000001)
    (0x10597C, b"\x10\x27\x00\x00", b"\x01\x00\x00\x00"),

    # 2. First divisor MOVS r1,#254 → MOVS r1,#10  (dm ÷ 10 = whole metres)
    (0x105926, b"\xfe\x21", b"\x0a\x21"),

    # 3. Clean metres/decimal block (replaces the feet/inch arithmetic)
    (0x10592E, _HEIGHT_BLOCK_OLD, _HEIGHT_BLOCK_NEW),

    # 4. Feet-mark character (0xB4) → period (0xAD)
    (0x10599C, b"\xb4\x20", b"\xad\x20"),

    # 5. Decimal-digit write: strip BL+shift, write r5 (decimal) directly (12 bytes)
    #    adds r0,r5,#0 / adds r0,#0xA1 / strb r0,[r4] / NOP×3
    (0x1059A4,
     b"\x28\x1c\x0a\x21\xde\xf0\x30\xfe\xa1\x30\x20\x70",
     b"\x28\x1c\xa1\x30\x20\x70\xc0\x46\xc0\x46\xc0\x46"),

    # 6. 'm' unit write: replace inch-digit BL with direct char write (14 bytes)
    #    add r4,sp,#0x10 / movs r0,#0xE1 ('m') / strb r0,[r4] / NOP×5
    (0x1059B0,
     b"\x04\xac\x28\x1c\x0a\x21\xde\xf0\x65\xfe\xa1\x30\x20\x70",
     b"\x04\xac\xe1\x20\x20\x70\xc0\x46\xc0\x46\xc0\x46\xc0\x46"),

    # 7. Inch-mark character (0xB2) → blank (0x00 = space in CFRU)
    (0x1059C2, b"\xb2\x20", b"\x00\x20"),

    # ── String table at 0x415F98 ─────────────────────────────────────────────
    # 8. "Ht\xFF" → "Ta\xFF"  (Taille)
    (0x415F98, b"\xc2\xe8\xff", b"\xce\xd5\xff"),

    # 9. "Wt\xFF" → "Po\xFF"  (Poids)
    (0x415F9B, b"\xd1\xe8\xff", b"\xca\xe3\xff"),

    # 10. "lbs.\xFF" → "kg\xFF\x00\x00"  (weight stays numeric kg; identity table)
    (0x415FA0, b"\xe0\xd6\xe7\xad\xff", b"\xdf\xdb\xff\x00\x00"),
]


def apply_patches(data: bytearray, patches: list = PATCHES) -> int:
    """Apply *patches* to *data* in-place; return the number applied.

    Raises ``ValueError`` when a patch's expected bytes don't match and the
    slot does not already hold the replacement (i.e. unexpected divergence).
    """
    applied = 0
    for offset, old, new in patches:
        if len(old) != len(new):
            raise ValueError(f"0x{offset:X}: length mismatch ({len(old)} vs {len(new)})")
        current = bytes(data[offset: offset + len(old)])
        if current == new:
            continue  # already patched — idempotent
        if current != old:
            raise ValueError(
                f"0x{offset:X}: unexpected bytes {current.hex(' ')} "
                f"(expected {old.hex(' ')})"
            )
        data[offset: offset + len(new)] = new
        applied += 1
    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-fr.gba"))
    args = parser.parse_args()

    data = bytearray(args.rom.read_bytes())
    applied = apply_patches(data)
    if applied:
        args.rom.write_bytes(data)
    print(f"Pokédex metrics patches applied: {applied} (of {len(PATCHES)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
