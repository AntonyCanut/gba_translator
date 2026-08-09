"""Régression de l’ordre français sur l’écran de saisie du surnom.

La routine FireRed d’origine concatène ``nom d’espèce + titre``. Le patch FR
doit exécuter les vrais octets Thumb qui composent au contraire
``Surnom de + nom d’espèce + ?`` avant l’appel au moteur de texte.
"""

from __future__ import annotations

import importlib.util
import struct
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder, TextEncoder


ROOT = Path(__file__).resolve().parents[1]
COMBINED = ROOT / "languages/fr/combined_fr.txt"
PATCH_MODULE = ROOT / "languages/fr/patches/nickname_prompt.py"
BUILT_ROM = ROOT / "output/roms/GenedRom-fr.gba"

ROUTINE_FILE = 0x9F4F0
ROUTINE_GBA = 0x08000000 + ROUTINE_FILE
ROUTINE_SIZE = 0x7C
STRING_COPY = 0x08008D84
STRING_APPEND_N = 0x08008DEC
FILL_WINDOW = 0x0800445C
PRINT_TEXT = 0x08002C48
PUT_WINDOW = 0x08003FA0
NAMING_SCREEN_PTR = 0x0203998C
SPECIES_NAMES = 0x0966A98C

# ROM anglaise, ``DrawMonTextEntryBox`` + son pool de littéraux. Ce repli fait
# réellement échouer la garde avant que le module de patch n’existe.
ORIGINAL_ROUTINE = bytes.fromhex(
    "30b58bb0184d28681849401801880b2041431748091803a869f73cfc28681549"
    "40180068816803a80f2269f767fc2868114c00190078112164f798ff28680019"
    "007801210091002101910291012103aa012363f781fb28680019007864f728fd"
    "0bb030bc01bc00478c990302341e00008ca96609281e0000141e0000"
)


def _live_translation(offset: int) -> str:
    value = None
    for line in COMBINED.read_text(encoding="utf-8").splitlines():
        if not line.startswith("0x") or ":" not in line:
            continue
        raw_offset, text = line.split(":", 1)
        if int(raw_offset, 16) == offset:
            value = text.lstrip(" ")
    assert value is not None
    return value


def _load_routine() -> bytes:
    if not PATCH_MODULE.exists():
        return ORIGINAL_ROUTINE
    spec = importlib.util.spec_from_file_location("nickname_prompt_patch", PATCH_MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PATCHED_ROUTINE


def _read_string(uc, address: int) -> bytes:
    out = bytearray()
    while True:
        value = bytes(uc.mem_read(address + len(out), 1))[0]
        out.append(value)
        if value == 0xFF:
            return bytes(out)


def _emulate_title(routine: bytes, title: str, species_name: str) -> str:
    unicorn = pytest.importorskip("unicorn")
    from unicorn import Uc, UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_THUMB
    from unicorn.arm_const import (
        UC_ARM_REG_LR,
        UC_ARM_REG_PC,
        UC_ARM_REG_R0,
        UC_ARM_REG_R1,
        UC_ARM_REG_R2,
        UC_ARM_REG_SP,
    )

    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    uc.mem_map(0x08000000, 0x01800000)
    uc.mem_map(0x02000000, 0x00040000)
    uc.mem_map(0x03000000, 0x00008000)
    uc.mem_write(ROUTINE_GBA, routine)

    screen = 0x02010000
    template = 0x02013000
    title_ptr = 0x02018000
    species = 1
    uc.mem_write(NAMING_SCREEN_PTR, screen.to_bytes(4, "little"))
    uc.mem_write(screen + 0x1E28, template.to_bytes(4, "little"))
    uc.mem_write(screen + 0x1E34, species.to_bytes(2, "little"))
    uc.mem_write(screen + 0x1E14, b"\x04")
    uc.mem_write(template + 8, title_ptr.to_bytes(4, "little"))
    uc.mem_write(title_ptr, TextEncoder.encode_pokemon(title))
    species_bytes = TextEncoder.encode_pokemon(species_name)
    uc.mem_write(SPECIES_NAMES + 11 * species, species_bytes.ljust(11, b"\xff"))

    rendered = []

    def _return(uc_) -> None:
        uc_.reg_write(UC_ARM_REG_PC, uc_.reg_read(UC_ARM_REG_LR))

    def _copy(uc_, append: bool = False) -> None:
        dest = uc_.reg_read(UC_ARM_REG_R0)
        src = uc_.reg_read(UC_ARM_REG_R1)
        if append:
            dest += len(_read_string(uc_, dest)) - 1
        payload = _read_string(uc_, src)
        uc_.mem_write(dest, payload)
        uc_.reg_write(UC_ARM_REG_R0, dest + len(payload) - 1)
        _return(uc_)

    def _hook(uc_, address, _size, _user):
        if address == STRING_COPY:
            _copy(uc_)
        elif address == STRING_APPEND_N:
            _copy(uc_, append=True)
        elif address == FILL_WINDOW:
            _return(uc_)
        elif address == PRINT_TEXT:
            rendered.append(_read_string(uc_, uc_.reg_read(UC_ARM_REG_R2)))
            _return(uc_)
        elif address == PUT_WINDOW:
            uc_.emu_stop()

    uc.hook_add(UC_HOOK_CODE, _hook)
    uc.reg_write(UC_ARM_REG_SP, 0x03007F00)
    uc.reg_write(UC_ARM_REG_LR, 0x08000001)
    uc.emu_start(ROUTINE_GBA | 1, ROUTINE_GBA + ROUTINE_SIZE, count=500)
    assert len(rendered) == 1
    return TextDecoder.decode_pokemon(rendered[0])


def test_issue_179_composes_prefix_species_and_question_mark() -> None:
    title = _live_translation(0x418E5C)
    rendered = _emulate_title(_load_routine(), title, "Wattouat")
    assert rendered == "Surnom de Wattouat ?"


def test_issue_179_patch_is_declared_and_idempotent() -> None:
    assert PATCH_MODULE.exists(), "le patch post-build du titre de surnom manque"
    spec = importlib.util.spec_from_file_location("nickname_prompt_apply", PATCH_MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    data = bytearray(ROUTINE_FILE + ROUTINE_SIZE)
    data[ROUTINE_FILE:ROUTINE_FILE + ROUTINE_SIZE] = ORIGINAL_ROUTINE
    assert module.apply_patches(data) == 1
    assert data[ROUTINE_FILE:ROUTINE_FILE + ROUTINE_SIZE] == module.PATCHED_ROUTINE
    assert module.apply_patches(data) == 0


@pytest.mark.rom
def test_issue_179_built_rom_renders_wattouat_title() -> None:
    data = BUILT_ROM.read_bytes()
    routine = data[ROUTINE_FILE:ROUTINE_FILE + ROUTINE_SIZE]
    assert routine == _load_routine()

    title_pointer = struct.unpack_from("<I", data, 0x3E247C)[0]
    title_offset = title_pointer - 0x08000000
    title_bytes = data[title_offset:data.index(b"\xff", title_offset) + 1]
    title = TextDecoder.decode_pokemon(title_bytes)

    wattouat_offset = (SPECIES_NAMES - 0x08000000) + 11 * 179
    wattouat_bytes = data[wattouat_offset:wattouat_offset + 11]
    wattouat = TextDecoder.decode_pokemon(wattouat_bytes)

    assert title == "Surnom de "
    assert wattouat == "Wattouat"
    assert _emulate_title(routine, title, wattouat) == "Surnom de Wattouat ?"
