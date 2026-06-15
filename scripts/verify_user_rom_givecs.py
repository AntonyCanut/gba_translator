#!/usr/bin/env python3
"""verify_user_rom_givecs.py — does YOUR ROM have the clean "give CS" sequence?

Ticket "Problème pas de gain d'objet" (freeze on the hillbilly's
"Alors, prends cette CS pour aller le voir." box, screenshot).

Static analysis proved that on the current FR build every byte the engine
touches during that gift — the event-script bytecode (msgbox -> giveitem 0x01B5
-> callstd 0), the granted item's whole 44-byte struct, the dialogue string
slot, and the obtain message — is byte-identical to the English ROM (which does
not freeze) apart from the intentionally translated French text. So a freeze
there can only come from a **stale / divergent ROM**, not from the translation.

This tool settles it: point it at the ROM file you are actually PLAYING and it
reports its SHA-256 and whether its give-CS region matches the known-good build.

Usage:
    python3 scripts/verify_user_rom_givecs.py /path/to/your_rom.gba
    python3 scripts/verify_user_rom_givecs.py            # checks output/roms/GenedRom-fr.gba

Exit code 0 = give-CS region clean; 1 = divergent (rebuild / re-download); 2 = usage error.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

ROM_BASE = 0x08000000
MAX_STRING_BYTES = 1024

# --- give-CS regions (file offsets) -----------------------------------------
GIVE_CS_SCRIPT_LO = 0x1E79360
GIVE_CS_SCRIPT_HI = 0x1E79460
GIVE_CS_STRING_OFF = 0x1F3316D          # the screenshot dialogue
GIVE_CS_NEXT_STRING_OFF = 0x1F33351     # next string (slot boundary)
GIVE_CS_SLOT_BYTES = GIVE_CS_NEXT_STRING_OFF - GIVE_CS_STRING_OFF  # 484
OBTAIN_MSG_OFF = 0x1A5DF1               # "{PLAYER} a obtenu le {ITEM} !"
ITEM_TABLE_BASE = 0x876074
ITEM_STRIDE = 44
CS_ITEM_ID = 0x01B5
ITEM_ENTRY_OFF = ITEM_TABLE_BASE + CS_ITEM_ID * ITEM_STRIDE

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
EN_ROM_PATH = PROJECT_ROOT / "input" / "roms" / "englishrom.gba"
FR_ROM_PATH = PROJECT_ROOT / "output" / "roms" / "GenedRom-fr.gba"


ROM_BASE_PTR = 0x08000000

# Argument bytes per FC extended control command (Gen III ExtCtrlCode); a code
# whose args would overrun the 0xFF terminator is "dangling" -> printer runaway.
FC_ARG_COUNTS = {
    0x01: 1, 0x02: 1, 0x03: 1, 0x04: 3, 0x05: 1, 0x06: 1,
    0x08: 1, 0x0B: 2, 0x0C: 1, 0x0D: 1, 0x0E: 1, 0x10: 2,
    0x11: 1, 0x12: 1, 0x13: 1, 0x14: 1, 0x19: 1,
}
RAW_ARG_PREFIXES = {0xF7: 1, 0xF8: 1, 0xF9: 1, 0xFD: 1}


def _loadword_operand_bytes(rom: bytes, lo: int, hi: int) -> set[int]:
    """Offsets of every `loadword 0, <ptr>` (0F 00 ptr4) operand in [lo, hi)."""
    allowed: set[int] = set()
    i = lo
    while i < hi - 5:
        if rom[i] == 0x0F and rom[i + 1] == 0x00:
            allowed.update(range(i + 2, i + 6))
            i += 6
            continue
        i += 1
    return allowed


def _loadword_pointers(rom: bytes, lo: int, hi: int) -> list[tuple[int, int]]:
    """(operand_offset, pointer) for every `loadword 0, <ptr>` in [lo, hi)."""
    out: list[tuple[int, int]] = []
    i = lo
    while i < hi - 5:
        if rom[i] == 0x0F and rom[i + 1] == 0x00:
            out.append((i, int.from_bytes(rom[i + 2:i + 6], "little")))
            i += 6
            continue
        i += 1
    return out


def _dangling_control_code(rom: bytes, off: int, term: int) -> str | None:
    """Return a description if a multi-byte control code in [off, term) would
    consume the 0xFF terminator (its args overrun) -> the text printer never
    stops at this box and the dialogue window never closes (freeze). Else None."""
    i = off
    while i < term:
        b = rom[i]
        if b == 0xFC:
            cmd = rom[i + 1] if i + 1 < term + 1 else None
            if cmd is None:
                return f"dangling FC at +{i - off}"
            length = 2 + FC_ARG_COUNTS.get(cmd, 0)
            if i + length > term:  # args reach into / past the 0xFF
                return f"FC {cmd:02X} truncated at +{i - off} (eats terminator)"
            i += length
            continue
        if b in RAW_ARG_PREFIXES:
            length = 1 + RAW_ARG_PREFIXES[b]
            if i + length > term:
                return f"dangling {b:02X} at +{i - off} (eats terminator)"
            i += length
            continue
        i += 1
    return None


def _term(rom: bytes, off: int) -> int:
    return rom.find(b"\xff", off, off + MAX_STRING_BYTES)


def check(user: bytes, en: bytes) -> list[str]:
    """Return a list of problems (empty == give-CS region is clean)."""
    problems: list[str] = []

    # 1. Event-script bytecode identical to EN except msgbox text operands.
    allowed = _loadword_operand_bytes(en, GIVE_CS_SCRIPT_LO, GIVE_CS_SCRIPT_HI)
    diff = [
        j for j in range(GIVE_CS_SCRIPT_LO, GIVE_CS_SCRIPT_HI)
        if user[j] != en[j] and j not in allowed
    ]
    if diff:
        problems.append(
            f"give-CS event-script bytecode diverges from English at "
            f"{[hex(d) for d in diff[:8]]}{' …' if len(diff) > 8 else ''} "
            f"(script corruption -> object-gain crash)"
        )

    # 2. Granted item 0x01B5 whole struct identical to EN.
    if user[ITEM_ENTRY_OFF:ITEM_ENTRY_OFF + ITEM_STRIDE] != en[ITEM_ENTRY_OFF:ITEM_ENTRY_OFF + ITEM_STRIDE]:
        problems.append(
            f"granted item 0x{CS_ITEM_ID:X} struct @0x{ITEM_ENTRY_OFF:X} diverges from English\n"
            f"      yours: {user[ITEM_ENTRY_OFF:ITEM_ENTRY_OFF + ITEM_STRIDE].hex()}\n"
            f"      clean: {en[ITEM_ENTRY_OFF:ITEM_ENTRY_OFF + ITEM_STRIDE].hex()}"
        )

    # 3. give-CS dialogue terminated and not overflowing its in-place slot.
    t = _term(user, GIVE_CS_STRING_OFF)
    if t == -1:
        problems.append(
            f"give-CS dialogue @0x{GIVE_CS_STRING_OFF:X} has NO 0xFF terminator -> "
            f"the text printer runs away (hard freeze)"
        )
    elif t >= GIVE_CS_NEXT_STRING_OFF:
        problems.append(
            f"give-CS dialogue @0x{GIVE_CS_STRING_OFF:X} OVERFLOWS its {GIVE_CS_SLOT_BYTES}-byte "
            f"slot (terminator at +{t - GIVE_CS_STRING_OFF}) -> clobbers the next string / freezes"
        )

    # 4. Obtain message terminated.
    if _term(user, OBTAIN_MSG_OFF) == -1:
        problems.append(
            f"obtain message @0x{OBTAIN_MSG_OFF:X} has NO 0xFF terminator -> obtain box freezes"
        )

    # 5. Follow EVERY dialogue pointer the give-CS script feeds to callstd —
    #    in-place AND build-relocated — and validate each resolves to a real,
    #    0xFF-terminated string with no dangling control code. The build relocates
    #    the verbose French boxes to free space at build-specific addresses, so a
    #    fixed-offset check (1-4 above) never sees them. A relocated pointer that
    #    lands on unwritten free space (0xFF) or a string whose last FC/FD eats
    #    its terminator is the "dialogue window won't close / freeze" this ticket
    #    is about. This is the check that actually follows the pointers.
    for off, ptr in _loadword_pointers(user, GIVE_CS_SCRIPT_LO, GIVE_CS_SCRIPT_HI):
        if not (ROM_BASE_PTR <= ptr < ROM_BASE_PTR + len(user)):
            problems.append(
                f"give-CS msgbox operand @0x{off:X} -> 0x{ptr:08X} is not a ROM "
                f"pointer (corrupt/un-repointed) -> prints garbage / freezes"
            )
            continue
        tgt = ptr - ROM_BASE_PTR
        term = _term(user, tgt)
        if term == -1:
            relocated = not (0x1F00000 <= tgt < 0x1F80000)
            problems.append(
                f"give-CS dialogue @0x{off:X} -> 0x{ptr:08X} "
                f"({'RELOCATED to free space' if relocated else 'in-place'}) has NO "
                f"0xFF terminator -> the dialogue window never closes (FREEZE)"
            )
            continue
        bad = _dangling_control_code(user, tgt, term)
        if bad:
            problems.append(
                f"give-CS dialogue @0x{off:X} -> 0x{ptr:08X}: {bad} -> the text "
                f"printer runs past the box and the window never closes (FREEZE)"
            )

    return problems


# Script operands (file offsets of the `loadword 0, <ptr>` that feed callstd).
GIVE_CS_BOX_OPERAND = 0x1E7938C   # loadword for the screenshot box ("...prends cette CS")


def _decode(raw: bytes) -> str:
    """Best-effort decode of a Pokémon string (without the trailing 0xFF)."""
    try:
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))
        from src.core.text_codec import TextDecoder  # noqa: PLC0415
        return TextDecoder.decode_pokemon(raw)
    except Exception:  # pragma: no cover - decoder is optional for the verdict
        return raw.hex()


def _show_give_cs_box(rom: bytes) -> None:
    """Print the give-CS dialogue box + obtain message exactly as the engine
    resolves them (following the live script pointer), so the user can visually
    confirm their ROM's text is intact."""
    ptr = int.from_bytes(rom[GIVE_CS_BOX_OPERAND:GIVE_CS_BOX_OPERAND + 4], "little")
    tgt = ptr - ROM_BASE_PTR
    print("give-CS box : (the screenshot dialogue, as your ROM stores it)")
    if not (0 <= tgt < len(rom)):
        print(f"   pointer 0x{ptr:08X} is not a ROM address — CORRUPT")
        print()
        return
    term = rom.find(b"\xff", tgt, tgt + MAX_STRING_BYTES)
    relocated = "" if 0x1F00000 <= tgt < 0x1F80000 else "  [relocated to free space]"
    if term == -1:
        print(f"   @0x{tgt:X}{relocated}: NO 0xFF terminator within {MAX_STRING_BYTES} bytes — RUNAWAY")
    else:
        text = _decode(rom[tgt:term]).replace("{PAGE}", "\n   ─── ").replace("{SCROLL}", " / ")
        print(f"   @0x{tgt:X}{relocated}  ({term - tgt} bytes, terminated)")
        for line in text.split("\n"):
            print(f"   | {line}")
    obt = rom.find(b"\xff", OBTAIN_MSG_OFF, OBTAIN_MSG_OFF + MAX_STRING_BYTES)
    if obt != -1:
        print(f"obtain msg  : | {_decode(rom[OBTAIN_MSG_OFF:obt])}")
    print()


def main(argv: list[str]) -> int:
    user_path = pathlib.Path(argv[1]) if len(argv) > 1 else FR_ROM_PATH
    if not user_path.exists():
        print(f"ERROR: ROM not found: {user_path}", file=sys.stderr)
        return 2
    if not EN_ROM_PATH.exists():
        print(f"ERROR: reference English ROM not found at {EN_ROM_PATH}", file=sys.stderr)
        return 2

    user = user_path.read_bytes()
    en = EN_ROM_PATH.read_bytes()

    print(f"ROM checked : {user_path}")
    print(f"size        : {len(user):,} bytes")
    print(f"SHA-256     : {hashlib.sha256(user).hexdigest()}")
    if FR_ROM_PATH.exists():
        clean = hashlib.sha256(FR_ROM_PATH.read_bytes()).hexdigest()
        print(f"clean build : {clean}{'  (EXACT MATCH)' if clean == hashlib.sha256(user).hexdigest() else ''}")
    print()

    # Decode and SHOW the actual give-CS box exactly as the engine prints it, by
    # following the live script pointer (not the fixed offset — the build may
    # relocate it). This lets you eyeball whether YOUR ROM's box is intact: a
    # freeze caused by data shows up here as truncated / garbage text or a box
    # that never terminates. A clean ROM shows the full, correctly-accented box
    # ending exactly at "Alors, prends cette CS pour aller le voir.".
    _show_give_cs_box(user)

    problems = check(user, en)
    if not problems:
        print("✅ give-CS sequence is CLEAN (byte-identical to the English engine path).")
        print("   This ROM cannot freeze at the hillbilly's CS gift due to translation data.")
        print("   If you still see the freeze, you are playing a DIFFERENT/older ROM file than")
        print("   this one — rebuild with `make build-fr` or re-download the current patch.")
        return 0

    print("❌ give-CS sequence is DIVERGENT — this build can freeze at the CS gift:")
    for p in problems:
        print(f"   - {p}")
    print("\n   Fix: rebuild from the current sources (`make build-fr`) and re-run this check.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
