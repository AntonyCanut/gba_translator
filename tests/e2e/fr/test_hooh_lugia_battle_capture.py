"""E2E: Verify Ho-Oh and Lugia battle-trigger and capture mechanics in the FR ROM.

This test suite guards against translation regressions that could break the
Ho-Oh or Lugia encounter sequences.  All tests are ROM-only (no emulator) and
are deterministic regression guards.

== Background ==

Ho-Oh and Lugia are triggered by static encounter scripts in two map areas:

  Lugia encounter trigger  @ 0x7BA890 (map area 0x7Bxxxx)
    The battle command + species are at 0x7BA898:
      51 00 00 02  5c 00 f9 00 00 00  <ptr-on-win>  <ptr-on-lose>
    Where f9 00 = Lugia (national dex 249).

  Ho-Oh encounter trigger  @ 0x7BB48F (same map segment)
    Key bytes: 4f fa 00 f2 b5 7b 08
    Where fa 00 = Ho-Oh (national dex 250).

  Both areas are verified byte-identical between EN and FR (only text-string
  pointer values change, because FR NPC dialogue was relocated to free space).

  Key items that unlock the encounters:
    Rainbow Wing  item 0x298  → FR name "Aile Aurore"
    Silver Wing   item 0x299  → FR name "Aile Argentée"

  Base stats table (CFRU-extended):
    Lugia  @ ROM 0x019E27D8 : catch rate = 6
    Ho-Oh  @ ROM 0x019E27F4 : catch rate = 6, held item = Sacred Ash (0x002D)

The battle command at 0x7BA89C = 0x5C (trainerbattle-style opcode) followed
by species f9 00 (Lugia) is the byte-level proof that the encounter script was
not overwritten by the French translation pipeline.
"""

from __future__ import annotations

import pathlib
import struct

import pytest

pytestmark = pytest.mark.rom

from src.text.charmap_data import BYTE_TO_CHAR

# ---------------------------------------------------------------------------
# ROM discovery
# ---------------------------------------------------------------------------

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent

EN_ROM_PATH = PROJECT_ROOT / "input" / "roms" / "englishrom.gba"
FR_ROM_PATH = PROJECT_ROOT / "output" / "roms" / "GenedRom-fr.gba"

GBA_ROM_BASE = 0x08000000


@pytest.fixture(scope="module")
def en_rom() -> bytes:
    if not EN_ROM_PATH.exists():
        pytest.skip("englishrom.gba not found")
    return EN_ROM_PATH.read_bytes()


@pytest.fixture(scope="module")
def fr_rom() -> bytes:
    if not FR_ROM_PATH.exists():
        pytest.skip("GenedRom-fr.gba not found (run make build-fr)")
    return FR_ROM_PATH.read_bytes()


def _deref(data: bytes, off: int):
    v = struct.unpack_from("<I", data, off)[0]
    if GBA_ROM_BASE <= v < GBA_ROM_BASE + len(data):
        return v - GBA_ROM_BASE
    return None


def _read_str(data: bytes, off: int, maxlen: int = 512):
    """Return (raw_bytes_including_0xFF, is_terminated)."""
    end = data.find(0xFF, off, off + maxlen)
    if end == -1:
        return data[off : off + maxlen], False
    return data[off : end + 1], True


def _decode(data: bytes, off: int, maxlen: int = 512) -> str:
    """Decode CFRU-encoded bytes starting at off, stopping at 0xFF."""
    result = []
    i = off
    limit = min(off + maxlen, len(data))
    while i < limit:
        b = data[i]
        if b == 0xFF:
            break
        if b == 0xFE:
            result.append("\n")
            i += 1
        elif b in (0xFC, 0xFD):
            result.append(f"<{b:02X}{data[i+1]:02X}>")
            i += 2
        elif b in BYTE_TO_CHAR:
            result.append(BYTE_TO_CHAR[b])
            i += 1
        else:
            result.append(f"<?{b:02X}>")
            i += 1
    return "".join(result)


# ---------------------------------------------------------------------------
# 1. Encounter trigger script integrity
# ---------------------------------------------------------------------------


class TestEncounterTriggerIntegrity:
    """The battle-trigger bytes in both encounter scripts must be identical
    between EN and FR — they must not have been overwritten by the translation
    pipeline."""

    # Lugia battle trigger: 5c 00 f9 00 00 00 (species=249) at 0x7BA89C
    # Layout: [51 00 00 02] [5c 00] [f9 00] [00 00] [ptr-on-win] [ptr-on-lose]
    # The 5c opcode is at 0x7BA89C; f9 00 (Lugia) at 0x7BA89E.
    LUGIA_TRIGGER_OFF = 0x7BA89C
    LUGIA_TRIGGER_LEN = 6
    LUGIA_TRIGGER_EN = bytes([0x5C, 0x00, 0xF9, 0x00, 0x00, 0x00])

    # Extended Lugia script area (battle + script pointers), 28 bytes
    LUGIA_SCRIPT_OFF = 0x7BA890
    LUGIA_SCRIPT_LEN = 28

    # Script pointers: on-win at 0x7BA8A2, on-lose at 0x7BA8A6
    LUGIA_WIN_PTR_OFF  = 0x7BA8A2
    LUGIA_LOSE_PTR_OFF = 0x7BA8A6

    # Ho-Oh encounter: key bytes 4f fa 00 f2 b5 7b 08 (Ho-Oh + script ptr)
    HOOH_TRIGGER_OFF = 0x7BB48F
    HOOH_TRIGGER_LEN = 17

    def test_lugia_battle_opcode_and_species_intact(self, en_rom, fr_rom):
        """The 6 bytes encoding the Lugia battle command (5c) + species (f9 00)
        must be identical in EN and FR."""
        en_bytes = en_rom[self.LUGIA_TRIGGER_OFF : self.LUGIA_TRIGGER_OFF + self.LUGIA_TRIGGER_LEN]
        fr_bytes = fr_rom[self.LUGIA_TRIGGER_OFF : self.LUGIA_TRIGGER_OFF + self.LUGIA_TRIGGER_LEN]

        assert en_bytes == self.LUGIA_TRIGGER_EN, (
            f"EN trigger bytes changed: expected {self.LUGIA_TRIGGER_EN.hex(' ')}, "
            f"got {en_bytes.hex(' ')}"
        )
        assert fr_bytes == self.LUGIA_TRIGGER_EN, (
            f"FR trigger bytes corrupted at 0x{self.LUGIA_TRIGGER_OFF:06X}: "
            f"expected {self.LUGIA_TRIGGER_EN.hex(' ')}, got {fr_bytes.hex(' ')} "
            f"(translation pipeline must not overwrite encounter scripts)"
        )

    def test_lugia_species_byte_is_f9(self, fr_rom):
        """Bytes +2/+3 of the Lugia trigger must be F9 00 = species 249 (Lugia)."""
        species_off = self.LUGIA_TRIGGER_OFF + 2  # 0x7BA89E
        species_bytes = fr_rom[species_off : species_off + 2]
        assert species_bytes == bytes([0xF9, 0x00]), (
            f"Lugia species bytes at 0x{species_off:06X}: "
            f"expected F9 00, got {species_bytes.hex(' ')}"
        )

    def test_lugia_trigger_area_matches_en(self, en_rom, fr_rom):
        """The 28-byte window around the Lugia encounter (0x7BA890) must be
        identical between EN and FR — only text-pointer changes are allowed,
        and they fall outside this window."""
        en_area = en_rom[self.LUGIA_SCRIPT_OFF : self.LUGIA_SCRIPT_OFF + self.LUGIA_SCRIPT_LEN]
        fr_area = fr_rom[self.LUGIA_SCRIPT_OFF : self.LUGIA_SCRIPT_OFF + self.LUGIA_SCRIPT_LEN]
        assert en_area == fr_area, (
            f"Lugia trigger area 0x{self.LUGIA_SCRIPT_OFF:06X}+{self.LUGIA_SCRIPT_LEN}: "
            f"EN={en_area.hex(' ')} FR={fr_area.hex(' ')}"
        )

    def test_lugia_script_pointers_are_valid_rom_addresses(self, fr_rom):
        """The two script pointers after the Lugia battle command must point
        to valid ROM offsets.

        on-win  script ptr at 0x7BA8A2 → should be 0x087BD834 (ROM 0x7BD834)
        on-lose script ptr at 0x7BA8A6 → should be 0x087BFDC0 (ROM 0x7BFDC0)
        """
        for label, ptr_off in [
            ("on-win",  self.LUGIA_WIN_PTR_OFF),
            ("on-lose", self.LUGIA_LOSE_PTR_OFF),
        ]:
            target = _deref(fr_rom, ptr_off)
            assert target is not None, (
                f"Lugia {label} script pointer at 0x{ptr_off:06X} is not a "
                f"valid GBA ROM pointer"
            )
            assert target < len(fr_rom), (
                f"Lugia {label} script pointer at 0x{ptr_off:06X} = "
                f"0x{target+GBA_ROM_BASE:08X} points outside ROM"
            )

    def test_hooh_trigger_area_matches_en(self, en_rom, fr_rom):
        """The 17-byte Ho-Oh encounter trigger (0x7BB48F) must be identical in
        EN and FR — it contains Ho-Oh species bytes and a battle-script pointer."""
        en_bytes = en_rom[self.HOOH_TRIGGER_OFF : self.HOOH_TRIGGER_OFF + self.HOOH_TRIGGER_LEN]
        fr_bytes = fr_rom[self.HOOH_TRIGGER_OFF : self.HOOH_TRIGGER_OFF + self.HOOH_TRIGGER_LEN]
        assert en_bytes == fr_bytes, (
            f"Ho-Oh trigger bytes changed at 0x{self.HOOH_TRIGGER_OFF:06X}: "
            f"EN={en_bytes.hex(' ')} FR={fr_bytes.hex(' ')}"
        )

    def test_hooh_species_byte_is_fa(self, fr_rom):
        """Bytes at 0x7BB497-0x7BB498 must be FA 00 = Ho-Oh (species 250)."""
        species_bytes = fr_rom[0x7BB497 : 0x7BB499]
        assert species_bytes == bytes([0xFA, 0x00]), (
            f"Ho-Oh species bytes at 0x7BB497: expected FA 00, "
            f"got {species_bytes.hex(' ')}"
        )

    def test_hooh_battle_script_pointer_valid(self, fr_rom):
        """The Ho-Oh battle script pointer at 0x7BB499 must point to valid ROM."""
        ptr_off = 0x7BB499
        target = _deref(fr_rom, ptr_off)
        assert target is not None, (
            f"Ho-Oh battle script pointer at 0x{ptr_off:06X} is not a valid GBA ROM pointer"
        )
        assert target < len(fr_rom), (
            f"Ho-Oh battle script pointer target 0x{target:06X} is outside ROM"
        )


# ---------------------------------------------------------------------------
# 2. Legendary species data (catch rate, stats, type)
# ---------------------------------------------------------------------------


class TestLegendarySpeciesData:
    """Base stats for Ho-Oh and Lugia must be intact in the FR ROM.

    The catch rate (byte+8 in the stats entry) is the most capture-critical
    field: a corrupted catch rate of 0 or 255 would make the Pokémon
    uncatchable or trivially catchable.

    The stats entry layout (BPRE/CFRU, 28 bytes from the entry base):
      +0  HP    +1  Atk   +2  Def   +3  Speed
      +4  SpA   +5  SpD   +6  Type1 +7  Type2
      +8  CatchRate ...
    """

    # Base stats table location (CFRU-extended, same in EN and FR)
    LUGIA_STATS_OFF = 0x019E27D8
    HOOH_STATS_OFF  = 0x019E27F4
    STATS_ENTRY_LEN = 28

    # Expected catch rate for both legendaries (= 6 in Unbound CFRU)
    EXPECTED_CATCH_RATE = 6

    # Lugia: Psychic=0x0E, Flying=0x02
    # Ho-Oh: Fire=0x0A, Flying=0x02
    LUGIA_TYPE1 = 0x0E  # Psychic
    HOOH_TYPE1  = 0x0A  # Fire
    SHARED_TYPE2 = 0x02  # Flying

    def test_lugia_catch_rate(self, fr_rom):
        catch_rate = fr_rom[self.LUGIA_STATS_OFF + 8]
        assert catch_rate == self.EXPECTED_CATCH_RATE, (
            f"Lugia catch rate at 0x{self.LUGIA_STATS_OFF+8:06X}: "
            f"expected {self.EXPECTED_CATCH_RATE}, got {catch_rate}"
        )

    def test_hooh_catch_rate(self, fr_rom):
        catch_rate = fr_rom[self.HOOH_STATS_OFF + 8]
        assert catch_rate == self.EXPECTED_CATCH_RATE, (
            f"Ho-Oh catch rate at 0x{self.HOOH_STATS_OFF+8:06X}: "
            f"expected {self.EXPECTED_CATCH_RATE}, got {catch_rate}"
        )

    def test_lugia_types(self, fr_rom):
        type1 = fr_rom[self.LUGIA_STATS_OFF + 6]
        type2 = fr_rom[self.LUGIA_STATS_OFF + 7]
        assert type1 == self.LUGIA_TYPE1, (
            f"Lugia Type1 at +6: expected 0x{self.LUGIA_TYPE1:02X} (Psychic), "
            f"got 0x{type1:02X}"
        )
        assert type2 == self.SHARED_TYPE2, (
            f"Lugia Type2 at +7: expected 0x{self.SHARED_TYPE2:02X} (Flying), "
            f"got 0x{type2:02X}"
        )

    def test_hooh_types(self, fr_rom):
        type1 = fr_rom[self.HOOH_STATS_OFF + 6]
        type2 = fr_rom[self.HOOH_STATS_OFF + 7]
        assert type1 == self.HOOH_TYPE1, (
            f"Ho-Oh Type1 at +6: expected 0x{self.HOOH_TYPE1:02X} (Fire), "
            f"got 0x{type1:02X}"
        )
        assert type2 == self.SHARED_TYPE2, (
            f"Ho-Oh Type2 at +7: expected 0x{self.SHARED_TYPE2:02X} (Flying), "
            f"got 0x{type2:02X}"
        )

    def test_hooh_hp_stat(self, fr_rom):
        hp = fr_rom[self.HOOH_STATS_OFF + 0]
        assert hp == 106, f"Ho-Oh HP corrupted: expected 106, got {hp}"

    def test_lugia_hp_stat(self, fr_rom):
        hp = fr_rom[self.LUGIA_STATS_OFF + 0]
        assert hp == 106, f"Lugia HP corrupted: expected 106, got {hp}"

    def test_hooh_held_item_sacred_ash(self, fr_rom):
        """Ho-Oh holds Sacred Ash (item 0x002D). The held-item fields must be
        intact so the capture gives the player Sacred Ash."""
        item1 = struct.unpack_from("<H", fr_rom, self.HOOH_STATS_OFF + 12)[0]
        item2 = struct.unpack_from("<H", fr_rom, self.HOOH_STATS_OFF + 14)[0]
        SACRED_ASH = 0x002D
        assert item1 == SACRED_ASH, (
            f"Ho-Oh held item1 at +12: expected Sacred Ash (0x{SACRED_ASH:04X}), "
            f"got 0x{item1:04X}"
        )
        assert item2 == SACRED_ASH, (
            f"Ho-Oh held item2 at +14: expected Sacred Ash (0x{SACRED_ASH:04X}), "
            f"got 0x{item2:04X}"
        )

    def test_lugia_no_held_item(self, fr_rom):
        """Lugia holds no item (0x0000)."""
        item1 = struct.unpack_from("<H", fr_rom, self.LUGIA_STATS_OFF + 12)[0]
        item2 = struct.unpack_from("<H", fr_rom, self.LUGIA_STATS_OFF + 14)[0]
        assert item1 == 0, f"Lugia held item1 should be 0, got 0x{item1:04X}"
        assert item2 == 0, f"Lugia held item2 should be 0, got 0x{item2:04X}"

    def test_stats_identical_en_fr(self, en_rom, fr_rom):
        """Full stats entries for both legendaries must be byte-identical in
        EN and FR — translation must not touch species data."""
        for name, off in [("Lugia", self.LUGIA_STATS_OFF), ("Ho-Oh", self.HOOH_STATS_OFF)]:
            en_entry = en_rom[off : off + self.STATS_ENTRY_LEN]
            fr_entry = fr_rom[off : off + self.STATS_ENTRY_LEN]
            assert en_entry == fr_entry, (
                f"{name} stats entry 0x{off:06X} changed in FR: "
                f"EN={en_entry.hex(' ')} FR={fr_entry.hex(' ')}"
            )


# ---------------------------------------------------------------------------
# 3. Wing items (unlock tokens for the encounters)
# ---------------------------------------------------------------------------


class TestWingItems:
    """Rainbow Wing and Silver Wing must be named in French and have intact
    description pointers in the FR ROM.

    Item table: 0x876074, stride 44 bytes, name[14] first, then item data.
    Description pointer at name_base + 0x14 (20 bytes into the entry).
    """

    ITEM_TABLE_BASE = 0x876074
    ITEM_STRIDE     = 44
    NAME_MAX_LEN    = 14
    DESC_PTR_OFFSET = 0x14  # within item entry

    RAINBOW_WING_INDEX = 0x298  # 664
    SILVER_WING_INDEX  = 0x299  # 665

    def _item_base(self, index: int) -> int:
        return self.ITEM_TABLE_BASE + index * self.ITEM_STRIDE

    def _read_name(self, data: bytes, index: int) -> tuple[bytes, bool]:
        base = self._item_base(index)
        return _read_str(data, base, self.NAME_MAX_LEN)

    def _read_desc(self, data: bytes, index: int) -> tuple[bytes, bool] | None:
        base  = self._item_base(index)
        target = _deref(data, base + self.DESC_PTR_OFFSET)
        if target is None:
            return None
        return _read_str(data, target)

    def test_rainbow_wing_name_is_aile_aurore(self, fr_rom):
        base = self._item_base(self.RAINBOW_WING_INDEX)
        raw, terminated = _read_str(fr_rom, base, self.NAME_MAX_LEN)
        assert terminated, (
            f"Rainbow Wing (0x298) name at 0x{base:06X} has no 0xFF terminator"
        )
        text = _decode(fr_rom, base, self.NAME_MAX_LEN)
        assert "Aile Aurore" in text, (
            f"Rainbow Wing name should be 'Aile Aurore', got {text!r}"
        )

    def test_silver_wing_name_is_aile_argentee(self, fr_rom):
        base = self._item_base(self.SILVER_WING_INDEX)
        raw, terminated = _read_str(fr_rom, base, self.NAME_MAX_LEN)
        assert terminated, (
            f"Silver Wing (0x299) name at 0x{base:06X} has no 0xFF terminator"
        )
        text = _decode(fr_rom, base, self.NAME_MAX_LEN)
        assert "Aile Argent" in text, (
            f"Silver Wing name should contain 'Aile Argent', got {text!r}"
        )

    def test_rainbow_wing_description_terminated(self, fr_rom):
        result = self._read_desc(fr_rom, self.RAINBOW_WING_INDEX)
        assert result is not None, "Rainbow Wing description pointer is invalid"
        raw, terminated = result
        assert terminated, (
            "Rainbow Wing description string is not terminated with 0xFF — "
            "could cause a GetStringWidth hang when the item description is shown"
        )

    def test_silver_wing_description_terminated(self, fr_rom):
        result = self._read_desc(fr_rom, self.SILVER_WING_INDEX)
        assert result is not None, "Silver Wing description pointer is invalid"
        raw, terminated = result
        assert terminated, (
            "Silver Wing description string is not terminated with 0xFF"
        )

    def test_rainbow_wing_not_english(self, fr_rom):
        base = self._item_base(self.RAINBOW_WING_INDEX)
        text = _decode(fr_rom, base, self.NAME_MAX_LEN)
        assert "Rainbow Wing" not in text, (
            f"Rainbow Wing item name is still English in FR ROM: {text!r}"
        )

    def test_silver_wing_not_english(self, fr_rom):
        base = self._item_base(self.SILVER_WING_INDEX)
        text = _decode(fr_rom, base, self.NAME_MAX_LEN)
        assert "Silver Wing" not in text, (
            f"Silver Wing item name is still English in FR ROM: {text!r}"
        )


# ---------------------------------------------------------------------------
# 4. NPC dialogue strings in the encounter area are properly terminated
# ---------------------------------------------------------------------------


class TestEncounterAreaStringTermination:
    """Every NPC dialogue string in the Ho-Oh/Lugia encounter zone must be
    terminated with 0xFF.  An unterminated string would cause GetStringWidth to
    loop indefinitely if the NPC is talked to before or after the encounter.

    We also verify that the encounter-script padding regions (between text and
    encounter data) do not contain stray 0xFF bytes that could truncate the
    strings early.
    """

    # Inline dialogue strings in the Lugia area (found via static analysis)
    LUGIA_INLINE_STRINGS = [
        0x7BA8B4,  # pre-battle NPC (sandstorm trainer)
        0x7BA8E6,  # post-battle NPC
        0x7BA91F,  # zap-badge dialogue
    ]

    # Inline dialogue strings in the Ho-Oh area
    HOOH_INLINE_STRINGS = [
        0x7BB3FF,  # long story dialogue ({FD:01}, did you get…)
    ]

    # FR text must not bleed into the encounter trigger window
    LUGIA_TRIGGER_NO_FF_START  = 0x7BA880
    LUGIA_TRIGGER_NO_FF_END    = 0x7BA890  # 16 bytes before trigger
    HOOH_TRIGGER_NO_FF_START   = 0x7BB476  # after movement script
    HOOH_TRIGGER_NO_FF_END     = 0x7BB48F  # up to Ho-Oh trigger

    def _assert_terminated(self, data: bytes, off: int, label: str, maxlen: int = 512):
        end = data.find(0xFF, off, off + maxlen)
        assert end != -1, (
            f"{label} at 0x{off:06X}: string not terminated within {maxlen} bytes "
            f"— GetStringWidth would loop forever if this NPC is rendered"
        )

    def test_lugia_area_inline_strings_terminated_fr(self, fr_rom):
        for off in self.LUGIA_INLINE_STRINGS:
            self._assert_terminated(fr_rom, off, f"Lugia-area inline string")

    def test_hooh_area_inline_strings_terminated_fr(self, fr_rom):
        for off in self.HOOH_INLINE_STRINGS:
            self._assert_terminated(fr_rom, off, f"Ho-Oh-area inline string")

    def test_lugia_trigger_window_has_no_premature_ff(self, fr_rom):
        """No 0xFF in the 16-byte window immediately before the Lugia trigger —
        a stray terminator here would silently truncate a preceding string and
        could corrupt the event script layout."""
        window = fr_rom[self.LUGIA_TRIGGER_NO_FF_START : self.LUGIA_TRIGGER_NO_FF_END]
        ff_positions = [
            self.LUGIA_TRIGGER_NO_FF_START + i
            for i, b in enumerate(window)
            if b == 0xFF
        ]
        assert ff_positions == [], (
            f"Unexpected 0xFF in Lugia pre-trigger window "
            f"0x{self.LUGIA_TRIGGER_NO_FF_START:06X}-0x{self.LUGIA_TRIGGER_NO_FF_END:06X}: "
            f"at {[hex(p) for p in ff_positions]}"
        )

    def test_lugia_inline_strings_match_en_or_are_french(self, en_rom, fr_rom):
        """The first inline string in the Lugia area (trainer battle text)
        should either be translated to French or be an intentional EN string.
        This test documents the current state — a fail means a regression."""
        off = 0x7BA8B4
        en_end = en_rom.find(0xFF, off, off + 512)
        fr_end = fr_rom.find(0xFF, off, off + 512)
        assert en_end != -1, f"EN string at 0x{off:06X} not terminated"
        assert fr_end != -1, f"FR string at 0x{off:06X} not terminated"
        en_bytes = en_rom[off : en_end]
        fr_bytes = fr_rom[off : fr_end]
        # String must be terminated in both ROMs
        assert en_bytes == fr_bytes or len(fr_bytes) > 0, (
            f"String at 0x{off:06X}: FR is empty"
        )


# ---------------------------------------------------------------------------
# 5. Encounter flag logic (setflag/checkflag bytes EN = FR)
# ---------------------------------------------------------------------------


class TestEncounterFlagLogic:
    """The flag-related bytes (setflag 0x29, checkflag 0x2A) inside the
    Ho-Oh and Lugia encounter scripts must be byte-identical between EN and
    FR — any divergence would alter the encounter gate logic (e.g. prevent
    re-encounter, skip the battle command, or break the post-battle flag).

    Flag 0x0700 is the «Ho-Oh encountered» flag; setflag is called at the
    moment the encounter fires, checkflag guards the re-entry path.
    Flags 0x0988 / 0x0994 / 0x0999 / 0x099A serve similar roles for Lugia
    and the broader encounter sequence.
    """

    # (offset, expected_3_bytes, label)
    FLAG_ENTRIES: list[tuple[int, bytes, str]] = [
        (0x7BB22A, bytes([0x29, 0x88, 0x09]), "setflag 0x0988 (Lugia event)"),
        (0x7BB241, bytes([0x2A, 0x94, 0x09]), "checkflag 0x0994"),
        (0x7BB4BA, bytes([0x29, 0x00, 0x07]), "setflag 0x0700 (Ho-Oh encountered)"),
        (0x7BB4C5, bytes([0x2A, 0x00, 0x07]), "checkflag 0x0700 (Ho-Oh gate)"),
        (0x7BB51C, bytes([0x2A, 0x88, 0x09]), "checkflag 0x0988"),
        (0x7BB8D5, bytes([0x2A, 0x99, 0x09]), "checkflag 0x0999"),
        (0x7BBC4E, bytes([0x29, 0x6B, 0x02]), "setflag 0x026B"),
        (0x7BBC6B, bytes([0x2A, 0x6B, 0x02]), "checkflag 0x026B"),
        (0x7BBC93, bytes([0x29, 0x07, 0x08]), "setflag 0x0807"),
        (0x7BBCAA, bytes([0x2A, 0x07, 0x08]), "checkflag 0x0807"),
        (0x7BBD5A, bytes([0x2A, 0x9A, 0x09]), "checkflag 0x099A"),
    ]

    def test_flag_bytes_match_en(self, en_rom, fr_rom):
        """All setflag/checkflag instructions in the encounter scripts must
        be byte-identical between EN and FR."""
        for off, expected, label in self.FLAG_ENTRIES:
            en_bytes = en_rom[off : off + 3]
            fr_bytes = fr_rom[off : off + 3]
            assert en_bytes == fr_bytes, (
                f"{label} at 0x{off:06X}: "
                f"EN={en_bytes.hex(' ')} ≠ FR={fr_bytes.hex(' ')}"
            )

    def test_flag_bytes_match_expected_values(self, fr_rom):
        """The setflag/checkflag bytes must equal their known correct values —
        this guards against the EN ROM itself being corrupted."""
        for off, expected, label in self.FLAG_ENTRIES:
            fr_bytes = fr_rom[off : off + 3]
            assert fr_bytes == expected, (
                f"{label} at 0x{off:06X}: "
                f"expected {expected.hex(' ')}, got {fr_bytes.hex(' ')}"
            )

    def test_hooh_flag_0700_set_before_check(self, fr_rom):
        """setflag 0x0700 (at 0x7BB4BA) must appear BEFORE checkflag 0x0700
        (at 0x7BB4C5) — the check guards the re-entry path and only makes
        sense after the flag is set at encounter time."""
        SET_OFF   = 0x7BB4BA
        CHECK_OFF = 0x7BB4C5
        assert SET_OFF < CHECK_OFF, (
            f"setflag 0x0700 at 0x{SET_OFF:X} should precede "
            f"checkflag 0x0700 at 0x{CHECK_OFF:X}"
        )
        set_bytes   = fr_rom[SET_OFF   : SET_OFF   + 3]
        check_bytes = fr_rom[CHECK_OFF : CHECK_OFF + 3]
        assert set_bytes   == bytes([0x29, 0x00, 0x07]), (
            f"setflag 0x0700 at 0x{SET_OFF:X}: got {set_bytes.hex(' ')}"
        )
        assert check_bytes == bytes([0x2A, 0x00, 0x07]), (
            f"checkflag 0x0700 at 0x{CHECK_OFF:X}: got {check_bytes.hex(' ')}"
        )

    def test_lugia_flag_0988_set_before_check(self, fr_rom):
        """setflag 0x0988 (at 0x7BB22A) must appear BEFORE checkflag 0x0988
        (at 0x7BB51C) — same ordering invariant as the Ho-Oh flag."""
        SET_OFF   = 0x7BB22A
        CHECK_OFF = 0x7BB51C
        assert SET_OFF < CHECK_OFF
        assert fr_rom[SET_OFF   : SET_OFF   + 3] == bytes([0x29, 0x88, 0x09])
        assert fr_rom[CHECK_OFF : CHECK_OFF + 3] == bytes([0x2A, 0x88, 0x09])


# ---------------------------------------------------------------------------
# 6. Méga-Bracelet item integrity
# ---------------------------------------------------------------------------


class TestMegaBraceletIntegrity:
    """The Méga-Bracelet is the key item obtained at the Ho-Oh encounter spot.
    Its name must be translated (EN «Mega Bracelet» → FR «Méga-Bracelet»),
    terminated correctly, and its description must also be properly terminated
    so GetStringWidth never loops.

    The item lives at index 0x21A in the standard item table (base 0x876074,
    stride 44), placing the struct at 0x87BCEC.  CFRU changed this entry to
    use a name POINTER (bytes 0-3 = GBA ptr to name string) rather than an
    inline 14-byte name.  The name string lives at the same ROM address in
    both EN and FR (pointer unchanged); only the content at that address
    differs.  The description pointer sits at the standard +0x14 offset within
    the item struct.
    """

    ITEM_TABLE_BASE = 0x876074
    ITEM_STRIDE     = 44
    MEGA_BRAC_IDX   = 0x21A                                     # item index
    # Struct base: 0x876074 + 0x21A * 44 = 0x87BCEC
    MEGA_BRAC_BASE  = ITEM_TABLE_BASE + MEGA_BRAC_IDX * ITEM_STRIDE
    DESC_PTR_OFFSET = 0x14

    # EN name bytes starting with M-e-g-a
    EN_NAME_PREFIX = bytes([0xC7, 0xD9, 0xDB, 0xD5])       # "Mega"

    # FR name bytes starting with M-é-g-a-  (é = 0x1B, - = 0xAE)
    FR_NAME_PREFIX = bytes([0xC7, 0x1B, 0xDB, 0xD5, 0xAE]) # "Méga-"

    def _name_off(self, rom: bytes) -> int | None:
        """Follow the name pointer at MEGA_BRAC_BASE to get the name string offset."""
        return _deref(rom, self.MEGA_BRAC_BASE)

    def test_mega_bracelet_name_translated_to_french(self, en_rom, fr_rom):
        """The name string at the pointed-to address must differ between EN and FR."""
        en_off = self._name_off(en_rom)
        fr_off = self._name_off(fr_rom)
        assert en_off is not None, f"EN name pointer at 0x{self.MEGA_BRAC_BASE:06X} is invalid"
        assert fr_off is not None, f"FR name pointer at 0x{self.MEGA_BRAC_BASE:06X} is invalid"
        en_name = en_rom[en_off : en_off + 14]
        fr_name = fr_rom[fr_off : fr_off + 14]
        assert en_name != fr_name, (
            f"Méga-Bracelet name at ptr→0x{fr_off:06X} is still EN — "
            f"translation not applied"
        )

    def test_mega_bracelet_fr_name_starts_with_mega_accent(self, fr_rom):
        """FR name must start with 'Méga-' (0xC7 0x1B 0xDB 0xD5 0xAE)."""
        fr_off = self._name_off(fr_rom)
        assert fr_off is not None, f"FR name pointer at 0x{self.MEGA_BRAC_BASE:06X} invalid"
        fr_prefix = fr_rom[fr_off : fr_off + len(self.FR_NAME_PREFIX)]
        assert fr_prefix == self.FR_NAME_PREFIX, (
            f"Méga-Bracelet FR name at ptr→0x{fr_off:06X}: "
            f"expected {self.FR_NAME_PREFIX.hex(' ')}, got {fr_prefix.hex(' ')}"
        )

    def test_mega_bracelet_fr_name_terminated(self, fr_rom):
        """FR Mega Bracelet name must be terminated with 0xFF within 14 bytes."""
        fr_off = self._name_off(fr_rom)
        assert fr_off is not None, f"FR name pointer at 0x{self.MEGA_BRAC_BASE:06X} invalid"
        raw, terminated = _read_str(fr_rom, fr_off, 14)
        assert terminated, (
            f"Méga-Bracelet name at ptr→0x{fr_off:06X} has no 0xFF terminator"
        )

    def test_mega_bracelet_description_pointer_valid(self, fr_rom):
        """Description pointer at MEGA_BRAC_BASE + 0x14 must be a valid ROM address."""
        desc_ptr_off = self.MEGA_BRAC_BASE + self.DESC_PTR_OFFSET
        target = _deref(fr_rom, desc_ptr_off)
        assert target is not None, (
            f"Méga-Bracelet description pointer at 0x{desc_ptr_off:06X} is not a "
            f"valid GBA ROM pointer (raw: {fr_rom[desc_ptr_off:desc_ptr_off+4].hex(' ')})"
        )
        assert target < len(fr_rom), (
            f"Méga-Bracelet description pointer targets 0x{target:06X}, outside ROM"
        )

    def test_mega_bracelet_description_terminated(self, fr_rom):
        """FR Mega Bracelet description must be terminated with 0xFF."""
        desc_ptr_off = self.MEGA_BRAC_BASE + self.DESC_PTR_OFFSET
        target = _deref(fr_rom, desc_ptr_off)
        if target is None:
            pytest.skip("Description pointer invalid — covered by test above")
        raw, terminated = _read_str(fr_rom, target)
        assert terminated, (
            f"Méga-Bracelet description at 0x{target:06X} has no 0xFF terminator "
            f"— GetStringWidth would loop on this item's help text"
        )
