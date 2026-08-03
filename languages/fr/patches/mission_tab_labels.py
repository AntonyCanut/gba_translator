#!/usr/bin/env python3
"""Patch the Mission menu labels and their grammatical contexts (#46, #114).

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

The stock ``Active`` string also has two consumers. The white filter tab needs
the plural ``Actives``, while the blue status at the end of one mission row
needs the singular ``Active``. The generic translation pass relocates
``Actives`` and repoints both consumers to it. This patch keeps the tab on that
live plural target and repoints only the row-status consumer to the original
in-place singular cell.
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

# The two consumers of stock ``Active`` are grammatically distinct in French.
# The tab keeps the translated plural target; the row status returns to the
# original seven-byte cell (six letters + 0xFF terminator), which fits exactly.
ACTIVE_TAB_PTR_OFFSET = 0x1EBFFC8
ACTIVE_STATUS_PTR_OFFSET = 0x1FB40B8
ACTIVE_INLINE_OFFSET = 0x1F5605C

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


def _pointer_target(rom: bytes, pointer_site: int) -> int | None:
    """Resolve a GBA pointer site to a validated file offset."""
    if not (0 <= pointer_site <= len(rom) - 4):
        return None
    ptr_raw = struct.unpack_from("<I", rom, pointer_site)[0]
    file_off = ptr_raw - GBA_BASE
    return file_off if 0 < file_off < len(rom) else None


def _blank_suffix(rom: bytearray, dry_run: bool) -> bool:
    """Blank the shared ``Missions`` suffix when it has an accepted value."""
    file_off = _pointer_target(rom, SUFFIX_PTR_OFFSET)
    if file_off is None:
        print("  WARN Mission suffix pointer out of range — skip", file=sys.stderr)
        return False

    current = _decode_at(rom, file_off)
    if current == "":
        return False

    if current not in _ACCEPTED:
        print(
            f"  WARN 0x{file_off:06X}: expected a Missions suffix "
            f"({sorted(_ACCEPTED)}) got «{current}» — skip",
            file=sys.stderr,
        )
        return False

    if not dry_run:
        for index in range(len(current)):
            rom[file_off + index] = 0xFF

    print(f"  0x{file_off:06X}  «{current}» → «» (Mission tab suffix removed)")
    return True


def _separate_active_contexts(rom: bytearray, dry_run: bool) -> bool:
    """Keep the tab plural while restoring the per-mission status singular."""
    tab_target = _pointer_target(rom, ACTIVE_TAB_PTR_OFFSET)
    status_target = _pointer_target(rom, ACTIVE_STATUS_PTR_OFFSET)
    if tab_target is None or status_target is None:
        print("  WARN Mission Active pointer out of range — skip", file=sys.stderr)
        return False

    tab_text = _decode_at(rom, tab_target)
    status_text = _decode_at(rom, status_target)
    if tab_text != "Actives":
        print(
            f"  WARN Active tab expected «Actives», got «{tab_text}» — skip",
            file=sys.stderr,
        )
        return False
    if status_text == "Active":
        return False
    if status_text != "Actives":
        print(
            f"  WARN mission status expected «Active» or «Actives», "
            f"got «{status_text}» — skip",
            file=sys.stderr,
        )
        return False

    inline_text = _decode_at(rom, ACTIVE_INLINE_OFFSET)
    if inline_text != "Active":
        print(
            f"  WARN 0x{ACTIVE_INLINE_OFFSET:06X}: expected original «Active», "
            f"got «{inline_text}» — skip",
            file=sys.stderr,
        )
        return False

    if not dry_run:
        struct.pack_into(
            "<I",
            rom,
            ACTIVE_STATUS_PTR_OFFSET,
            GBA_BASE + ACTIVE_INLINE_OFFSET,
        )

    print(
        f"  0x{ACTIVE_STATUS_PTR_OFFSET:06X}  «Actives» → «Active» "
        "(singular mission-row status)"
    )
    return True


def apply_to_rom(rom: bytearray, dry_run: bool = False) -> int:
    """Patch the Mission labels in `rom` in place.

    Returns 1 if at least one change was made, 0 otherwise.
    """
    suffix_changed = _blank_suffix(rom, dry_run)
    active_changed = _separate_active_contexts(rom, dry_run)
    return int(suffix_changed or active_changed)


def apply_patches(rom_path: Path, dry_run: bool = False) -> int:
    original = rom_path.read_bytes()
    rom = bytearray(original)
    changes = apply_to_rom(rom, dry_run=dry_run)
    if not dry_run and changes:
        Path(f"{rom_path}.bak").write_bytes(original)
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
