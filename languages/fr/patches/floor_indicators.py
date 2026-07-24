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

Étages rattachés à un lieu (relance #100)
-----------------------------------------
La table ``0x41803A`` n'est **pas** la seule source d'étages affichée au joueur.
D'autres libellés vivent dans leurs propres cellules, toujours accolés à un lieu,
et étaient restés en anglais :

* menus d'ascenseur (``multichoice`` FireRed et scripts de carte) :
  ``0x417AB0`` (``1F``-``5F``), ``0x7D8F91`` (``F1``/``B1F``-``B3F``),
  ``0x7ECDAD`` (``F5``-``F1``), ``0x1F6F5FB`` (``1F``/``B1F``-``B3F``) ;
* liste des émeraudes du Cube (``0x1E5BB44``) : chaque entrée affiche l'étage
  ``0x1EF1906``/``0x1EF190A``/``0x1EF190D`` à côté de la description du lieu.

Ces cellules sont trop courtes pour accueillir ``RDC`` et n'ont qu'un unique
référent chacune : plutôt que de les relocaliser une deuxième fois, on **réutilise
les libellés FR déjà écrits dans la région réservée** et on repointe les
emplacements listés dans ``EXTRA_SLOTS`` (adresses figées, vérifiées contre la
ROM de base — le build échoue bruyamment si la disposition change).

Le pop-up « nom de lieu + étage » : aucune chaîne, du **code** (relance #100)
------------------------------------------------------------------------------
Dernière source, et la seule que le rapporteur voyait encore : la bannière de
lieu affichée en entrant dans une carte (« Grotte de la Vallée 2F »). Le suffixe
d'étage n'y vient d'**aucune** chaîne de la ROM — il est **fabriqué par le code**.

``AppendFloorNumberString`` (``0x09847C``, unique appelant : la bannière en
``0x098424``) lit ``gMapHeader.floorNum`` (``s8`` en ``0x02036DFC+0x1A``) et
compose le suffixe caractère par caractère :

.. code-block:: text

    si floorNum == 0     -> rien
    si floorNum == 0x7F  -> " " + StringAppend("ROOFTOP" @0x41D18D, traduit "TOIT")
    sinon                -> " " + ('B' si négatif) + décimales(|floorNum|) + 'F'

C'est pour cela que les trois tours précédents ne pouvaient pas le corriger :
balayer la ROM à la recherche d'un libellé anglais atteignable ne trouve rien,
les octets ``'B'`` (``0xBC``) et ``'F'`` (``0xC0``) sont des immédiats Thumb.

On réécrit donc la routine **sur place** (92 octets disponibles jusqu'à la
fonction suivante en ``0x0984D8``) pour appliquer la convention de l'issue :

.. code-block:: text

    floorNum == 1  -> " RDC"                       (StringAppend, libellé réservé)
    floorNum >= 2  -> " " + décimales(floorNum-1) + 'E'      (2F -> 1E, 11F -> 10E)
    floorNum < 0   -> " -" + décimales(|floorNum|)           (B1F -> -1)
    floorNum 0x7F  -> inchangé (« TOIT »)

La routine réutilise le ``RDC`` déjà écrit en région réservée, donc le patch
reste auto-suffisant : ni ``combined_fr.txt`` ni le JSON ne peuvent le perdre.
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

# Floor labels shown next to a place but served by their own cells (see the
# module docstring). Pointer slot -> (EN cell it points at in the base ROM,
# French label to reuse from the reserved region).
#
# The slots are pinned instead of scanned: a byte-pattern scan also matches
# coincidental 4-byte runs inside sample/graphics data (e.g. 0xB21C48 happens to
# read as a pointer to the "B2F" cell), and repointing one of those would corrupt
# unrelated data.
EXTRA_SLOTS: dict[int, tuple[int, str]] = {
    # Multichoice "elevator" list (5 floors, descending) @0x3DFFE8-0x3E0008.
    0x3DFFE8: (0x417ABC, "4E"),   # 5F
    0x3DFFF0: (0x417AB9, "3E"),   # 4F
    0x3DFFF8: (0x417AB6, "2E"),   # 3F
    0x3E0000: (0x417AB3, "1E"),   # 2F
    0x3E0008: (0x417AB0, "RDC"),  # 1F
    # Map-script elevator (F1/B1F..B3F) @0x7D8E18-0x7D8E42.
    0x7D8E18: (0x7D8F91, "RDC"),  # F1
    0x7D8E26: (0x7D8F94, "-1"),   # B1F
    0x7D8E34: (0x7D8F98, "-2"),   # B2F
    0x7D8E42: (0x7D8F9C, "-3"),   # B3F
    # Map-script elevator (F5..F1) @0x16C180-0x16C1B8.
    0x16C180: (0x7ECDAD, "4E"),   # F5
    0x16C18E: (0x7ECDB0, "3E"),   # F4
    0x16C19C: (0x7ECDB3, "2E"),   # F3
    0x16C1AA: (0x7ECDB6, "1E"),   # F2
    0x16C1B8: (0x7ECDB9, "RDC"),  # F1
    # Cube emerald list @0x1E5BB44: one floor label per location description.
    0x1E5BB54: (0x1EF1906, "-1"),   # B1F
    0x1E5BB64: (0x1EF1906, "-1"),   # B1F
    0x1E5BB74: (0x1EF190A, "RDC"),  # 1F
    0x1E5BB84: (0x1EF190A, "RDC"),  # 1F
    0x1E5BB94: (0x1EF190A, "RDC"),  # 1F
    0x1E5BBA4: (0x1EF190A, "RDC"),  # 1F
    0x1E5BBB4: (0x1EF190A, "RDC"),  # 1F
    0x1E5BBC4: (0x1EF190A, "RDC"),  # 1F
    0x1E5BBD4: (0x1EF190D, "1E"),   # 2F
    0x1E5BBE4: (0x1EF190D, "1E"),   # 2F
    # Map-script elevator (1F/B1F..B3F) @0x1E912BA-0x1E912E4.
    0x1E912BA: (0x1F6F5FB, "RDC"),  # 1F
    0x1E912C8: (0x1F6F5FE, "-1"),   # B1F
    0x1E912D6: (0x1F6F602, "-2"),   # B2F
    0x1E912E4: (0x1F6F606, "-3"),   # B3F
}

DEFAULT_SOURCE = Path("input/roms/englishrom.gba")

# --- Bannière de lieu : la routine Thumb qui fabrique le suffixe d'étage ------
#
# ``AppendFloorNumberString(u8 *dest, s8 floorNum)``. On la réécrit entièrement :
# la zone va jusqu'à la fonction suivante (``0x0984D8``), soit 92 octets.
POPUP_FLOOR_FUNC = 0x09847C
POPUP_FLOOR_FUNC_END = 0x0984D8
POPUP_FLOOR_FUNC_SIZE = POPUP_FLOOR_FUNC_END - POPUP_FLOOR_FUNC

# Routines FireRed appelées par la nouvelle version (adresses GBA, mode Thumb).
STRING_APPEND = 0x08008D84
CONVERT_INT_TO_DECIMAL_STRING_N = 0x08008E78

# « ROOFTOP », déjà traduit « TOIT » sur place par le pipeline : on garde le
# pointeur d'origine, seul le libellé change.
ROOFTOP_STRING = 0x0841D18D

# Empreinte de la routine anglaise. Le build s'arrête si elle ne correspond pas :
# une routine déplacée signifierait qu'on écrase du code vivant.
ORIGINAL_POPUP_FLOOR_CODE = bytes.fromhex(
    "00b5021c09060b0e0916002923d00020107001327f2907d10249101c70f774fc"
    "19e000008dd14108002905dabc201070013248420006030e19060916101c0022"
    "022370f7dbfc021c111cc02010700132ff204870101c02bc08470000"
)

# Caractères CFRU utilisés comme immédiats par la routine.
CHAR_SPACE = 0x00
CHAR_MINUS = 0xAE
CHAR_E = 0xBF


def _encode(label: str) -> bytes:
    encoded = TextEncoder.encode_pokemon(label)
    if not encoded.endswith(b"\xFF"):
        encoded += b"\xFF"
    return encoded


def _bl(here: int, target: int) -> tuple[int, int]:
    """Encode a Thumb ``BL`` placed at ROM offset *here* and jumping to *target*."""
    delta = target - (ROM_BASE + here + 4)
    if not -(1 << 22) <= delta < (1 << 22):
        raise SystemExit(f"patch_floor_indicators_fr: BL out of range ({delta:#x})")
    return 0xF000 | ((delta >> 12) & 0x7FF), 0xF800 | ((delta >> 1) & 0x7FF)


def _branch(here: int, target: int, cond: int | None = None) -> int:
    """Encode a Thumb branch at offset *here*; *cond* ``None`` means unconditional."""
    delta = (target - (here + 4)) // 2
    if cond is None:
        return 0xE000 | (delta & 0x7FF)
    return 0xD000 | (cond << 8) | (delta & 0xFF)


def _ldr_pc(here: int, pool: int, reg: int) -> int:
    """Encode ``ldr rN, [pc, #imm]`` at offset *here* reading the word at *pool*."""
    imm = pool - ((here + 4) & ~3)
    if imm < 0 or imm % 4 or imm > 0x3FC:
        raise SystemExit(f"patch_floor_indicators_fr: literal out of reach ({imm:#x})")
    return 0x4800 | (reg << 8) | (imm >> 2)


def _build_popup_floor_code(rdc_addr: int) -> bytes:
    """Assemble the French ``AppendFloorNumberString``.

    Layout is fixed so that the routine ends exactly where the English one did
    (``0x0984D8``); the two literal words sit at the tail of the same region.
    """
    base = POPUP_FLOOR_FUNC
    l_pos = base + 0x26
    l_conv = base + 0x2E
    l_term = base + 0x40
    l_rdc = base + 0x46
    l_roof = base + 0x4A
    l_app = base + 0x4C
    l_ret = base + 0x52
    pool_rdc = base + 0x54
    pool_roof = base + 0x58

    conv_hi, conv_lo = _bl(base + 0x34, CONVERT_INT_TO_DECIMAL_STRING_N)
    append_hi, append_lo = _bl(base + 0x4E, STRING_APPEND)

    code = [
        0xB510,                                  # push {r4, lr}
        0x1C02,                                  # adds r2, r0, #0      ; r2 = dest
        0x0609,                                  # lsls r1, r1, #24
        0x1609,                                  # asrs r1, r1, #24     ; r1 = s8 floor
        0x2900,                                  # cmp  r1, #0
        _branch(base + 0x0A, l_ret, cond=0x0),   # beq  Lret            ; pas d'étage
        0x2000 | CHAR_SPACE,                     # movs r0, #' '
        0x7010,                                  # strb r0, [r2]
        0x3201,                                  # adds r2, #1
        0x297F,                                  # cmp  r1, #0x7F
        _branch(base + 0x14, l_roof, cond=0x0),  # beq  Lroof           ; « TOIT »
        0x2400,                                  # movs r4, #0          ; suffixe: aucun
        0x2900,                                  # cmp  r1, #0
        _branch(base + 0x1A, l_pos, cond=0xC),   # bgt  Lpos
        0x2000 | CHAR_MINUS,                     # movs r0, #'-'        ; sous-sol
        0x7010,                                  # strb r0, [r2]
        0x3201,                                  # adds r2, #1
        0x4249,                                  # rsbs r1, r1, #0      ; |floor|
        _branch(base + 0x24, l_conv),            # b    Lconv
        0x2901,                                  # Lpos: cmp r1, #1
        _branch(base + 0x28, l_rdc, cond=0x0),   # beq  Lrdc            ; 1F -> RDC
        0x3901,                                  # subs r1, #1          ; nF -> (n-1)E
        0x2400 | CHAR_E,                         # movs r4, #'E'
        0x1C10,                                  # Lconv: adds r0, r2, #0
        0x2200,                                  # movs r2, #0          ; mode aligné à gauche
        0x2302,                                  # movs r3, #2          ; 2 chiffres max
        conv_hi, conv_lo,                        # bl   ConvertIntToDecimalStringN
        0x2C00,                                  # cmp  r4, #0
        _branch(base + 0x3A, l_term, cond=0x0),  # beq  Lterm
        0x7004,                                  # strb r4, [r0]
        0x3001,                                  # adds r0, #1
        0x21FF,                                  # Lterm: movs r1, #0xFF
        0x7001,                                  # strb r1, [r0]
        _branch(base + 0x44, l_ret),             # b    Lret
        _ldr_pc(base + 0x46, pool_rdc, reg=1),   # Lrdc:  ldr r1, =RDC
        _branch(base + 0x48, l_app),             # b    Lapp
        _ldr_pc(base + 0x4A, pool_roof, reg=1),  # Lroof: ldr r1, =ROOFTOP
        0x1C10,                                  # Lapp:  adds r0, r2, #0
        append_hi, append_lo,                    # bl   StringAppend
        0xBD10,                                  # Lret:  pop {r4, pc}
    ]
    blob = struct.pack(f"<{len(code)}H", *code)
    blob += struct.pack("<II", rdc_addr, ROOFTOP_STRING)
    if len(blob) != POPUP_FLOOR_FUNC_SIZE:
        raise SystemExit(
            f"patch_floor_indicators_fr: routine de {len(blob)} octets, "
            f"{POPUP_FLOOR_FUNC_SIZE} attendus"
        )
    return blob


def _popup_floor_code(source: bytes, rdc_addr: int) -> bytes:
    """Assemble the banner routine after checking the base ROM still holds it.

    Overwriting 92 bytes of code is only safe as long as those bytes really are
    ``AppendFloorNumberString``; a fingerprint mismatch means the layout moved,
    and the build must fail rather than corrupt whatever moved in.
    """
    actual = source[POPUP_FLOOR_FUNC:POPUP_FLOOR_FUNC_END]
    if actual != ORIGINAL_POPUP_FLOOR_CODE:
        raise SystemExit(
            "patch_floor_indicators_fr: AppendFloorNumberString "
            f"@0x{POPUP_FLOOR_FUNC:X} does not match the expected base ROM code "
            f"({actual.hex()}) — layout changed, aborting."
        )
    return _build_popup_floor_code(rdc_addr)


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


def _extra_targets(source: bytes, label_addr: dict[str, int]) -> dict[int, int]:
    """Resolve ``EXTRA_SLOTS`` to ``slot -> French label address``.

    Every pinned slot must still hold, *in the base ROM*, the pointer to the
    English cell it was recorded against. A mismatch means the ROM layout moved
    and repointing would corrupt unrelated bytes, so we abort the build instead.
    """
    targets: dict[int, int] = {}
    for slot, (en_cell, label) in EXTRA_SLOTS.items():
        actual = struct.unpack_from("<I", source, slot)[0]
        if actual != ROM_BASE + en_cell:
            raise SystemExit(
                f"patch_floor_indicators_fr: slot 0x{slot:X} holds 0x{actual:08X} "
                f"instead of 0x{ROM_BASE + en_cell:08X} in the base ROM — layout "
                "changed, aborting."
            )
        targets[slot] = label_addr[label]
    return targets


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
    label_addr: dict[str, int] = {}
    block = bytearray()
    cursor = FLOOR_STR_OFFSET
    for en_off in FR_LABELS:  # dict preserves insertion (table) order
        encoded = _encode(FR_LABELS[en_off])
        dest_addr[en_off] = ROM_BASE + cursor
        label_addr[FR_LABELS[en_off]] = ROM_BASE + cursor
        block += encoded
        cursor += len(encoded)

    extra_targets = _extra_targets(source, label_addr)

    # The place-name banner spells its floor in code, not in a string cell.
    popup_code = _popup_floor_code(source, label_addr["RDC"])

    # Idempotency: already fully applied?
    already = (
        rom[FLOOR_STR_OFFSET:FLOOR_STR_OFFSET + len(block)] == block
        and rom[POPUP_FLOOR_FUNC:POPUP_FLOOR_FUNC_END] == popup_code
        and all(
            struct.unpack_from("<I", rom, slot)[0] == dest_addr[en_off]
            for en_off, slist in slots.items()
            for slot in slist
        )
        and all(
            struct.unpack_from("<I", rom, slot)[0] == addr
            for slot, addr in extra_targets.items()
        )
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

    extra_patched = 0
    for slot, addr in extra_targets.items():
        if struct.unpack_from("<I", rom, slot)[0] != addr:
            struct.pack_into("<I", rom, slot, addr)
            extra_patched += 1

    banner = rom[POPUP_FLOOR_FUNC:POPUP_FLOOR_FUNC_END] != popup_code
    if banner:
        rom[POPUP_FLOOR_FUNC:POPUP_FLOOR_FUNC_END] = popup_code

    print(
        f"  floor indicators: 15 labels @0x{FLOOR_STR_OFFSET:07X}, "
        f"{patched}/{total_slots} pointer(s) repointed, "
        f"{extra_patched}/{len(extra_targets)} place-bound label(s) repointed, "
        f"banner routine {'rewritten' if banner else 'already French'}"
    )
    return patched + extra_patched + int(banner)


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
