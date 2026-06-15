"""E2E: Verify the battle foe-name suffix patch applied to the FR ROM.

The patch script (scripts/patch_battle_prefix_fr.py) turns the stock
prefix display into a French suffix display:
  - Trainer foe: "L'adversaire X" -> "X adverse"
  - Wild Pokémon: "sauvage X"      -> "X sauvage"

It does so by:
  - Emptying "L'adversaire " prefix at 0xA4C61A and 0xA4C64C
  - Emptying "sauvage" prefix at 0xA4C636
  - Installing two self-contained Thumb code caves at 0x1D89C / 0x1D908
  - Redirecting the two foe-name `B outer_loop` branches (0xD7BB4 / 0xD7C94)
    to those caves with a BL

Cave behaviour (verified by disassembly of the stock engine):
  1. copy the foe name from [r2] into the display buffer (r8 + r6),
  2. append the 8-byte suffix INLINE (no 0xFF terminator -> the rest of the
     message is preserved),
  3. write 0xFF to the engine name buffer at [sp] so the engine's own name
     copy becomes a no-op,
  4. jump to 0x080D82E4 (the convergence point) which runs the now-empty name
     copy, gender handling and continues expanding the message template.

These tests assert the cave bytes AND guard against the two historical
regressions:
  * a 0xFF terminator written into the *display* buffer (truncates the message)
  * `movs r6, #imm` (absolute destination index) / a top-of-cave `cmp ; bne`
    early-exit that prevented the suffix from ever being written.
"""

import struct

import pytest


ROM_PATH = "output/roms/GenedRom-fr.gba"

_ADVERSE_CFRU = bytes([0x00, 0xD5, 0xD8, 0xEA, 0xD9, 0xE6, 0xE7, 0xD9])  # " adverse"
_SAUVAGE_CFRU = bytes([0x00, 0xE7, 0xD5, 0xE9, 0xEA, 0xD5, 0xDB, 0xD9])  # " sauvage"

_CAVE_A_FILE = 0x1D89C
_CAVE_B_FILE = 0x1D908
_ROM_BASE    = 0x08000000
_CAVE_SIZE   = 108
_CONVERGE    = _ROM_BASE + 0xD82E4 + 1  # 0x080D82E5 (Thumb)

# Cave header: PUSH {r4,r5} + the name copy_loop, through the first STRB.
#   PUSH {r4, r5}      = 0xB430
#   LDRB r4, [r2, #0]  = 0x7814   <- copy_loop
#   CMP  r4, #0xFF     = 0x2CFF
#   BEQ  -> 0x14       = 0xD005   (write_suffix)
#   MOV  r5, r8        = 0x4645
#   ADDS r5, r5, r6    = 0x19AD
#   STRB r4, [r5, #0]  = 0x702C
#   ADDS r6, #1        = 0x3601
#   ADDS r2, #1        = 0x3201
#   B    -> copy_loop  = 0xE7F6
_CAVE_HEADER = bytes([
    0x30, 0xB4,   # PUSH {r4, r5}
    0x14, 0x78,   # LDRB r4, [r2, #0]
    0xFF, 0x2C,   # CMP  r4, #0xFF
    0x05, 0xD0,   # BEQ  -> write_suffix (cave+0x14)
    0x45, 0x46,   # MOV  r5, r8
    0xAD, 0x19,   # ADDS r5, r5, r6
    0x2C, 0x70,   # STRB r4, [r5, #0]
    0x01, 0x36,   # ADDS r6, #1
    0x01, 0x32,   # ADDS r2, #1
    0xF6, 0xE7,   # B    -> copy_loop (cave+0x02)
])


@pytest.fixture(scope="module")
def rom_data():
    import pathlib
    path = pathlib.Path(ROM_PATH)
    if not path.exists():
        pytest.skip(f"ROM not found: {ROM_PATH}")
    return path.read_bytes()


class TestBattleSuffixPatch:
    # ---- prefix emptying ---------------------------------------------------
    def test_ladversaire_space_prefix_emptied(self, rom_data):
        assert rom_data[0xA4C61A] == 0xFF, (
            f"Expected 0xFF at 0xA4C61A, got 0x{rom_data[0xA4C61A]:02X}"
        )

    def test_ladversaire_nospace_prefix_emptied(self, rom_data):
        assert rom_data[0xA4C64C] == 0xFF, (
            f"Expected 0xFF at 0xA4C64C, got 0x{rom_data[0xA4C64C]:02X}"
        )

    def test_sauvage_prefix_emptied(self, rom_data):
        assert rom_data[0xA4C636] == 0xFF, (
            f"Expected 0xFF at 0xA4C636, got 0x{rom_data[0xA4C636]:02X}"
        )

    # ---- cave structure ----------------------------------------------------
    def test_cave_a_header(self, rom_data):
        actual = rom_data[_CAVE_A_FILE: _CAVE_A_FILE + len(_CAVE_HEADER)]
        assert actual == _CAVE_HEADER, (
            f"Cave A header mismatch:\n  got {bytes(actual).hex(' ')}\n  exp {_CAVE_HEADER.hex(' ')}"
        )

    def test_cave_b_header(self, rom_data):
        actual = rom_data[_CAVE_B_FILE: _CAVE_B_FILE + len(_CAVE_HEADER)]
        assert actual == _CAVE_HEADER, (
            f"Cave B header mismatch:\n  got {bytes(actual).hex(' ')}\n  exp {_CAVE_HEADER.hex(' ')}"
        )

    def test_sauvage_bytes_in_cave_a(self, rom_data):
        """Cave A suffix block (cave+0x18..0x37) encodes CFRU ' sauvage'."""
        cave = rom_data[_CAVE_A_FILE: _CAVE_A_FILE + _CAVE_SIZE]
        found = bytes(cave[0x18 + i * 4] for i in range(8))
        assert found == _SAUVAGE_CFRU, (
            f"Cave A CFRU ' sauvage' mismatch: got {found.hex(' ')}"
        )

    def test_adverse_bytes_in_cave_b(self, rom_data):
        """Cave B suffix block (cave+0x18..0x37) encodes CFRU ' adverse'."""
        cave = rom_data[_CAVE_B_FILE: _CAVE_B_FILE + _CAVE_SIZE]
        found = bytes(cave[0x18 + i * 4] for i in range(8))
        assert found == _ADVERSE_CFRU, (
            f"Cave B CFRU ' adverse' mismatch: got {found.hex(' ')}"
        )

    @pytest.mark.parametrize("cave_file", [_CAVE_A_FILE, _CAVE_B_FILE])
    def test_cave_blank_engine_buffer_at_sp(self, rom_data, cave_file):
        """cave+0x3A = ADD r5, sp, #8, then MOVS r4,#0xFF / STRB r4,[r5].

        The 0xFF terminator is written to the engine's name buffer at [sp],
        NOT to the display buffer -- guards against the truncation regression.
        """
        assert struct.unpack_from("<H", rom_data, cave_file + 0x3A)[0] == 0xAD02, "ADD r5, sp, #8 missing"
        assert struct.unpack_from("<H", rom_data, cave_file + 0x3C)[0] == 0x24FF, "MOVS r4, #0xFF missing"
        assert struct.unpack_from("<H", rom_data, cave_file + 0x3E)[0] == 0x702C, "STRB r4, [r5] missing"

    @pytest.mark.parametrize("cave_file", [_CAVE_A_FILE, _CAVE_B_FILE])
    def test_cave_jumps_to_convergence_point(self, rom_data, cave_file):
        """cave epilogue: BX r3 with literal = 0x080D82E5 (convergence point)."""
        assert struct.unpack_from("<H", rom_data, cave_file + 0x44)[0] == 0x4718, "BX r3 missing"
        lit = struct.unpack_from("<I", rom_data, cave_file + 0x48)[0]
        assert lit == _CONVERGE, f"convergence literal: 0x{lit:08X} (expected 0x{_CONVERGE:08X})"

    # ---- regression guards -------------------------------------------------
    @pytest.mark.parametrize("cave_file", [_CAVE_A_FILE, _CAVE_B_FILE])
    def test_cave_has_no_absolute_r6_index(self, rom_data, cave_file):
        """`movs r6, #imm` (0x26xx) corrupts the display index -- must not appear.

        r6 is only ever updated via ADDS (0x3601 / 0x3608) in the correct cave.
        """
        cave = rom_data[cave_file: cave_file + 0x48]  # code region, exclude literal
        for off in range(0, len(cave) - 1, 2):
            hw = struct.unpack_from("<H", cave, off)[0]
            assert (hw & 0xFF00) != 0x2600, (
                f"forbidden MOVS r6,#imm (0x{hw:04X}) at cave+0x{off:X}"
            )

    @pytest.mark.parametrize("cave_file", [_CAVE_A_FILE, _CAVE_B_FILE])
    def test_cave_no_early_exit_on_nonempty_name(self, rom_data, cave_file):
        """The cave must NOT begin with `cmp r5,#0xFF; bne` (the never-fires bug).

        The first compare in the correct cave is `cmp r4,#0xFF; beq` belonging to
        the name copy loop, at cave+0x04/0x06.
        """
        # cave+0x04 must be CMP r4,#0xFF (0x2CFF), cave+0x06 must be BEQ (0xD0xx),
        # never CMP r5,#0xFF (0x2DFF) / BNE (0xD1xx).
        assert struct.unpack_from("<H", rom_data, cave_file + 0x04)[0] == 0x2CFF
        beq = struct.unpack_from("<H", rom_data, cave_file + 0x06)[0]
        assert (beq & 0xFF00) == 0xD000, f"expected BEQ at cave+0x06, got 0x{beq:04X}"

    # ---- branch redirection ------------------------------------------------
    @pytest.mark.parametrize("site,expected_cave", [
        (0xD7BB4, _CAVE_A_FILE),  # wild foe name
        (0xD7C94, _CAVE_B_FILE),  # trainer foe name
    ])
    def test_bl_patch_targets_cave(self, rom_data, site, expected_cave):
        h1, h2 = struct.unpack_from("<HH", rom_data, site)
        assert (h1 >> 11) == 0x1E, f"0x{site:X}: h1=0x{h1:04X} not BL"
        assert (h2 >> 11) == 0x1F, f"0x{site:X}: h2=0x{h2:04X} not BL suffix"
        off = ((h1 & 0x7FF) << 12) | ((h2 & 0x7FF) << 1)
        if off >= (1 << 22):
            off -= (1 << 23)
        target = site + 4 + off
        assert target == expected_cave, (
            f"0x{site:X}: BL -> 0x{target:X}, expected 0x{expected_cave:X}"
        )
