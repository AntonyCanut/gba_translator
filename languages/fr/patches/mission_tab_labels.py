#!/usr/bin/env python3
"""Blank the redundant " Missions" suffix on the Mission menu filter tabs (issue #114).

The Mission HQ menu builds each filter-tab header at runtime by copying the
selected category name and appending a shared " Missions" label, e.g.
``"Toutes" + "Missions" → "ToutesMissions"``. The category names themselves are
already translated (Toutes / Actives / Inactives / Terminées, relocated and
repointed by the pipeline), but the appended suffix made every tab read as a
run-on compound ("ToutesMissions", "ActivesMissions", …).

Issue #114 asks for the tabs to show only the category word:

  ToutesMissions    → Toutes
  InactivesMissions → Inactives
  ActivesMissions   → Actives
  TerminéesMissions → Terminées

The suffix is a single, separately-pointed string. Its pointer lives at a fixed
data location in the mission-menu UI pointer array; following it lands on the
shared label (" Missions" in the stock EN ROM, "Missions" after the FR build
dropped the leading space). Blanking that string — writing a lone 0xFF
terminator — makes the runtime append nothing, so each tab renders just its
category name.

Why a class-3 *post-build* patch and not a ``combined_fr.txt`` entry: the goal
is an *empty* string, and the translation pipeline silently ignores empty
overrides for offsets already present in the CSV (see ``apply_combined_fr.py``,
``if text:`` guard). Patching the byte in place here — committed code wired into
``make build-fr`` — is the only mechanism that reliably removes the suffix, and
it is immune to ``combined_fr.txt`` rewrites.

Idempotent and self-healing: it follows the *live* pointer (robust to
relocation), only acts when the target still contains a "Missions" label, and is
a no-op once the string is already blank.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.core.text_codec import POKEMON_TABLE

REV = {v: k for k, v in POKEMON_TABLE.items()}
GBA_BASE = 0x08000000

# Pointer to the shared " Missions" suffix label inside the Mission-menu UI
# pointer array. Adjacent entries: 0x1EBE978 → category "All", 0x1EBE990 → sort
# header " A-Z". This one is appended to the selected category to form the tab
# header. Fixed base-ROM data location; the build never moves the pointer word
# itself (only its target may relocate, which is why we resolve it live).
SUFFIX_PTR_OFFSET = 0x1EBE988

# Strings we are willing to blank (EN original + FR build variant). Matching
# guards against silently clobbering an unrelated string if the layout changes.
_ACCEPTED = {"Missions", " Missions"}

MAX_LEN = 12


def _decode_at(rom: bytes, off: int, maxlen: int = MAX_LEN) -> str:
    chars = []
    for i in range(maxlen):
        b = rom[off + i]
        if b == 0xFF:
            break
        chars.append(REV.get(b, f"[{b:02X}]"))
    return "".join(chars)


def apply_to_rom(rom: bytearray, dry_run: bool = False) -> int:
    """Blank the Mission-tab " Missions" suffix in `rom` in place.

    Returns 1 if a change was made, 0 otherwise.
    """
    ptr_raw = struct.unpack_from("<I", rom, SUFFIX_PTR_OFFSET)[0]
    file_off = ptr_raw - GBA_BASE
    if not (0 < file_off < len(rom)):
        print(
            f"  WARN suffix pointer 0x{ptr_raw:08X} out of range — skip",
            file=sys.stderr,
        )
        return 0

    current = _decode_at(rom, file_off)
    if current == "":
        return 0  # already blank — idempotent no-op

    if current not in _ACCEPTED:
        print(
            f"  WARN 0x{file_off:06X}: expected a Missions suffix "
            f"({sorted(_ACCEPTED)}) got «{current}» — skip",
            file=sys.stderr,
        )
        return 0

    if not dry_run:
        # Overwrite the whole label (including any leading space) with 0xFF so
        # the runtime append contributes nothing and no stale bytes remain
        # reachable through the terminator.
        for j in range(len(current)):
            rom[file_off + j] = 0xFF

    print(f"  0x{file_off:06X}  «{current}» → «» (Mission tab suffix removed)")
    return 1


def apply_patches(rom_path: Path, dry_run: bool = False) -> int:
    rom = bytearray(rom_path.read_bytes())
    changes = apply_to_rom(rom, dry_run=dry_run)
    if not dry_run and changes:
        rom_path.write_bytes(rom)
    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    n = apply_patches(args.rom, dry_run=args.dry_run)
    suffix = " (dry-run)" if args.dry_run else ""
    print(f"patch_mission_tab_labels_fr: {n} patch(es) applied{suffix}")


if __name__ == "__main__":
    main()
