"""Unit tests for the language-agnostic inter-cell collision detector."""

import struct

from src.core.collision_check import (
    ROM_BASE,
    Collision,
    build_pointer_index,
    find_collisions,
    has_live_pointer,
    live_target,
    plausible_sites,
)


def _ptr(offset: int) -> bytes:
    return struct.pack('<I', ROM_BASE + offset)


def _blank(size: int = 0x400) -> bytearray:
    # 0x00 is a benign non-terminator filler for these byte-level tests
    # (the pokemon terminator is 0xFF), so a blank ROM has no terminators.
    return bytearray(size)


# ── build_pointer_index / plausibility ──────────────────────────────────────

def test_build_pointer_index_finds_aligned_and_unaligned():
    rom = _blank()
    rom[0x200:0x204] = _ptr(0x100)   # aligned site
    rom[0x211:0x215] = _ptr(0x100)   # unaligned site (0x211 % 4 != 0)
    index = build_pointer_index(bytes(rom))
    assert set(index[0x100]) == {0x200, 0x211}


def test_plausible_sites_keeps_aligned_rejects_random_code_word():
    rom = _blank()
    rom[0x200:0x204] = _ptr(0x100)   # aligned → plausible
    rom[0x211:0x215] = _ptr(0x100)   # unaligned, no opcode before → rejected
    index = build_pointer_index(bytes(rom))
    kept = plausible_sites(bytes(rom), 0x100, index[0x100])
    assert kept == [0x200]


def test_plausible_sites_accepts_script_opcode_prefixed():
    rom = _blank()
    rom[0x210] = 0x67                # preparemsg opcode immediately before
    rom[0x211:0x215] = _ptr(0x100)   # unaligned but opcode-prefixed → plausible
    index = build_pointer_index(bytes(rom))
    assert plausible_sites(bytes(rom), 0x100, index[0x100]) == [0x211]


def test_has_live_pointer_phantom_vs_live():
    rom = _blank()
    rom[0x200:0x204] = _ptr(0x100)          # 0x100 is addressed (aligned)
    rom[0x305:0x309] = _ptr(0x140)          # 0x140 only via an unaligned code word
    index = build_pointer_index(bytes(rom))
    assert has_live_pointer(index, 0x100, en_rom=bytes(rom))
    assert not has_live_pointer(index, 0x140, en_rom=bytes(rom))   # phantom
    assert not has_live_pointer(index, 0x180, en_rom=bytes(rom))   # absent entirely


def test_live_target_reads_current_pointer():
    rom = _blank()
    rom[0x200:0x204] = _ptr(0x3A0)
    assert live_target(bytes(rom), 0x200) == 0x3A0
    assert live_target(bytes(rom), 0x3FE) is None  # off the end


# ── find_collisions ─────────────────────────────────────────────────────────

def test_no_collision_when_terminated_before_next():
    rom = _blank()
    rom[0x108] = 0xFF                       # cell 0x100 terminates before 0x140
    rom[0x148] = 0xFF                       # cell 0x140 terminates before 0x180
    collisions = find_collisions(bytes(rom), [0x100, 0x140, 0x180])
    assert collisions == []


def test_collision_when_string_overruns_next_cell():
    rom = _blank()
    # 0x100 has NO 0xFF anywhere before 0x140 → it runs into the neighbour.
    rom[0x148] = 0xFF
    collisions = find_collisions(bytes(rom), [0x100, 0x140, 0x180])
    assert len(collisions) == 1
    assert collisions[0].offset == 0x100
    assert collisions[0].next_offset == 0x140


def test_relocated_cell_not_flagged_even_if_unterminated_in_place():
    rom = _blank()
    # cell 0x100 addressed by an aligned pointer that now targets free space.
    en = _blank()
    en[0x200:0x204] = _ptr(0x100)
    index = build_pointer_index(bytes(en))
    built = _blank()
    built[0x200:0x204] = _ptr(0x3A0)       # relocated: pointer no longer → 0x100
    # in-place bytes at 0x100 are unterminated, but they are dead now.
    collisions = find_collisions(
        bytes(built), [0x100, 0x140], en_index=index, en_rom=bytes(en)
    )
    assert collisions == []


def test_in_place_live_cell_flagged_when_unterminated():
    rom = _blank()
    en = _blank()
    en[0x200:0x204] = _ptr(0x100)
    index = build_pointer_index(bytes(en))
    built = _blank()
    built[0x200:0x204] = _ptr(0x100)       # still points in place
    # no 0xFF before 0x140 → collision
    collisions = find_collisions(
        bytes(built), [0x100, 0x140], en_index=index, en_rom=bytes(en)
    )
    assert len(collisions) == 1
    assert collisions[0].kind == 'in_place'


def test_phantom_overrun_flagged_with_phantom_kind():
    en = _blank()
    en[0x200:0x204] = _ptr(0x100)          # only 0x100 is addressed
    index = build_pointer_index(bytes(en))
    built = _blank()
    built[0x200:0x204] = _ptr(0x100)
    built[0x108] = 0xFF                     # 0x100 is terminated (safe)
    # 0x140 is a phantom (no pointer) and unterminated before 0x180 → flagged.
    collisions = find_collisions(
        bytes(built), [0x100, 0x140, 0x180], en_index=index, en_rom=bytes(en)
    )
    assert [c.kind for c in collisions] == ['phantom']
    assert collisions[0].offset == 0x140


def test_source_terminator_gate_drops_fragment_false_positives():
    # Build overruns at both 0x100 and 0x140, but the SOURCE only had a real
    # boundary (0xFF) inside the 0x100→0x140 gap. 0x140→0x180 was already one
    # long unterminated string in source (an interior fragment) → not a defect.
    source = _blank()
    source[0x120] = 0xFF                    # real boundary in source for 0x100
    # no 0xFF between 0x140 and 0x180 in source → fragment
    built = _blank()                        # build has no 0xFF anywhere
    collisions = find_collisions(
        bytes(built), [0x100, 0x140, 0x180], source_rom=bytes(source)
    )
    assert [c.offset for c in collisions] == [0x100]
    assert collisions[0].extra['source_had_terminator'] is True


def test_empty_source_cell_is_free_space_not_a_collision():
    # 0x100 is EMPTY in the source (its first byte is already the terminator):
    # unused free space the generic builder's relocator may reuse. A built
    # string that spans it is free-space reuse, not a destroyed cell boundary,
    # so it must not be flagged — while a real (non-empty) overrunning cell at
    # 0x140 still is.
    source = _blank()
    source[0x100] = 0xFF                    # empty source cell → free space
    source[0x160] = 0xFF                    # real boundary in 0x140→0x180 gap
    built = _blank()                        # build has no 0xFF anywhere
    collisions = find_collisions(
        bytes(built), [0x100, 0x140, 0x180], source_rom=bytes(source)
    )
    offsets = [c.offset for c in collisions]
    assert 0x100 not in offsets            # empty source → skipped
    assert 0x140 in offsets                # real cell overrun → still flagged


def test_next_is_live_flags_real_neighbour_vs_fragment():
    en = _blank()
    en[0x200:0x204] = _ptr(0x100)          # 0x100 addressed (the overrunning cell)
    en[0x204:0x208] = _ptr(0x140)          # 0x140 addressed → real neighbour
    # 0x180 is NOT addressed → an interior fragment
    index = build_pointer_index(bytes(en))
    built = _blank()
    built[0x200:0x204] = _ptr(0x100)
    built[0x204:0x208] = _ptr(0x140)
    # 0x100 overruns 0x140 (live) ; 0x140 overruns 0x180 (fragment)
    collisions = find_collisions(
        bytes(built), [0x100, 0x140, 0x180], en_index=index, en_rom=bytes(en)
    )
    by_off = {c.offset: c for c in collisions}
    assert by_off[0x100].extra['next_is_live'] is True    # high confidence
    assert by_off[0x140].extra['next_is_live'] is False   # low confidence


def test_region_restricts_audit():
    rom = _blank()
    # both cells overrun, but only the in-region one is reported
    collisions = find_collisions(
        bytes(rom), [0x100, 0x140, 0x900, 0x940], region=(0x900, 0xA00)
    )
    assert [c.offset for c in collisions] == [0x900]


def test_collision_as_dict_is_serializable():
    c = Collision(offset=0x920000, next_offset=0x920040, kind='in_place',
                  decoded='foo', extra={'gap_bytes': 0x40})
    d = c.as_dict()
    assert d['offset'] == '0x920000'
    assert d['next_offset'] == '0x920040'
    assert d['gap_bytes'] == 0x40
