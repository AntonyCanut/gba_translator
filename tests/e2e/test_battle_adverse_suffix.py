"""E2E: Verify "X adverse" battle-prefix patch is applied to the FR ROM.

The patch script (scripts/patch_battle_prefix_fr.py) transforms the trainer-foe
display from "L'adversaire X" to "X adverse" by:
  - Emptying the "L'adversaire " prefix at ROM offset 0xA4C61A
  - Emptying the no-space form at 0xA4C64C
  - Installing two 72-byte Thumb code caves at 0x1D89C / 0x1D8E4
  - Replacing six "B outer_loop" instructions with BL to the appropriate cave

These tests read the built+patched ROM and assert the expected bytes are present.
"""

import struct

import pytest


ROM_PATH = "output/roms/GenedRom-fr.gba"

# Cave signatures: first 16 bytes of each cave
# PUSH {r3,r4,r5} / LDR r3,[PC,#60] / LDR r3,[r3] / MOVS r4,#8 / TST r3,r4 / BEQ
_CAVE_HEADER = bytes([
    0x38, 0xB4,          # PUSH {r3, r4, r5}
    0x0F, 0x4B,          # LDR r3, [PC, #60]   → gBattleTypeFlags addr
    0x1B, 0x68,          # LDR r3, [r3]
    0x08, 0x24,          # MOVS r4, #8
    0x23, 0x42,          # TST r3, r4
    0x16, 0xD0,          # BEQ (skip if not trainer)
    0x15, 0x78,          # LDRB r5, [r2, #0]
    0xFF, 0x2D,          # CMP r5, #0xFF
])

_GBAFLAGS = 0x02022B4C
_CAVE_A_FILE = 0x1D89C
_CAVE_B_FILE = 0x1D8E4
_ROM_BASE    = 0x08000000


@pytest.fixture(scope="module")
def rom_data():
    import pathlib
    path = pathlib.Path(ROM_PATH)
    if not path.exists():
        pytest.skip(f"ROM not found: {ROM_PATH}")
    return path.read_bytes()


class TestBattleAdversePatch:
    def test_ladversaire_space_prefix_emptied(self, rom_data):
        """0xA4C61A first byte must be 0xFF (prefix is empty)."""
        assert rom_data[0xA4C61A] == 0xFF, (
            f"Expected 0xFF at 0xA4C61A, got 0x{rom_data[0xA4C61A]:02X}"
        )

    def test_ladversaire_nospace_prefix_emptied(self, rom_data):
        """0xA4C64C first byte must be 0xFF (no-space prefix form emptied)."""
        assert rom_data[0xA4C64C] == 0xFF, (
            f"Expected 0xFF at 0xA4C64C, got 0x{rom_data[0xA4C64C]:02X}"
        )

    def test_sauvage_prefix_untouched(self, rom_data):
        """0xA4C636 must still start with 's' (0xE7) — wild prefix must be intact."""
        assert rom_data[0xA4C636] == 0xE7, (
            f"Expected 0xE7 ('s') at 0xA4C636, got 0x{rom_data[0xA4C636]:02X}"
        )

    def test_cave_a_header(self, rom_data):
        """Cave A at 0x1D89C must start with the expected Thumb instructions."""
        actual = rom_data[_CAVE_A_FILE: _CAVE_A_FILE + len(_CAVE_HEADER)]
        assert actual == _CAVE_HEADER, (
            f"Cave A header mismatch:\n  got {actual.hex(' ')}\n  exp {_CAVE_HEADER.hex(' ')}"
        )

    def test_cave_a_literal_pool(self, rom_data):
        """Cave A literal pool must hold the correct GBA addresses."""
        flags = struct.unpack_from("<I", rom_data, _CAVE_A_FILE + 0x40)[0]
        loop  = struct.unpack_from("<I", rom_data, _CAVE_A_FILE + 0x44)[0]
        assert flags == _GBAFLAGS, f"Cave A flags addr: 0x{flags:08X}"
        assert loop == _ROM_BASE + 0xD82AA + 1, f"Cave A loop addr: 0x{loop:08X}"

    def test_cave_b_header(self, rom_data):
        """Cave B at 0x1D8E4 must start with the expected Thumb instructions."""
        actual = rom_data[_CAVE_B_FILE: _CAVE_B_FILE + len(_CAVE_HEADER)]
        assert actual == _CAVE_HEADER, (
            f"Cave B header mismatch:\n  got {actual.hex(' ')}\n  exp {_CAVE_HEADER.hex(' ')}"
        )

    def test_cave_b_literal_pool(self, rom_data):
        """Cave B literal pool must target 0xD82A4 (different outer-loop entry)."""
        flags = struct.unpack_from("<I", rom_data, _CAVE_B_FILE + 0x40)[0]
        loop  = struct.unpack_from("<I", rom_data, _CAVE_B_FILE + 0x44)[0]
        assert flags == _GBAFLAGS, f"Cave B flags addr: 0x{flags:08X}"
        assert loop == _ROM_BASE + 0xD82A4 + 1, f"Cave B loop addr: 0x{loop:08X}"

    @pytest.mark.parametrize("site,expected_cave", [
        (0xD7BB4, _CAVE_A_FILE),
        (0xD7C94, _CAVE_B_FILE),
        (0xD7D08, _CAVE_B_FILE),
        (0xD7D7C, _CAVE_B_FILE),
        (0xD7DF0, _CAVE_B_FILE),
        (0xD7E64, _CAVE_B_FILE),
    ])
    def test_bl_patch_targets_cave(self, rom_data, site, expected_cave):
        """Each patched site must be a BL instruction pointing to the right cave."""
        h1, h2 = struct.unpack_from("<HH", rom_data, site)
        assert (h1 >> 11) == 0x1E, f"0x{site:X}: h1=0x{h1:04X} is not BL (bits[15:11] must be 11110)"
        assert (h2 >> 11) == 0x1F, f"0x{site:X}: h2=0x{h2:04X} is not BL suffix"
        imm_hi = h1 & 0x7FF
        imm_lo = h2 & 0x7FF
        off = (imm_hi << 12) | (imm_lo << 1)
        if off >= (1 << 22):
            off -= (1 << 23)
        target = site + 4 + off
        assert target == expected_cave, (
            f"0x{site:X}: BL → 0x{target:X}, expected 0x{expected_cave:X}"
        )

    def test_adverse_bytes_in_cave(self, rom_data):
        """Cave A must contain the CFRU encoding of ' adverse' in its write sequence."""
        # " adverse" in CFRU: 00=space D5=a D8=d EA=v D9=e E6=r E7=s D9=e
        adverse_cfru = bytes([0x00, 0xD5, 0xD8, 0xEA, 0xD9, 0xE6, 0xE7, 0xD9])
        cave_bytes = rom_data[_CAVE_A_FILE: _CAVE_A_FILE + 72]
        # The bytes are interspersed with MOVS opcodes every 4 bytes; check each
        write_area = cave_bytes[0x16:0x36]   # 32 bytes: 8 × (MOVS r4,#x + STRB)
        found = [write_area[i * 4] for i in range(8)]   # byte 0 of each MOVS halfword (stored XX 24 little-endian)
        assert bytes(found) == adverse_cfru, (
            f"CFRU ' adverse' mismatch: got {bytes(found).hex(' ')}"
        )
