"""E2E regression guard: the Ho-Oh -> Lugia *ritual* cutscene is byte-for-byte
logic-identical between EN and FR, and contains no unterminated strings.

== What this protects ==

The reported bug ("after the Ho-Oh battle, the Lugia battle never triggers, in
FR") would, if it were a *translation* regression, have to manifest as one of
exactly two things inside the encounter script:

  1. a SCRIPT-COMMAND change  -> the FR pipeline overwrote a setflag / compare /
     goto / battle opcode, breaking the chain that leads from Ho-Oh to Lugia; or
  2. an UNTERMINATED STRING   -> an in-place FR string lost its 0xFF terminator,
     so GetStringWidth loops forever (a freeze) before the Lugia command runs.

Both are checked here against the real ROMs.

== Where the encounter actually lives ==

Ho-Oh and Lugia are summoned by Hoopa during the Aklove "Prison Bottle" ritual
in the Temple of the Void. The script is in CFRU-expanded ROM:

  region              [0x1E8B000, 0x1E8D400)
  Lugia setwildbattle  0x1E8CB9B : b6 f9 00 4b 00 00   (f9 00 = Lugia, dex 249)
  Ho-Oh setwildbattle  0x1E8CC34 : b6 fa 00 4b 00 00   (fa 00 = Ho-Oh, dex 250)

After each battle the script reads the outcome:

  ... 25 38 01      special 0x0138         (run the scripted wild battle)
      27            waitstate
      26 0d 80 b4   specialvar VAR_0x800D = special 0xB4   (= battle outcome)
      21 0d 80 ..   compare VAR_0x800D to {4,5,7} -> branch

and BOTH the "defeated" (fall-through) and "caught" (outcome 7) branches set the
progression var `16 00 80 0f 80` = setvar VAR_0x8000 = 0x800F, so catching Ho-Oh
with a Quick Ball does NOT dead-end the ritual — it advances to Lugia exactly
like defeating it. (This was the prime suspect for the report; it is ruled out
in code.)

== The invariant ==

Across the whole region, EVERY byte that differs between EN and FR is a 4-byte
text pointer (EN -> 0x09Fxxxxx original text region, FR -> relocated free space).
There is not a single differing script-command byte. If a future build ever
mutates one encounter opcode, `test_ritual_logic_byte_identical` goes red.
"""

from __future__ import annotations

import pathlib

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
EN_ROM_PATH = PROJECT_ROOT / "input" / "roms" / "englishrom.gba"
FR_ROM_PATH = PROJECT_ROOT / "output" / "roms" / "GenedRom-fr.gba"

GBA_BASE = 0x08000000
GBA_END = 0x0A000000

# The Aklove / Hoopa portal ritual script region.
RITUAL_LO = 0x1E8B000
RITUAL_HI = 0x1E8D400

# Verified battle-command offsets (setwildbattle opcode 0xB6, species, lvl, item).
LUGIA_SETWILD = 0x1E8CB9B  # b6 f9 00 4b 00 00
HOOH_SETWILD = 0x1E8CC34   # b6 fa 00 4b 00 00
SPECIES_LUGIA = 0xF9
SPECIES_HOOH = 0xFA

# specialvar VAR_0x800D = special 0xB4  -> reads the battle outcome.
OUTCOME_READ = bytes([0x26, 0x0D, 0x80, 0xB4, 0x00])
# setvar VAR_0x8000 = 0x800F  -> the ritual-progression advance.
ADVANCE_VAR = bytes([0x16, 0x00, 0x80, 0x0F, 0x80])


@pytest.fixture(scope="module")
def en() -> bytes:
    if not EN_ROM_PATH.exists():
        pytest.skip("englishrom.gba not found")
    return EN_ROM_PATH.read_bytes()


@pytest.fixture(scope="module")
def fr() -> bytes:
    if not FR_ROM_PATH.exists():
        pytest.skip("GenedRom-fr.gba not found")
    return FR_ROM_PATH.read_bytes()


def _rd32(rom: bytes, o: int) -> int:
    return rom[o] | rom[o + 1] << 8 | rom[o + 2] << 16 | rom[o + 3] << 24


def _is_ptr(rom: bytes, o: int) -> bool:
    if o + 4 > len(rom):
        return False
    return GBA_BASE <= _rd32(rom, o) < GBA_END


def _diff_ranges(en: bytes, fr: bytes, lo: int, hi: int):
    ranges = []
    i = lo
    while i < hi:
        if en[i] != fr[i]:
            j = i
            while j < hi and en[j] != fr[j]:
                j += 1
            ranges.append((i, j))
            i = j
        else:
            i += 1
    return ranges


def test_ritual_logic_byte_identical(en: bytes, fr: bytes):
    """Every EN/FR difference in the ritual script is a relocated text pointer.

    Zero script-command bytes may differ. A failure here means the translation
    pipeline mutated an encounter opcode (flag / compare / goto / battle), which
    is exactly the class of change that could stop Lugia from triggering.
    """
    ranges = _diff_ranges(en, fr, RITUAL_LO, RITUAL_HI)
    assert ranges, "expected text-pointer relocations in the FR ritual region"

    non_pointer = []
    for a, b in ranges:
        # A legitimate translation diff is a 4-byte run that is a valid ROM
        # pointer in BOTH roms (EN original text -> FR relocated free space).
        if (b - a) == 4 and _is_ptr(en, a) and _is_ptr(fr, a):
            continue
        non_pointer.append((a, b, en[a:b].hex(), fr[a:b].hex()))

    assert not non_pointer, (
        "FR translation altered NON-text bytes in the Ho-Oh/Lugia ritual script "
        "(possible encounter-logic regression):\n"
        + "\n".join(
            f"  0x{a:07X}..0x{b:07X} EN={eh} FR={fh}" for a, b, eh, fh in non_pointer
        )
    )


def test_battle_commands_present_and_identical(en: bytes, fr: bytes):
    """Both setwildbattle commands exist, with the right species, identical EN/FR."""
    for off, species, name in (
        (LUGIA_SETWILD, SPECIES_LUGIA, "Lugia"),
        (HOOH_SETWILD, SPECIES_HOOH, "Ho-Oh"),
    ):
        assert fr[off] == 0xB6, f"{name}: setwildbattle opcode 0xB6 missing @ 0x{off:07X}"
        assert fr[off + 1] == species, (
            f"{name}: species byte 0x{species:02X} missing @ 0x{off + 1:07X} "
            f"(got 0x{fr[off + 1]:02X})"
        )
        assert fr[off + 2] == 0x00, f"{name}: species high byte must be 0x00"
        # Logic must match EN exactly across the whole 6-byte command.
        assert en[off:off + 6] == fr[off:off + 6], (
            f"{name}: setwildbattle command differs EN vs FR @ 0x{off:07X}"
        )


def test_outcome_read_follows_each_battle(en: bytes, fr: bytes):
    """The battle-outcome read (specialvar 0xB4) appears shortly after each battle."""
    for off, name in ((LUGIA_SETWILD, "Lugia"), (HOOH_SETWILD, "Ho-Oh")):
        window = fr[off:off + 0x20]
        assert OUTCOME_READ in window, (
            f"{name}: battle-outcome read {OUTCOME_READ.hex()} not found after "
            f"setwildbattle @ 0x{off:07X}"
        )


def test_catching_hooh_does_not_dead_end_lugia(en: bytes, fr: bytes):
    """Both the 'defeated' and 'caught' Ho-Oh branches set the progression var.

    Documents (and guards) the in-code fact that capturing Ho-Oh with a Quick
    Ball advances the ritual to Lugia exactly like KO'ing it — the outcome-7
    (CAUGHT) branch sets `setvar VAR_0x8000 = 0x800F` just like the fall-through
    (defeated) branch. The two occurrences live in the Ho-Oh block, between its
    battle command and the next block.
    """
    block = fr[HOOH_SETWILD:HOOH_SETWILD + 0x90]
    occurrences = block.count(ADVANCE_VAR)
    assert occurrences >= 2, (
        "expected the Ho-Oh progression var (setvar VAR_0x8000=0x800F) on BOTH "
        f"the defeated and caught branches; found {occurrences} occurrence(s). "
        "If this drops to 1, catching Ho-Oh may no longer chain into Lugia."
    )
    # And the same logic must hold in EN (proves it is not an FR-specific change).
    assert en[HOOH_SETWILD:HOOH_SETWILD + 0x90].count(ADVANCE_VAR) == occurrences


def _loadpointer_text_refs(rom: bytes, lo: int, hi: int):
    """Yield (site, target_offset) for every `0F 00 <ptr>` text load in [lo,hi)."""
    refs = []
    for o in range(lo, hi - 6):
        if rom[o] == 0x0F and rom[o + 1] == 0x00:
            p = _rd32(rom, o + 2)
            if GBA_BASE <= p < GBA_END:
                refs.append((o, p - GBA_BASE))
    return refs


def test_all_ritual_strings_terminated(fr: bytes):
    """No string referenced by the ritual script is unterminated (freeze guard).

    An in-place FR string that overflowed its slot would lose the neighbouring
    0xFF, and the engine's word-wrapper would loop forever when the box renders
    — appearing in-game as "the game froze and Lugia never came". Every text
    pointer in the script must resolve to a 0xFF within a sane length.
    """
    MAX = 800  # longest legit multi-page dialogue here is ~632 bytes, terminated.
    refs = _loadpointer_text_refs(fr, RITUAL_LO, RITUAL_HI)
    assert len(refs) > 100, "sanity: expected many text refs in the ritual script"

    unterminated = []
    for site, off in refs:
        window = fr[off:off + MAX]
        if 0xFF not in window:
            unterminated.append((site, off))

    assert not unterminated, (
        "Unterminated FR string(s) referenced by the ritual script — would "
        "freeze the cutscene before Lugia triggers:\n"
        + "\n".join(f"  site 0x{s:07X} -> text 0x{o:07X}" for s, o in unterminated)
    )


# --- B-56 follow-up: prove CAPTURE is not a dead end, for BOTH legendaries ---
#
# The reopened report is specifically "after CAPTURING Ho-Oh, the scene that
# leads to Lugia never plays". Decoded from both ROMs, each battle block handles
# all three relevant wild-battle outcomes and advances the ritual on every one:
#
#   outcome 7 (CAUGHT)        -> setflag <caught-flag>; setvar VAR_0x8000=0x800F
#   outcomes 4/5 (RAN/TELE)   -> setvar VAR_0x8000=0x800F
#   fall-through (1 = WON)    -> setvar VAR_0x8000=0x800F
#
# so the progression var is set THREE times per block (once per branch), and the
# caught branch additionally raises a per-legendary "caught" flag. None of this
# differs EN vs FR.
ADVANCE_VAR_3X = 3
HOOH_CAUGHT_SETFLAG = bytes([0x29, 0xDF, 0x15])   # setflag 0x15DF @ 0x1E8CC94
LUGIA_CAUGHT_SETFLAG = bytes([0x29, 0xDE, 0x15])  # setflag 0x15DE @ 0x1E8CBFB

# Block spans (battle-command start -> just past the outcome handler).
LUGIA_BLOCK = (LUGIA_SETWILD, HOOH_SETWILD)         # 0x1E8CB9B .. 0x1E8CC34
HOOH_BLOCK = (HOOH_SETWILD, HOOH_SETWILD + 0xCC)    # 0x1E8CC34 .. 0x1E8CD00


@pytest.mark.parametrize(
    "block, setflag, name",
    [
        (HOOH_BLOCK, HOOH_CAUGHT_SETFLAG, "Ho-Oh (caught flag 0x15DF)"),
        (LUGIA_BLOCK, LUGIA_CAUGHT_SETFLAG, "Lugia (caught flag 0x15DE)"),
    ],
)
def test_caught_branch_advances_and_raises_flag(en, fr, block, setflag, name):
    """Capturing each legendary advances the ritual AND raises its caught flag.

    This is the crux of the reopened B-56 report. If catching Ho-Oh (or Lugia)
    with a Quick Ball were a dead end, the caught branch would be missing either
    the progression var or the flag. Both are present, and identical EN vs FR.
    """
    lo, hi = block
    seg_fr = fr[lo:hi]
    seg_en = en[lo:hi]

    assert setflag in seg_fr, (
        f"{name}: caught branch must raise its caught flag {setflag.hex()} "
        "(missing -> capture may dead-end the ritual)"
    )
    # All three outcome branches (WON / RAN-TELE / CAUGHT) advance the ritual.
    assert seg_fr.count(ADVANCE_VAR) == ADVANCE_VAR_3X, (
        f"{name}: expected the progression var on all 3 outcome branches, "
        f"found {seg_fr.count(ADVANCE_VAR)}"
    )
    # And EN behaves identically -> this is NOT an FR-specific change.
    assert seg_en.count(ADVANCE_VAR) == seg_fr.count(ADVANCE_VAR)
    assert (setflag in seg_en) == (setflag in seg_fr)


def test_lugia_block_is_wired_like_hooh(en, fr):
    """The Lugia battle block exists and mirrors Ho-Oh's outcome handling.

    Guards against a build that drops/relocates the Lugia battle wiring while
    leaving Ho-Oh intact. Both blocks must contain: the setwildbattle command,
    the outcome read (specialvar 0xB4), and the progression advance.
    """
    for off, species, name in (
        (LUGIA_SETWILD, SPECIES_LUGIA, "Lugia"),
        (HOOH_SETWILD, SPECIES_HOOH, "Ho-Oh"),
    ):
        block = fr[off:off + 0x90]
        assert block[0] == 0xB6 and block[1] == species, f"{name}: setwildbattle wiring"
        assert OUTCOME_READ in block, f"{name}: outcome read missing"
        assert ADVANCE_VAR in block, f"{name}: progression advance missing"


# Cross-build guard: the build the user actually downloads (the release ROM) must
# carry the same ritual logic as the freshly-built output ROM. All shipped FR
# builds share EN's encounter logic; only relocated text differs.
_CANDIDATE_RELEASE_BUILDS = [
    PROJECT_ROOT.parent / "Unbound" / "release" / "pokemon_unbound_fr.gba",
    PROJECT_ROOT.parent / "Unbound" / "data" / "frenchrom.gba",
]


@pytest.mark.parametrize(
    "release_path", _CANDIDATE_RELEASE_BUILDS, ids=lambda p: p.name
)
def test_release_build_ritual_logic_matches_en(en, release_path):
    """Any shipped FR release build's ritual logic is byte-identical to EN.

    Same invariant as test_ritual_logic_byte_identical, applied to the release
    artefacts the user plays — so a stale/older download is also covered.
    """
    if not release_path.exists():
        pytest.skip(f"{release_path.name} not present")
    rel = release_path.read_bytes()
    ranges = _diff_ranges(en, rel, RITUAL_LO, RITUAL_HI)
    non_pointer = [
        (a, b) for a, b in ranges
        if not ((b - a) == 4 and _is_ptr(en, a) and _is_ptr(rel, a))
    ]
    assert not non_pointer, (
        f"{release_path.name}: NON-text byte differs from EN in the ritual "
        f"script (encounter-logic regression): "
        + ", ".join(f"0x{a:07X}..0x{b:07X}" for a, b in non_pointer)
    )


# --- P-70: the repointer clobbers EVERY legendary-cutscene setflag chain ---
#
# The Ho-Oh/Lugia checks above guard only the [0x1E8B000, 0x1E8D400) region, but
# the same `repoint_stale_text_pointers` false-match hits 13 sites ROM-wide,
# including Groudon's Red-Orb summon (0x1E59D1F). When only Ho-Oh/Lugia were
# patched, every rebuild left the other 11 (Groudon among them) clobbered and the
# summon dialogue looped forever. This guard fails on ANY clobbered site.
#
# Signature: a 4-byte window == `08 29 F6 09` (LE 0x09F62908, the EN address of
# "I swam, of course!") that the repointer rewrites to the relocated FR text
# pointer (the address of "J'ai nagé, bien sûr !"). A real setflag chain has the
# *previous* setflag opcode (0x29) two bytes before the window; the two genuine
# relocated text pointers that share the bytes (0x1E8738D, 0x1E873B4) do not, and
# must stay French.
#
# The relocated FR address is BUILD-DEPENDENT (free-space layout shifts as
# translations are added — 0x08C277E1 in older builds, 0x08C421A6 here, "anything
# in 0x08xxxxxx" per patch_legendary_ritual_fr.py). So the genuine-pointer guard
# below checks the *property* (still FR, not reverted to EN), never a frozen
# address.
_SETFLAG_WINDOW = bytes([0x08, 0x29, 0xF6, 0x09])
_SETFLAG_OPCODE = 0x29
_EN_RITUAL_TEXT_PTR = 0x09F62908  # EN "I swam, of course!" — must NOT come back
_FR_RITUAL_TEXT_HEAD = bytes([0xC4, 0xB4])  # "J'" — start of "J'ai nagé, bien sûr !"
_GENUINE_RELOCATED_POINTERS = (0x1E8738D, 0x1E873B4)


def _setflag_chain_sites(rom: bytes):
    sites, start = [], 0
    while True:
        off = rom.find(_SETFLAG_WINDOW, start)
        if off == -1:
            break
        start = off + 1
        if off >= 2 and rom[off - 2] == _SETFLAG_OPCODE:
            sites.append(off)
    return sites


def test_no_legendary_setflag_chain_is_clobbered(en: bytes, fr: bytes):
    """Every legendary-cutscene `setflag` chain is restored to EN (battle launches).

    Discovered by signature (not an allow-list) so Groudon and its ~10 siblings
    are covered, not just Ho-Oh/Lugia. A clobbered site = the relocated FR
    pointer 0x08C277E1 sitting in script bytecode -> the cutscene never reaches
    `special 0x138` and the summon loops.
    """
    sites = _setflag_chain_sites(en)
    assert len(sites) >= 13, f"sanity: expected >=13 setflag-chain sites, found {len(sites)}"

    clobbered = [
        off for off in sites
        if bytes(fr[off:off + 4]) != bytes(en[off:off + 4])
    ]
    assert not clobbered, (
        "Clobbered legendary-cutscene setflag chain(s) — the summon will loop "
        "and the legendary battle never launches:\n"
        + "\n".join(
            f"  0x{o:07X} EN={en[o:o+4].hex()} FR={fr[o:o+4].hex()}"
            for o in clobbered
        )
    )


def test_genuine_relocated_pointers_stay_french(en: bytes, fr: bytes):
    """The two real relocated text pointers sharing the setflag bytes are NOT
    reverted to EN by the repair (they legitimately point at relocated FR text).

    Guards the *property*, not a frozen address: each must (a) be a valid GBA
    pointer, (b) NOT revert to the EN pointer 0x09F62908 ("I swam, of course!"),
    (c) agree with its twin, and (d) resolve to the French string
    "J'ai nagé, bien sûr !" (not the English original). The exact relocated
    address shifts between builds as free space is reallocated.
    """
    targets = []
    for off in _GENUINE_RELOCATED_POINTERS:
        ptr = _rd32(fr, off)
        assert GBA_BASE <= ptr < GBA_END, (
            f"genuine relocated pointer 0x{off:07X} = 0x{ptr:08X} is not a valid "
            "GBA ROM pointer"
        )
        assert ptr != _EN_RITUAL_TEXT_PTR, (
            f"genuine relocated pointer 0x{off:07X} reverted to the EN text pointer "
            f"0x{_EN_RITUAL_TEXT_PTR:08X} -> the ritual line would show English"
        )
        targets.append(ptr)

    assert targets[0] == targets[1], (
        "the two genuine pointers must share one relocated FR string; got "
        f"0x{targets[0]:08X} and 0x{targets[1]:08X}"
    )

    fr_off = targets[0] - GBA_BASE
    fr_text = fr[fr_off : fr_off + 32]
    en_off = _EN_RITUAL_TEXT_PTR - GBA_BASE
    en_text = en[en_off : en_off + 32]
    assert fr_text[: fr_text.find(0xFF)] != en_text[: en_text.find(0xFF)], (
        f"relocated text at 0x{targets[0]:08X} equals the EN original "
        "('I swam, of course!') — not translated"
    )
    assert fr_text[:2] == _FR_RITUAL_TEXT_HEAD, (
        "relocated FR text should be \"J'ai nagé, bien sûr !\" (starts with \"J'\"); "
        f"got {fr_text[:8].hex()}"
    )
