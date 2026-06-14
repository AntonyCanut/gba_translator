"""Regression guard for the post-Zeph "give CS" sequence.

Ticket "Problème pas de gain d'objet": after beating Zeph the player is
kidnapped, escapes through a portal and a hillbilly NPC hands over the CS
(Coupe / Cut).  On an earlier build the game crashed at the *object gain*
step.  The crash class for a Gen-III text engine is a malformed string:

  * a string with no ``0xFF`` terminator -> the printer runs away into the
    next bytes (script/code) and the CPU jumps to garbage;
  * a multi-byte control code (``FC <cmd> <args>`` / ``FD <var>``) left
    dangling right before the terminator -> the engine reads ``0xFF`` as an
    argument/command and desyncs;
  * a buffer placeholder (``FD <var>``) count that no longer matches the
    English original -> the wrong / an unset ``gStringVar`` is dereferenced
    while building the "obtained the <ITEM>!" message.

This test re-reads the *built* French ROM and asserts every string used by
that sequence is byte-clean and structurally identical (control-code wise)
to the English source it was translated from.  It is deterministic (no
emulator) so it "holds" as a CI regression guard.
"""

import importlib

import pytest

from src.core.text_codec import TextDecoder

# Authoritative control-code parsing, shared with the ROM builder so this
# guard can never drift from how the engine actually reads the bytes.
_builder = importlib.import_module("src.translators.19_build_translated_rom_generic")
TranslatedROMBuilder = _builder.TranslatedROMBuilder
FC_ARG_COUNTS = TranslatedROMBuilder.FC_ARG_COUNTS

POKEMON_TERMINATOR = 0xFF
# Control prefixes that consume a fixed number of trailing argument bytes.
RAW_ARG_PREFIXES = {0xF7: 1, 0xF8: 1, 0xF9: 1, 0xFD: 1}
# Single-byte text-flow controls (newline / scroll / page).
FLOW_CONTROLS = {0xFA, 0xFB, 0xFE}

# Offsets (English extraction offsets, written in-place by the build) of every
# string the "give CS" object-gain chain renders, in story order.
SEQUENCE = {
    "hillbilly_intro": 0x1F33067,        # "...sortir d'un portail magique"
    "hillbilly_give_cs": 0x1F3316D,      # "Alors, prends cette CS pour aller le voir." (screenshot)
    "cs_explanation": 0x1F33351,         # explains a CS, hands over Coupe / Cut
    "item_obtained": 0x1A5DF1,           # "{PLAYER} a obtenu le {ITEM} !"  <- the object-gain message
    "move_learn_full": 0x416DF7,         # party full -> ask to forget a move
    "which_move_forget": 0x416EA4,       # "Quelle capacité oublier ?<FC09>"
    "learned_via_cs": 0x41A938,          # learned the CS move
    "learned_via_cs_forgot": 0x41A965,   # learned the CS move and forgot another
}

MAX_STRING_BYTES = 1024  # any sequence string terminates well within this


def _read_string(rom: bytes, offset: int):
    """Return (raw_bytes_including_FF, terminator_index) or (chunk, None)."""
    end = rom.find(b"\xff", offset, offset + MAX_STRING_BYTES)
    if end == -1:
        return rom[offset:offset + MAX_STRING_BYTES], None
    return rom[offset:end + 1], end - offset


def _walk_control_codes(raw: bytes):
    """Yield (index, prefix, length) for every control code; raise on a code
    that runs past the ``0xFF`` terminator (i.e. is truncated / dangling)."""
    i = 0
    n = len(raw)
    while i < n:
        b = raw[i]
        if b == POKEMON_TERMINATOR:
            return
        if b == 0xFC:
            if i + 1 >= n - 1:  # need at least a command byte before FF
                raise AssertionError(f"dangling FC at +{i}")
            cmd = raw[i + 1]
            arg_count = FC_ARG_COUNTS.get(cmd, 0)
            length = 2 + arg_count
            if i + length > n - 1:  # args would overrun into / past the FF
                raise AssertionError(
                    f"FC {cmd:02X} truncated at +{i} (needs {arg_count} args)"
                )
            yield (i, 0xFC, length)
            i += length
            continue
        if b in RAW_ARG_PREFIXES:
            length = 1 + RAW_ARG_PREFIXES[b]
            if i + length > n - 1:
                raise AssertionError(f"dangling {b:02X} at +{i}")
            yield (i, b, length)
            i += length
            continue
        i += 1


def _control_signature(raw: bytes):
    """Ordered list of buffer/extended control codes (flow controls ignored)."""
    sig = []
    for idx, prefix, length in _walk_control_codes(raw):
        sig.append(tuple(raw[idx:idx + length]))
    return sig


from tests.e2e.conftest import EN_ROM_PATH, FR_ROM_PATH


@pytest.fixture(scope="module")
def fr_rom():
    if not FR_ROM_PATH.exists():
        pytest.skip("GenedRom-fr.gba not found in output/roms/ (run `make build-fr`)")
    return FR_ROM_PATH.read_bytes()


@pytest.fixture(scope="module")
def en_rom():
    if not EN_ROM_PATH.exists():
        pytest.skip("englishrom.gba not found in input/roms/")
    return EN_ROM_PATH.read_bytes()


@pytest.mark.parametrize("name,offset", list(SEQUENCE.items()))
def test_sequence_string_is_terminated(fr_rom, name, offset):
    """No runaway text: every string ends with 0xFF (else the printer reads
    script/code as text and the CPU crashes)."""
    _, term = _read_string(fr_rom, offset)
    assert term is not None, f"{name} @0x{offset:X}: no 0xFF terminator within {MAX_STRING_BYTES} bytes"


@pytest.mark.parametrize("name,offset", list(SEQUENCE.items()))
def test_sequence_control_codes_well_formed(fr_rom, name, offset):
    """No dangling/truncated multi-byte control code before the terminator."""
    raw, _ = _read_string(fr_rom, offset)
    # consuming the generator raises AssertionError on any malformed code
    list(_walk_control_codes(raw))


@pytest.mark.parametrize("name,offset", list(SEQUENCE.items()))
def test_sequence_string_decodes(fr_rom, name, offset):
    """The bytes decode cleanly with the French charmap (no unknown glyphs
    that would indicate corruption)."""
    raw, _ = _read_string(fr_rom, offset)
    text = TextDecoder.decode_pokemon(raw)
    assert text, f"{name} @0x{offset:X}: decoded to empty string"


@pytest.mark.parametrize("name,offset", list(SEQUENCE.items()))
def test_sequence_buffer_codes_match_english(fr_rom, en_rom, name, offset):
    """The set/order of ``FD <var>`` buffer references is identical to the
    English source.  A mismatch means the "{PLAYER} obtained the {ITEM}!"
    style messages would dereference the wrong / an unset gStringVar -> the
    object-gain crash this ticket is about."""
    fr_raw, _ = _read_string(fr_rom, offset)
    en_raw, _ = _read_string(en_rom, offset)

    def fd_refs(raw):
        return [sig for sig in _control_signature(raw) if sig[0] == 0xFD]

    assert fd_refs(fr_raw) == fd_refs(en_raw), (
        f"{name} @0x{offset:X}: buffer (FD) references diverged from English\n"
        f"  FR: {fd_refs(fr_raw)}\n  EN: {fd_refs(en_raw)}"
    )


# ---------------------------------------------------------------------------
# Object-gain *script* guard (the non-text crash class).
#
# The string guards above only cover the dialogue the engine prints. The crash
# the user reopened this ticket about happens at the *object gain* itself, after
# the "Alors, prends cette CS pour aller le voir." box (screenshot): the NPC
# event script runs ``giveitem CS``. That is plain script bytecode, not text, so
# a build pass that mis-rewrote a relocated text pointer into the script (the
# documented `_plausible_pointer_sites` false-positive class) would corrupt the
# giveitem command and crash *without* any string looking wrong.
#
# This sequence was reproduced end-to-end in mGBA from the ticket save (kidnap
# cutscene -> Ivory/Zeph battles -> portal escape -> hillbilly hands the CS):
# the item (id 0x01B5) is added to the bag and the game does NOT crash on the
# current build. These assertions pin the bytecode that makes that true so a
# future rebuild can't silently regress it.
# ---------------------------------------------------------------------------

# Disassembled give-CS NPC event script (file offsets; addr = 0x08000000 + off).
GIVE_CS_SCRIPT_LO = 0x1E79360
GIVE_CS_SCRIPT_HI = 0x1E79460
# The giveitem block right after the "give CS" dialogue:
#   1A 00 80 B5 01   setorcopyvar 0x8000 = 0x01B5   (the CS item id)
#   1A 01 80 01 00   setorcopyvar 0x8001 = 0x0001   (quantity)
#   09 00            callstd 0                       (STD_OBTAIN_ITEM)
GIVE_CS_GIVEITEM_OFF = 0x1E79392
GIVE_CS_GIVEITEM_LEN = 12
CS_ITEM_ID = 0x01B5

ROM_BASE = 0x08000000
ROM_END = 0x0A000000


def _loadword_sites(rom: bytes, lo: int, hi: int):
    """Yield (offset, pointer) for every ``loadword 0, <ptr>`` (0F 00 ptr4) in
    [lo, hi) — i.e. every msgbox text operand the script feeds to callstd."""
    i = lo
    while i < hi - 5:
        if rom[i] == 0x0F and rom[i + 1] == 0x00:
            ptr = int.from_bytes(rom[i + 2:i + 6], "little")
            yield (i, ptr)
            i += 6
            continue
        i += 1


def test_give_cs_giveitem_command_intact(fr_rom, en_rom):
    """The ``giveitem`` block must stay byte-identical to English and still set
    var 0x8000 to the CS id (0x01B5) and run ``callstd 0`` (STD_OBTAIN_ITEM).
    Corruption here is the object-gain crash this ticket is about."""
    fr_block = fr_rom[GIVE_CS_GIVEITEM_OFF:GIVE_CS_GIVEITEM_OFF + GIVE_CS_GIVEITEM_LEN]
    en_block = en_rom[GIVE_CS_GIVEITEM_OFF:GIVE_CS_GIVEITEM_OFF + GIVE_CS_GIVEITEM_LEN]
    assert fr_block == en_block, (
        f"give-CS giveitem bytecode diverged from English @0x{GIVE_CS_GIVEITEM_OFF:X}\n"
        f"  FR: {fr_block.hex()}\n  EN: {en_block.hex()}"
    )
    # Decode it explicitly so the guard fails loudly if the structure changes.
    assert fr_block[0] == 0x1A and int.from_bytes(fr_block[1:3], "little") == 0x8000, (
        "expected `setorcopyvar 0x8000, <item>`"
    )
    assert int.from_bytes(fr_block[3:5], "little") == CS_ITEM_ID, (
        f"give-CS no longer grants item 0x{CS_ITEM_ID:X}"
    )
    assert fr_block[10:12] == b"\x09\x00", "expected `callstd 0` (STD_OBTAIN_ITEM)"


def test_give_cs_script_bytecode_matches_english(fr_rom, en_rom):
    """The whole give-CS event script must be byte-identical to English EXCEPT
    at msgbox text-pointer operands, which the build legitimately rewrites when
    it relocates a translated string. Any *other* diff is script-bytecode
    corruption — the non-text object-gain crash class."""
    allowed = set()
    for off, _ in _loadword_sites(en_rom, GIVE_CS_SCRIPT_LO, GIVE_CS_SCRIPT_HI):
        allowed.update(range(off + 2, off + 6))  # the 4 operand bytes only
    corrupt = [
        j
        for j in range(GIVE_CS_SCRIPT_LO, GIVE_CS_SCRIPT_HI)
        if fr_rom[j] != en_rom[j] and j not in allowed
    ]
    assert not corrupt, (
        "give-CS script bytecode diverged from English outside msgbox operands "
        f"(corruption): {[hex(c) for c in corrupt]}"
    )


def test_give_cs_script_msgbox_pointers_resolve(fr_rom):
    """Every dialogue the give-CS script feeds to ``callstd`` must point at a
    real, 0xFF-terminated ROM string — whether it was kept in place or relocated
    by the build. A dangling operand here = the engine prints from garbage and
    the CPU jumps off into the weeds during the object-gain scene."""
    sites = list(_loadword_sites(fr_rom, GIVE_CS_SCRIPT_LO, GIVE_CS_SCRIPT_HI))
    assert len(sites) >= 5, f"expected the give-CS script to render several boxes, found {len(sites)}"
    for off, ptr in sites:
        assert ROM_BASE <= ptr < ROM_END, (
            f"loadword @0x{off:X} has non-ROM operand 0x{ptr:08X}"
        )
        target = ptr - ROM_BASE
        end = fr_rom.find(b"\xff", target, target + MAX_STRING_BYTES)
        assert end != -1, (
            f"loadword @0x{off:X} -> 0x{ptr:08X}: string not 0xFF-terminated "
            f"within {MAX_STRING_BYTES} bytes (dangling/relocated-to-garbage)"
        )
