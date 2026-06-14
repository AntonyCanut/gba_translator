"""E2E: Verify battle-prefix patch applied to the FR ROM.

The patch script (scripts/patch_battle_prefix_fr.py) transforms:
  - Trainer foe: "L'adversaire X" → "X adverse"
  - Wild Pokémon: "sauvage X"     → "X sauvage"

It does so by:
  - Emptying "L'adversaire " prefix at 0xA4C61A and 0xA4C64C
  - Emptying "sauvage" prefix at 0xA4C636
  - Installing two 108-byte Thumb code caves at 0x1D89C / 0x1D908
  - Replacing six "B outer_loop" instructions with BL to the appropriate cave

Each cave checks the last nickname char (0xFF) then the trainer bit to decide
which 8-byte suffix to append: " adverse" (trainer) or " sauvage" (wild).

These tests read the built+patched ROM and assert the expected bytes are present.
"""

import struct

import pytest


ROM_PATH = "output/roms/GenedRom-fr.gba"

# New 108-byte cave header: first 16 bytes
# PUSH / LDR flags / LDR [r3] / MOVS r4,#8 / LDRB r5 / CMP r5,#FF / BNE skip / MOV r5,r8
_CAVE_HEADER = bytes([
    0x38, 0xB4,   # PUSH {r3, r4, r5}
    0x18, 0x4B,   # LDR r3, [PC, #0x60]  → gBattleTypeFlags addr
    0x1B, 0x68,   # LDR r3, [r3]
    0x08, 0x24,   # MOVS r4, #8
    0x15, 0x78,   # LDRB r5, [r2, #0]   (next nickname char)
    0xFF, 0x2D,   # CMP r5, #0xFF
    0x27, 0xD1,   # BNE +0x4E (skip: not last char)
    0x45, 0x46,   # MOV r5, r8
])

_ADVERSE_CFRU = bytes([0x00, 0xD5, 0xD8, 0xEA, 0xD9, 0xE6, 0xE7, 0xD9])  # " adverse"
_SAUVAGE_CFRU = bytes([0x00, 0xE7, 0xD5, 0xE9, 0xEA, 0xD5, 0xDB, 0xD9])  # " sauvage"

_GBAFLAGS    = 0x02022B4C
_CAVE_A_FILE = 0x1D89C
_CAVE_B_FILE = 0x1D908   # moved: Cave A is now 108 bytes (was 72)
_ROM_BASE    = 0x08000000
_CAVE_SIZE   = 108


@pytest.fixture(scope="module")
def rom_data():
    import pathlib
    path = pathlib.Path(ROM_PATH)
    if not path.exists():
        pytest.skip(f"ROM not found: {ROM_PATH}")
    return path.read_bytes()


class TestBattlePrefixPatch:
    def test_ladversaire_space_prefix_emptied(self, rom_data):
        """0xA4C61A first byte must be 0xFF (trainer-foe space-prefix emptied)."""
        assert rom_data[0xA4C61A] == 0xFF, (
            f"Expected 0xFF at 0xA4C61A, got 0x{rom_data[0xA4C61A]:02X}"
        )

    def test_ladversaire_nospace_prefix_emptied(self, rom_data):
        """0xA4C64C first byte must be 0xFF (trainer-foe no-space prefix emptied)."""
        assert rom_data[0xA4C64C] == 0xFF, (
            f"Expected 0xFF at 0xA4C64C, got 0x{rom_data[0xA4C64C]:02X}"
        )

    def test_sauvage_prefix_emptied(self, rom_data):
        """0xA4C636 first byte must be 0xFF (wild prefix emptied; suffix written by cave)."""
        assert rom_data[0xA4C636] == 0xFF, (
            f"Expected 0xFF at 0xA4C636, got 0x{rom_data[0xA4C636]:02X}"
        )

    def test_cave_a_header(self, rom_data):
        """Cave A at 0x1D89C must start with the expected Thumb instructions."""
        actual = rom_data[_CAVE_A_FILE: _CAVE_A_FILE + len(_CAVE_HEADER)]
        assert actual == _CAVE_HEADER, (
            f"Cave A header mismatch:\n  got {bytes(actual).hex(' ')}\n  exp {_CAVE_HEADER.hex(' ')}"
        )

    def test_cave_a_literal_pool(self, rom_data):
        """Cave A literal pool (at cave+0x64/0x68) must hold the correct GBA addresses."""
        flags = struct.unpack_from("<I", rom_data, _CAVE_A_FILE + 0x64)[0]
        loop  = struct.unpack_from("<I", rom_data, _CAVE_A_FILE + 0x68)[0]
        assert flags == _GBAFLAGS, f"Cave A flags addr: 0x{flags:08X}"
        assert loop == _ROM_BASE + 0xD82AA + 1, f"Cave A loop addr: 0x{loop:08X}"

    def test_cave_b_header(self, rom_data):
        """Cave B at 0x1D908 must start with the expected Thumb instructions."""
        actual = rom_data[_CAVE_B_FILE: _CAVE_B_FILE + len(_CAVE_HEADER)]
        assert actual == _CAVE_HEADER, (
            f"Cave B header mismatch:\n  got {bytes(actual).hex(' ')}\n  exp {_CAVE_HEADER.hex(' ')}"
        )

    def test_cave_b_literal_pool(self, rom_data):
        """Cave B literal pool must target 0xD82A4 (different outer-loop entry)."""
        flags = struct.unpack_from("<I", rom_data, _CAVE_B_FILE + 0x64)[0]
        loop  = struct.unpack_from("<I", rom_data, _CAVE_B_FILE + 0x68)[0]
        assert flags == _GBAFLAGS, f"Cave B flags addr: 0x{flags:08X}"
        assert loop == _ROM_BASE + 0xD82A4 + 1, f"Cave B loop addr: 0x{loop:08X}"

    def test_cave_a_bne_skip_target(self, rom_data):
        """BNE at cave+0x0C must jump to cave+0x5E (LDR/BX, bypassing POP)."""
        hw = struct.unpack_from("<H", rom_data, _CAVE_A_FILE + 0x0C)[0]
        assert hw == 0xD127, f"BNE halfword: 0x{hw:04X} (expected 0xD127)"

    def test_cave_a_beq_wild_target(self, rom_data):
        """BEQ at cave+0x14 must jump to cave+0x3A (wild write block)."""
        hw = struct.unpack_from("<H", rom_data, _CAVE_A_FILE + 0x14)[0]
        assert hw == 0xD011, f"BEQ halfword: 0x{hw:04X} (expected 0xD011)"

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
        assert (h1 >> 11) == 0x1E, f"0x{site:X}: h1=0x{h1:04X} not BL (bits[15:11] must be 11110)"
        assert (h2 >> 11) == 0x1F, f"0x{site:X}: h2=0x{h2:04X} not BL suffix"
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
        """Cave A write block (cave+0x16..0x35) must encode CFRU ' adverse' bytes."""
        cave_bytes = rom_data[_CAVE_A_FILE: _CAVE_A_FILE + _CAVE_SIZE]
        write_area = cave_bytes[0x16:0x36]   # 32 bytes: 8 × (MOVS r4,#x + STRB)
        found = bytes(write_area[i * 4] for i in range(8))
        assert found == _ADVERSE_CFRU, (
            f"CFRU ' adverse' mismatch: got {found.hex(' ')}"
        )

    def test_sauvage_bytes_in_cave(self, rom_data):
        """Cave A write block (cave+0x3A..0x59) must encode CFRU ' sauvage' bytes."""
        cave_bytes = rom_data[_CAVE_A_FILE: _CAVE_A_FILE + _CAVE_SIZE]
        write_area = cave_bytes[0x3A:0x5A]   # 32 bytes: 8 × (MOVS r4,#x + STRB)
        found = bytes(write_area[i * 4] for i in range(8))
        assert found == _SAUVAGE_CFRU, (
            f"CFRU ' sauvage' mismatch: got {found.hex(' ')}"
        )
