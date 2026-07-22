#!/usr/bin/env python3
"""Traduit de façon *déterministe* le pop-up d'étages (#27 / #100).

Le petit pop-up d'étage affiché dans les grottes et les bâtiments (« 1F »,
« 2F », … « 11F », « B1F »… « B4F ») est servi par une table de 15 chaînes aux
offsets EN ``0x41803A``-``0x41806B``, atteinte par **six** tables de pointeurs
dupliquées (39 emplacements — ordres croissant/décroissant + look-ups du rituel).

Convention FR demandée dans l'issue :
``1F → RDC``, puis ``nF → (n-1)E`` et les sous-sols ``B1F..B4F → -1..-4``.

Pourquoi un patch dédié plutôt que le pipeline générique
--------------------------------------------------------
Chaque libellé FR est plus long ou de longueur différente de son original
anglais (``RDC`` > ``1F``, ``10E`` > ``11F``…). Le build générique écrivait donc
les libellés courts *en place* mais **relocalisait** les longs (``RDC``, ``10E``)
dans du free-space partagé, puis repointait les six tables. Cette étape était
non déterministe : plusieurs rebuilds ont fait **retomber le pop-up en anglais**
(``1F``) et un build a **fusionné deux libellés en `RDC1E`** (terminateur ``0xFF``
perdu). C'est exactement ce que l'issue #100 a signalé (« les étages ne sont pas
traduits dans la dernière version ») et pourquoi le rapporteur demande de rendre
le correctif *persistant*.

Ce patch supprime cette fragilité : il écrit les 15 libellés dans une région de
padding **fixe et réservée** en fin de ROM et repointe **tous** les emplacements
vers cette copie. Le pop-up ne dépend donc plus du tout de la relocalisation
générique — la sortie est identique à chaque build. Comme c'est du code commité,
il survit aussi aux réécritures de ``combined_fr.txt`` et du JSON (classe 3).
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.core.text_codec import TextEncoder  # noqa: E402

ROM_BASE = 0x08000000
ROM_LIMIT = 0x0A000000

# EN string offset -> French label (issue #27 / #100).
FR_LABELS = {
    0x41803A: "RDC",
    0x41803D: "1E",
    0x418040: "2E",
    0x418043: "3E",
    0x418046: "4E",
    0x418049: "5E",
    0x41804C: "6E",
    0x41804F: "7E",
    0x418052: "8E",
    0x418055: "9E",
    0x418059: "10E",
    0x41805D: "-1",
    0x418061: "-2",
    0x418065: "-3",
    0x418069: "-4",
}

# Fixed, reserved destination in the ROM's trailing padding. Sits just below the
# other dedicated tail-string patch (``party_cancel_button`` @0x1FFFF80); the
# 0x1FFFF00-0x1FFFF7F run is genuine 0xFF padding the generic free-space
# allocator never reaches (it fills space from the low ROM upward and stops well
# before the tail).
FLOOR_STR_OFFSET = 0x1FFFF00

DEFAULT_SOURCE = Path("input/roms/englishrom.gba")


def _encode(label: str) -> bytes:
    encoded = TextEncoder.encode_pokemon(label)
    if not encoded.endswith(b"\xFF"):
        encoded += b"\xFF"
    return encoded


def _find_slots(source: bytes) -> dict[int, list[int]]:
    """All pointer slots in the base ROM that target the floor string table.

    Grouped by EN string offset. Scanning the untouched base ROM (never the
    already-relocated FR build) is what makes the slot set complete.
    """
    slots: dict[int, list[int]] = {off: [] for off in FR_LABELS}
    for off in FR_LABELS:
        needle = struct.pack("<I", ROM_BASE + off)
        start = 0
        while True:
            i = source.find(needle, start)
            if i == -1:
                break
            if i % 2 == 0:  # pointer tables are word/half-word aligned
                slots[off].append(i)
            start = i + 1
    return slots


def apply(rom: bytearray, source: bytes) -> int:
    """Write the 15 FR floor labels to reserved padding and repoint every slot.

    Returns the number of pointer slots (re)pointed. Raises SystemExit on an
    unexpected ROM layout so a regression fails the build loudly instead of
    silently shipping English floors.
    """
    slots = _find_slots(source)

    missing = [off for off, s in slots.items() if not s]
    if missing:
        raise SystemExit(
            "patch_floor_indicators_fr: no pointer found for floor cell(s) "
            + ", ".join(f"0x{off:X}" for off in missing)
            + " — base ROM layout changed, aborting."
        )
    total_slots = sum(len(s) for s in slots.values())
    if total_slots < 30:
        raise SystemExit(
            f"patch_floor_indicators_fr: only {total_slots} floor pointers found "
            "(expected ~39) — base ROM layout changed, aborting."
        )

    # Deterministic layout: labels laid out in table order from FLOOR_STR_OFFSET.
    dest_addr: dict[int, int] = {}
    block = bytearray()
    cursor = FLOOR_STR_OFFSET
    for en_off in FR_LABELS:  # dict preserves insertion (table) order
        encoded = _encode(FR_LABELS[en_off])
        dest_addr[en_off] = ROM_BASE + cursor
        block += encoded
        cursor += len(encoded)

    # Idempotency: already fully applied?
    already = rom[FLOOR_STR_OFFSET:FLOOR_STR_OFFSET + len(block)] == block and all(
        struct.unpack_from("<I", rom, slot)[0] == dest_addr[en_off]
        for en_off, slist in slots.items()
        for slot in slist
    )
    if already:
        return 0

    # Occupation guard: the reserved run must be free (all 0xFF) or already ours.
    current = bytes(rom[FLOOR_STR_OFFSET:FLOOR_STR_OFFSET + len(block)])
    if current != block and any(byte != 0xFF for byte in current):
        raise SystemExit(
            f"patch_floor_indicators_fr: reserved region 0x{FLOOR_STR_OFFSET:07X} "
            f"is occupied ({current.hex()}) — refusing to overwrite live data."
        )

    # The slots come from scanning the untouched base ROM for pointers that
    # target the floor table, so by construction every one is a floor pointer:
    # repointing it to the correct French label is always right. We therefore
    # repoint *unconditionally* — this is what repairs the two shipped failure
    # modes (English residue "1F", merged "RDC1E") instead of aborting on them.
    rom[FLOOR_STR_OFFSET:FLOOR_STR_OFFSET + len(block)] = block
    patched = 0
    for en_off, slist in slots.items():
        for slot in slist:
            if struct.unpack_from("<I", rom, slot)[0] != dest_addr[en_off]:
                struct.pack_into("<I", rom, slot, dest_addr[en_off])
                patched += 1

    print(
        f"  floor indicators: 15 labels @0x{FLOOR_STR_OFFSET:07X}, "
        f"{patched}/{total_slots} pointer(s) repointed"
    )
    return patched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-fr.gba"))
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()

    if not args.rom.exists():
        raise SystemExit(f"ROM not found: {args.rom}")
    if not args.source.exists():
        raise SystemExit(f"Base ROM not found: {args.source}")

    original = args.rom.read_bytes()
    if original[0xB2] != 0x96:
        raise SystemExit(f"Not a valid GBA ROM: {args.rom}")

    rom = bytearray(original)
    patched = apply(rom, args.source.read_bytes())
    if patched:
        Path(f"{args.rom}.bak").write_bytes(original)
        args.rom.write_bytes(rom)
    print(f"patch_floor_indicators_fr: {patched} pointer(s) redirigé(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
