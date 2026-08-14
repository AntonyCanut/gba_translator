"""Gardes ROM des patchs texte/moteur portés de FR vers DE (F-602)."""

from __future__ import annotations

import importlib
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder, TextEncoder
from src.i18n import load_registry

ROOT = Path(__file__).resolve().parents[3]
ROM_BASE = 0x08000000
PORTS = {
    "mission_titles",
    "mission_tab_labels",
    "pc_move_labels",
    "pokedex_stat_labels",
    "trainer_class_names",
    "zone_names",
}


def _module(name: str):
    path = ROOT / "languages" / "de" / "patches" / f"{name}.py"
    assert path.is_file(), f"patch DE manquant: {path.relative_to(ROOT)}"
    return importlib.import_module(f"languages.de.patches.{name}")


def _decode(rom: bytes, offset: int) -> str:
    end = rom.index(0xFF, offset)
    return TextDecoder.decode_pokemon(rom[offset : end + 1], preserve_unknown=True)


def test_descriptor_declares_every_useful_port_for_generic_dispatch() -> None:
    from scripts import build_language

    patches = set(load_registry().get("de").patches)

    assert PORTS <= patches
    for step in PORTS:
        module = _module(step)
        assert build_language._lang_patch_script(step, "de") == Path(module.__file__)


@pytest.mark.parametrize("step", sorted(PORTS))
def test_ported_patch_cli_is_self_contained(step: str) -> None:
    script = ROOT / "languages" / "de" / "patches" / f"{step}.py"

    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_mission_title_replaces_only_the_guarded_english_cell() -> None:
    mod = _module("mission_titles")
    rom = bytearray(b"\x00" * 0x2000000)
    expected = TextEncoder.encode("The Food Thief", "pokemon")
    rom[mod.TITLE_OFFSET : mod.TITLE_OFFSET + len(expected)] = expected

    changed = mod.apply(rom)

    assert changed == 1
    assert _decode(rom, mod.TITLE_OFFSET) == "Der Essensdieb"
    first = bytes(rom)
    assert mod.apply(rom) == 0
    assert bytes(rom) == first


def test_mission_title_rejects_an_unknown_preimage() -> None:
    mod = _module("mission_titles")
    rom = bytearray(b"\x00" * 0x2000000)
    rom[mod.TITLE_OFFSET : mod.TITLE_OFFSET + 4] = b"BAD\xff"

    with pytest.raises(ValueError, match="inattendus"):
        mod.apply(rom)


def test_mission_tab_suffix_is_removed_through_its_live_pointer() -> None:
    mod = _module("mission_tab_labels")
    rom = bytearray(b"\x00" * 0x2000000)
    target = 0x1F10000
    suffix = TextEncoder.encode("Missionen", "pokemon")
    struct.pack_into("<I", rom, mod.SUFFIX_PTR_OFFSET, ROM_BASE + target)
    rom[target : target + len(suffix)] = suffix

    changed = mod.apply(rom)

    assert changed == 1
    assert rom[target] == 0xFF
    first = bytes(rom)
    assert mod.apply(rom) == 0
    assert bytes(rom) == first


def test_mission_tab_suffix_rejects_an_unrelated_string() -> None:
    mod = _module("mission_tab_labels")
    rom = bytearray(b"\x00" * 0x2000000)
    target = 0x1F10000
    payload = TextEncoder.encode("Gefahr", "pokemon")
    struct.pack_into("<I", rom, mod.SUFFIX_PTR_OFFSET, ROM_BASE + target)
    rom[target : target + len(payload)] = payload

    with pytest.raises(ValueError, match="Suffix"):
        mod.apply(rom)


def test_pc_mail_action_fits_its_fixed_cell_and_is_idempotent() -> None:
    mod = _module("pc_move_labels")
    rom = bytearray(b"\x00" * (mod.MAIL_OFFSET + mod.CELL_SIZE + 8))
    rom[mod.MAIL_OFFSET : mod.MAIL_OFFSET + mod.CELL_SIZE] = mod.ENGLISH_CELL

    changed = mod.apply(rom)

    assert changed == 1
    assert _decode(rom, mod.MAIL_OFFSET) == "Zum Beutel"
    assert mod.apply(rom) == 0


def test_pc_mail_action_rejects_unknown_cell_bytes() -> None:
    mod = _module("pc_move_labels")
    rom = bytearray(b"\x00" * (mod.MAIL_OFFSET + mod.CELL_SIZE + 8))
    rom[mod.MAIL_OFFSET : mod.MAIL_OFFSET + mod.CELL_SIZE] = b"X" * mod.CELL_SIZE

    with pytest.raises(ValueError, match="octets inattendus"):
        mod.apply(rom)


def _pokedex_rom(mod) -> bytearray:
    rom = bytearray(b"\x00" * 0x970000)
    cursor = 0x900000
    for table in mod.PTR_TABLE_OFFSETS:
        for index, key in enumerate(mod.STAT_ORDER):
            struct.pack_into("<I", rom, table + index * 4, ROM_BASE + cursor)
            entry = mod.EN_ENTRIES[key]
            rom[cursor : cursor + len(entry)] = entry
            cursor += len(entry)
    return rom


def test_pokedex_stats_use_bounded_german_abbreviations() -> None:
    mod = _module("pokedex_stat_labels")
    rom = _pokedex_rom(mod)

    changed = mod.apply(rom)

    # SpA est déjà identique dans les deux copies ; les cinq autres labels changent.
    assert changed == 10
    for table in mod.PTR_TABLE_OFFSETS:
        rendered = []
        for index in range(6):
            target = struct.unpack_from("<I", rom, table + index * 4)[0] - ROM_BASE
            label = TextDecoder.decode_pokemon(
                bytes(rom[target : target + 4]) + b"\xff", preserve_unknown=True
            )
            rendered.append(label.rstrip())
        assert rendered == ["KP", "Ang", "Ver", "Init", "SpA", "SpV"]
    assert mod.apply(rom) == 0


def test_pokedex_stats_reject_unknown_entry_bytes() -> None:
    mod = _module("pokedex_stat_labels")
    rom = _pokedex_rom(mod)
    first = struct.unpack_from("<I", rom, mod.PTR_TABLE_OFFSETS[0])[0] - ROM_BASE
    rom[first : first + 7] = b"BROKEN!"

    with pytest.raises(ValueError, match="inattendus"):
        mod.apply(rom)


def test_trainer_classes_patch_every_available_german_cell_strictly() -> None:
    mod = _module("trainer_class_names")
    source = (ROOT / "input/roms/englishrom.gba").read_bytes()
    rom = bytearray(source)

    stats = mod.apply(rom, source)

    assert stats == {"written": 95, "unchanged": 0, "preserved": 11}
    expected = {
        13: "Schnösel",
        20: "Käfermaniac",
        23: "Lady",
        33: "Drachenprofi",
        37: "Schirmdame",
        48: "Schattenboss",
        49: "Ex-Schatten",
        82: "Forscher",
        96: "Geschwister",
    }
    for index, text in expected.items():
        offset = mod.TABLE_BASE + index * mod.CELL_STRIDE
        assert _decode(rom, offset) == text
    assert mod.apply(rom, source) == {"written": 0, "unchanged": 95, "preserved": 11}


def test_trainer_classes_reject_a_corrupted_source_cell() -> None:
    mod = _module("trainer_class_names")
    source = (ROOT / "input/roms/englishrom.gba").read_bytes()
    rom = bytearray(source)
    offset = mod.TABLE_BASE + mod.FIRST_TRANSLATED_INDEX * mod.CELL_STRIDE
    rom[offset : offset + mod.CELL_STRIDE] = b"X" * mod.CELL_STRIDE

    with pytest.raises(ValueError, match="classe Dresseur"):
        mod.apply(rom, source)


def test_zone_names_restore_english_strings_and_known_referrers() -> None:
    mod = _module("zone_names")
    source = (ROOT / "input/roms/englishrom.gba").read_bytes()
    rom = bytearray(source)
    translated = 0x1F10000
    german = TextEncoder.encode("Hafen von Antésia", "pokemon")
    rom[translated : translated + len(german)] = german
    slot = mod.POINTER_SITES[0x0B51EAC][0]
    struct.pack_into("<I", rom, slot, ROM_BASE + translated)

    changed = mod.apply(rom, source)

    assert changed >= 1
    for offset, slots in mod.POINTER_SITES.items():
        assert _decode(rom, offset) == mod.ENGLISH_NAMES[offset]
        for pointer_site in slots:
            assert struct.unpack_from("<I", rom, pointer_site)[0] == ROM_BASE + offset
    first = bytes(rom)
    assert mod.apply(rom, source) == 0
    assert bytes(rom) == first


def test_zone_names_reject_an_unknown_relocated_preimage() -> None:
    mod = _module("zone_names")
    source = (ROOT / "input/roms/englishrom.gba").read_bytes()
    rom = bytearray(source)
    translated = 0x1F10000
    bad = TextEncoder.encode("Nom inventé", "pokemon")
    rom[translated : translated + len(bad)] = bad
    slot = mod.POINTER_SITES[0x0B51EAC][0]
    struct.pack_into("<I", rom, slot, ROM_BASE + translated)

    with pytest.raises(ValueError, match="pointeur de zone"):
        mod.apply(rom, source)


@pytest.mark.rom
def test_built_de_rom_contains_every_port_and_is_idempotent() -> None:
    built_rom = ROOT / "output" / "roms" / "GenedRom-de.gba"
    if not built_rom.is_file():
        pytest.skip("GenedRom-de.gba non construite")

    source = (ROOT / "input" / "roms" / "englishrom.gba").read_bytes()
    original = built_rom.read_bytes()
    rom = bytearray(original)

    mission_title = _module("mission_titles")
    mission_tabs = _module("mission_tab_labels")
    pc_labels = _module("pc_move_labels")
    pokedex_stats = _module("pokedex_stat_labels")
    trainer_classes = _module("trainer_class_names")
    zones = _module("zone_names")

    assert mission_title.apply(rom) == 0
    assert mission_tabs.apply(rom) == 0
    assert pc_labels.apply(rom) == 0
    assert pokedex_stats.apply(rom) == 0
    assert trainer_classes.apply(rom, source) == {
        "written": 0,
        "unchanged": 95,
        "preserved": 11,
    }
    assert zones.apply(rom, source) == 0
    assert bytes(rom) == original

    assert _decode(rom, mission_title.TITLE_OFFSET) == "Der Essensdieb"
    suffix = struct.unpack_from("<I", rom, mission_tabs.SUFFIX_PTR_OFFSET)[0] - ROM_BASE
    assert rom[suffix] == 0xFF
    assert _decode(rom, pc_labels.MAIL_OFFSET) == "Zum Beutel"
    for offset, expected in zones.ENGLISH_NAMES.items():
        assert _decode(rom, offset) == expected
