"""Regression guard for the six untranslated Dragon Cave cutscene lines."""

from __future__ import annotations

import re
import struct

import pytest

from src.core.text_codec import TextDecoder

GBA_BASE = 0x08000000

# (speaker, live pointer site, original string offset, expected FR, forbidden EN)
# A short FR string may overwrite its original slot; longer strings are relocated.
CUTSCENE_LINES = (
    (
        "Ace",
        0x1E5DAD4,
        0x1F47E06,
        "Quoi ? Ces Pokémon",
        "Wha-? These Pokémon",
    ),
    (
        "Ivory",
        0x1E5DC81,
        0x1F481B4,
        "Si ça ne tenait qu'à moi, nous ne détruirions rien",
        "If it were up to me, we wouldn't be destroying anything",
    ),
    (
        "Marlon",
        0x1E5E0B8,
        0x1F485D8,
        "Soulève ce rocher et pousse-le sur le côté",
        "Just pick up that boulder and move it to the side",
    ),
    (
        "Marlon",
        0x1E5E230,
        0x1F48785,
        "je ne m'attends pas à ce que tu nous pardonnes un jour",
        "I don't expect you to ever forgive us for what we did",
    ),
    (
        "Ace",
        0x1E5E126,
        0x1F4868B,
        "Je t'avais dit que je reviendrais",
        "I told you I'd come back",
    ),
    (
        "Mélony",
        0x1E5E43F,
        0x1F48D07,
        "Ce drôle de type essaie sans arrêt de me convaincre qu'il est mon père",
        "This weird guy keeps trying to convince me he's my dad",
    ),
)


def _decode_pointer_target(rom: bytes, pointer_site: int) -> tuple[int, str]:
    """Decode the terminated string addressed by a live GBA pointer."""
    pointer = struct.unpack_from("<I", rom, pointer_site)[0]
    target = pointer - GBA_BASE
    assert 0 <= target < len(rom), (
        f"pointer @0x{pointer_site:07X} targets invalid address 0x{pointer:08X}"
    )
    end = rom.find(b"\xff", target, min(target + 800, len(rom)))
    assert end >= 0, f"unterminated string targeted by pointer @0x{pointer_site:07X}"
    return target, TextDecoder.decode_pokemon(rom[target : end + 1], preserve_unknown=True)


def _visible_text(decoded: str) -> str:
    """Flatten line/page controls so assertions describe player-visible prose."""
    without_controls = re.sub(r"<0x[0-9A-Fa-f]{2}>", " ", decoded)
    return " ".join(without_controls.split())


@pytest.mark.parametrize(
    "speaker,pointer_site,english_offset,expected_french,forbidden_english",
    CUTSCENE_LINES,
)
def test_dragon_cave_cutscene_is_french(
    fr_rom_path,
    speaker: str,
    pointer_site: int,
    english_offset: int,
    expected_french: str,
    forbidden_english: str,
) -> None:
    """Each live cutscene pointer must resolve to FR without its reported EN residue."""
    rom = fr_rom_path.read_bytes()

    target, decoded = _decode_pointer_target(rom, pointer_site)
    visible = _visible_text(decoded)

    assert expected_french in visible, (
        f"{speaker}: expected {expected_french!r} via pointer @0x{pointer_site:07X}, "
        f"live target 0x{target:07X} (original slot 0x{english_offset:07X}), "
        f"got {visible!r}"
    )
    assert forbidden_english not in visible, (
        f"{speaker}: English residue remains via pointer @0x{pointer_site:07X}: "
        f"{visible!r}"
    )
