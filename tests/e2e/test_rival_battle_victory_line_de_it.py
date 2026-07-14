"""Régression DE/IT : la réplique post-combat du rival reste traduite."""

from __future__ import annotations

import re
import struct
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder


GBA_BASE = 0x08000000
LIVE_POINTER_SITE = 0x1E5A488
ORIGINAL_ENGLISH_OFFSET = 0x1F478EE
PROJECT_ROOT = Path(__file__).resolve().parents[2]

LANGUAGE_CASES = (
    (
        "de",
        PROJECT_ROOT / "output" / "roms" / "GenedRom-de.gba",
        "Mann… warum habe ich mir überhaupt Sorgen gemacht? Natürlich bist du bereit!",
    ),
    (
        "it",
        PROJECT_ROOT / "output" / "roms" / "GenedRom-it.gba",
        "Cavolo… di cosa mi preoccupavo? Certo che sei pronto!",
    ),
)


def _decode_pointer_target(rom: bytes) -> tuple[int, str]:
    """Suit le pointeur vivant et décode la chaîne GBA terminée."""
    pointer = struct.unpack_from("<I", rom, LIVE_POINTER_SITE)[0]
    target = pointer - GBA_BASE
    assert 0 <= target < len(rom), (
        f"pointeur @0x{LIVE_POINTER_SITE:07X} invalide : 0x{pointer:08X}"
    )
    end = rom.find(b"\xff", target, min(target + 800, len(rom)))
    assert end >= 0, f"chaîne non terminée via le pointeur @0x{LIVE_POINTER_SITE:07X}"
    raw = rom[target : end + 1]
    decoded = TextDecoder.decode_pokemon(raw, preserve_unknown=True)
    # Dans la police CFRU, 0xB0 est le glyphe « … » ; le décodeur historique
    # l'expose encore comme un guillemet droit.
    if 0xB0 in raw:
        decoded = decoded.replace('"', "…")
    return target, decoded


def _visible_text(decoded: str) -> str:
    """Normalise les contrôles et retours de ligne sans masquer le texte affiché."""
    without_controls = re.sub(r"<0x[0-9A-Fa-f]{2}>", " ", decoded)
    return " ".join(without_controls.split())


@pytest.mark.parametrize("language,rom_path,expected", LANGUAGE_CASES, ids=("de", "it"))
def test_rival_battle_victory_line_is_localized(
    language: str, rom_path: Path, expected: str
) -> None:
    """La cible du pointeur doit contenir la traduction, sans résidu anglais."""
    if not rom_path.exists():
        pytest.skip(f"{rom_path.name} absente — lancer make build-{language}")

    target, decoded = _decode_pointer_target(rom_path.read_bytes())
    visible = _visible_text(decoded)

    assert visible == expected, (
        f"{language.upper()} : attendu {expected!r} via @0x{LIVE_POINTER_SITE:07X}, "
        f"cible vivante 0x{target:07X} (slot EN 0x{ORIGINAL_ENGLISH_OFFSET:07X}), "
        f"obtenu {visible!r}"
    )
    assert "what was I even worried about" not in visible
    assert "Of course you're ready" not in visible
