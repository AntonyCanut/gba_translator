"""E2E coverage for the Crystal Peak end-game dialogue cluster.

The strings are reached through script pointers, so this test follows the
live pointer slots from the English ROM into the built French ROM instead of
assuming that relocation preserves the original text offsets.
"""

from __future__ import annotations

import struct

from src.core.text_codec import TextDecoder


SAMPLES = {
    # Ace's ascent: the two strings reported by this ticket.
    0x1F479B7: (
        "Gagnons le sommet au plus vite.",
        "Let's make our way to the top as",
    ),
    0x1F47A62: ("En faisant équipe avec", "While teamed up with"),
    # Alternate ascent dialogue covered by the parent Crystal Peak ticket.
    0x1F47B23: ("Ces types", "Those Light of Ruin guys"),
    # Aklove/Hoopa final battle.
    0x1F49748: ("Hoopa a invoqué", "Hoopa summoned a mysterious power"),
    # Zeph/Marlon epilogue.
    0x1F4A66B: ("Bien sûr, Zeph", "Of course, Zeph"),
    # Champion victory screen.
    0x1F4BCD8: ("nouvelle tenue", "new outfit has been"),
    # Final post-campaign scene.
    0x1F4CFB3: ("Marlon ! Toi aussi", "Marlon! You're here too"),
}

POINTER_BASE = 0x08000000
POINTER_END = 0x0A000000
POKEMON_TERMINATOR = 0xFF


def _pointer_slots(rom: bytes, target: int) -> list[int]:
    needle = struct.pack("<I", POINTER_BASE + target)
    slots: list[int] = []
    cursor = 0
    while True:
        slot = rom.find(needle, cursor)
        if slot < 0:
            return slots
        slots.append(slot)
        cursor = slot + 1


def _decode_pointer_target(rom: bytes, slot: int, limit: int = 1200) -> str:
    pointer = struct.unpack_from("<I", rom, slot)[0]
    assert POINTER_BASE <= pointer < POINTER_END, (
        f"invalid live GBA pointer 0x{pointer:08X} at 0x{slot:X}"
    )
    offset = pointer - POINTER_BASE
    end = min(offset + limit, len(rom))
    raw = rom[offset:end]
    terminator = raw.find(bytes([POKEMON_TERMINATOR]))
    if terminator >= 0:
        raw = raw[: terminator + 1]
    return TextDecoder.decode_pokemon(raw, preserve_unknown=True)


def test_crystal_peak_samples_decode_through_live_pointers(en_rom_path, fr_rom_path):
    """Every representative final-scene sample is French at a live pointer."""
    en_rom = en_rom_path.read_bytes()
    fr_rom = fr_rom_path.read_bytes()

    for offset, (french_marker, english_marker) in SAMPLES.items():
        slots = _pointer_slots(en_rom, offset)
        assert slots, f"no live pointer found for 0x{offset:X}"

        decoded = [_decode_pointer_target(fr_rom, slot) for slot in slots]
        matching = [text for text in decoded if french_marker in text]
        assert matching, (
            f"0x{offset:X}: no live French decode contained {french_marker!r}; "
            f"decoded samples={decoded[:3]!r}"
        )
        assert all(english_marker not in text for text in decoded), (
            f"0x{offset:X}: English residue survived a live-pointer decode"
        )
