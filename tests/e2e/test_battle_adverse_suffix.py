"""E2E: Verify battle-prefix patch applied to the FR ROM.

The patch script (scripts/patch_battle_prefix_fr.py) transforms:
  - Trainer foe: "L'adversaire X" → "X adverse"
  - Wild Pokémon: "sauvage X"     → "X sauvage"

It does so by:
  - Emptying "L'adversaire " prefix at 0xA4C61A and 0xA4C64C
  - Emptying "sauvage" prefix at 0xA4C636
  - Installing two 108-byte Thumb code caves at 0x1D89C / 0x1D908
  - Replacing the two relevant "B outer_loop" instructions with BL to the cave

Cave A (wild,    0x1D89C): copies nickname from [r2] + " sauvage" + 0xFF
Cave B (trainer, 0x1D908): copies nickname from [r2] + " adverse" + 0xFF

Cave B2-B5 sites (0xD7D08/7C/F0/E64) are NOT patched; their output lands
after our 0xFF terminator and is invisible to the text renderer.
"""

import struct

import pytest


ROM_PATH = "output/roms/GenedRom-fr.gba"

# Cave header: first 16 bytes (PUSH through first STRB in copy_loop)
#   PUSH {r2, r4, r5}  = 0xB434
#   LDRB r4, [r2, #0]  = 0x7814  ← copy_loop
#   CMP  r4, #0xFF     = 0x2CFF
#   BEQ  → 0x14        = 0xD005
#   MOV  r5, r8        = 0x4645
#   ADDS r5, r5, r6    = 0x19AD
#   STRB r4, [r5, #0]  = 0x702C
#   ADDS r6, #1        = 0x3601
_CAVE_HEADER = bytes([
    0x34, 0xB4,   # PUSH {r2, r4, r5}
    0x14, 0x78,   # LDRB r4, [r2, #0]
    0xFF, 0x2C,   # CMP  r4, #0xFF
    0x05, 0xD0,   # BEQ  → write_suffix (cave+0x14)
    0x45, 0x46,   # MOV  r5, r8
    0xAD, 0x19,   # ADDS r5, r5, r6
    0x2C, 0x70,   # STRB r4, [r5, #0]
    0x01, 0x36,   # ADDS r6, #1
])

_ADVERSE_CFRU = bytes([0x00, 0xD5, 0xD8, 0xEA, 0xD9, 0xE6, 0xE7, 0xD9])  # " adverse"
_SAUVAGE_CFRU = bytes([0x00, 0xE7, 0xD5, 0xE9, 0xEA, 0xD5, 0xDB, 0xD9])  # " sauvage"

_CAVE_A_FILE = 0x1D89C
_CAVE_B_FILE = 0x1D908
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

    def test_cave_b_header(self, rom_data):
        """Cave B at 0x1D908 must start with the same Thumb header as Cave A."""
        actual = rom_data[_CAVE_B_FILE: _CAVE_B_FILE + len(_CAVE_HEADER)]
        assert actual == _CAVE_HEADER, (
            f"Cave B header mismatch:\n  got {bytes(actual).hex(' ')}\n  exp {_CAVE_HEADER.hex(' ')}"
        )

    def test_cave_a_beq_target(self, rom_data):
        """BEQ at cave A+0x06 must encode jump to write_suffix at cave+0x14."""
        hw = struct.unpack_from("<H", rom_data, _CAVE_A_FILE + 0x06)[0]
        assert hw == 0xD005, f"BEQ halfword: 0x{hw:04X} (expected 0xD005)"

    def test_cave_a_backward_branch(self, rom_data):
        """B at cave A+0x12 must jump back to copy_loop at cave+0x02."""
        hw = struct.unpack_from("<H", rom_data, _CAVE_A_FILE + 0x12)[0]
        assert hw == 0xE7F6, f"B-backward halfword: 0x{hw:04X} (expected 0xE7F6)"

    def test_cave_a_terminator_movs(self, rom_data):
        """MOVS r4, #0xFF at cave A+0x3E writes the string terminator."""
        hw = struct.unpack_from("<H", rom_data, _CAVE_A_FILE + 0x3E)[0]
        assert hw == 0x24FF, f"MOVS #0xFF halfword: 0x{hw:04X} (expected 0x24FF)"

    def test_cave_a_literal_pool(self, rom_data):
        """Cave A literal at cave+0x4C must be the outer_loop_A GBA Thumb address."""
        loop = struct.unpack_from("<I", rom_data, _CAVE_A_FILE + 0x4C)[0]
        assert loop == _ROM_BASE + 0xD82AA + 1, f"Cave A loop addr: 0x{loop:08X}"

    def test_cave_b_literal_pool(self, rom_data):
        """Cave B literal at cave+0x4C must be the outer_loop_B GBA Thumb address."""
        loop = struct.unpack_from("<I", rom_data, _CAVE_B_FILE + 0x4C)[0]
        assert loop == _ROM_BASE + 0xD82A4 + 1, f"Cave B loop addr: 0x{loop:08X}"

    @pytest.mark.parametrize("site,expected_cave", [
        (0xD7BB4, _CAVE_A_FILE),  # token 0x0E — wild name
        (0xD7C94, _CAVE_B_FILE),  # token 0x10 — trainer name
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

    def test_cave_b25_sites_not_bl(self, rom_data):
        """Cave B2-B5 sites must NOT be BL (original B outer_loop retained)."""
        for site in (0xD7D08, 0xD7D7C, 0xD7DF0, 0xD7E64):
            h1 = struct.unpack_from("<H", rom_data, site)[0]
            assert (h1 >> 11) != 0x1E, (
                f"0x{site:X}: unexpected BL at h1=0x{h1:04X} — should be original B outer_loop"
            )

    def test_sauvage_bytes_in_cave_a(self, rom_data):
        """Cave A suffix block (cave+0x18..0x37) must encode CFRU ' sauvage' bytes."""
        cave_bytes = rom_data[_CAVE_A_FILE: _CAVE_A_FILE + _CAVE_SIZE]
        # 8 pairs of (MOVS r4, #byte; STRB); MOVS byte is at offset 0 of each 4-byte pair
        found = bytes(cave_bytes[0x18 + i * 4] for i in range(8))
        assert found == _SAUVAGE_CFRU, (
            f"Cave A CFRU ' sauvage' mismatch: got {found.hex(' ')}"
        )

    def test_adverse_bytes_in_cave_b(self, rom_data):
        """Cave B suffix block (cave+0x18..0x37) must encode CFRU ' adverse' bytes."""
        cave_bytes = rom_data[_CAVE_B_FILE: _CAVE_B_FILE + _CAVE_SIZE]
        found = bytes(cave_bytes[0x18 + i * 4] for i in range(8))
        assert found == _ADVERSE_CFRU, (
            f"Cave B CFRU ' adverse' mismatch: got {found.hex(' ')}"
        )
