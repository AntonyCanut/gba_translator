"""E2E: no English floor label is reachable in the built FR ROM (issue #100).

Issue #100 was reopened three times. Each round fixed one storage location and
each time the reporter came back with a screenshot showing an English floor —
the last one being ``Grotte de la Vallée 2F``, i.e. a floor glued to a **place
name** in the map-name pop-up.

The reason is that Unbound spells floors in several unrelated places:

  * the map-name pop-up table (``0x41803A``, six duplicate pointer tables);
  * elevator menus, both the FireRed ``multichoice`` lists and map scripts,
    each with their own cells (``0x417AB0``, ``0x7D8F91``, ``0x7ECDAD``,
    ``0x1F6F5FB``);
  * the Cube collection list, where each entry shows a floor next to the
    description of where the item was found (``0x1EF1906``);
  * plain French prose — Zygarde cells, tablets, emeralds, Trainer-Tips signs,
    item hints, the department-store directory — which kept writing ``B1F`` /
    ``3F`` inside otherwise French sentences.

Unit tests pin each of those individually. This suite takes the player's point
of view instead: it sweeps the whole built artifact and fails if *any* live
pointer resolves to an English floor label, or if any reachable French text
still spells one out. That is the check none of the earlier rounds performed,
and it is what keeps the issue from being reopened a fourth time.

Needs the built ROM (``output/roms/GenedRom-fr.gba``); marked ``rom``.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder, TextEncoder

REPO_ROOT = Path(__file__).resolve().parents[3]
FR_ROM = REPO_ROOT / "output/roms/GenedRom-fr.gba"
GBA_BASE = 0x08000000

# Every English spelling Unbound uses for a floor.
ENGLISH_FLOORS = (
    [f"{n}F" for n in range(1, 12)]
    + [f"B{n}F" for n in range(1, 5)]
    + [f"F{n}" for n in range(1, 6)]
)

# Floor tokens as they appear *inside* a sentence. `\n`/`\l`/`\p` are decoded to
# real control characters here, so a plain word-boundary check is enough.
_PROSE_TOKEN = re.compile(r"(?<![A-Za-z0-9])(?:B[1-4]F|(?:[1-9]|1[01])F)(?![A-Za-z0-9])")

# French text is what we sweep for prose residue: a string is considered French
# when it carries an accent or a French-only function word. Sweeping *every*
# string would flag the untouched English source strings the ROM still carries
# for unshipped content.
_FRENCH_HINT = re.compile(
    r"[éèêëàâçùûüîïôœÉÈÊÀÂÇÎÔ]|\b(?:le|la|les|des|une|dans|près|trouvée?|au|du)\b"
)

pytestmark = pytest.mark.rom


@pytest.fixture(scope="module")
def rom() -> bytes:
    if not FR_ROM.exists():
        pytest.skip("built FR ROM not present")
    return FR_ROM.read_bytes()


def _decode_at(rom: bytes, offset: int, limit: int = 400) -> str:
    if not 0 <= offset < len(rom):
        return ""
    chunk = rom[offset : offset + limit]
    end = chunk.find(b"\xFF")
    raw = chunk if end == -1 else chunk[: end + 1]
    try:
        return TextDecoder.decode_pokemon(raw, preserve_unknown=True)
    except Exception:  # undecodable bytes are not player-visible text
        return ""


def _encode(label: str) -> bytes:
    encoded = TextEncoder.encode_pokemon(label)
    return encoded if encoded.endswith(b"\xFF") else encoded + b"\xFF"


def _standalone_cells(rom: bytes, label: str) -> list[int]:
    """Offsets where *label* is a complete string (preceded by a terminator)."""
    needle = _encode(label)
    cells, pos = [], 0
    while True:
        hit = rom.find(needle, pos)
        if hit == -1:
            return cells
        pos = hit + 1
        if hit == 0 or rom[hit - 1] == 0xFF:
            cells.append(hit)


def _pointer_slots(rom: bytes, offset: int) -> list[int]:
    """Half-word aligned cells holding a GBA pointer to *offset*."""
    needle = struct.pack("<I", GBA_BASE + offset)
    return [m.start() for m in re.finditer(re.escape(needle), rom) if m.start() % 2 == 0]


def test_no_live_pointer_resolves_to_an_english_floor(rom: bytes):
    """The sweep that all three earlier #100 rounds were missing.

    Floor labels are always consumed as a *set* (a menu, a table, a script that
    offers several floors), so a genuine slot always has a sibling nearby. An
    isolated 4-byte run that merely happens to read as a pointer — sample and
    graphics data contains a few — is not a floor reference, and repointing it
    would corrupt unrelated bytes.
    """
    candidates = []
    for label in ENGLISH_FLOORS:
        for cell in _standalone_cells(rom, label):
            candidates += [(slot, cell, label) for slot in _pointer_slots(rom, cell)]

    addresses = {slot for slot, _cell, _label in candidates}
    offenders = [
        item
        for item in candidates
        if any(other != item[0] and abs(other - item[0]) <= 0x60 for other in addresses)
    ]

    assert not offenders, "English floor still reachable: " + ", ".join(
        f"slot {slot:#x} -> {cell:#x} ({label})" for slot, cell, label in offenders[:20]
    )


def test_no_reachable_french_sentence_spells_an_english_floor(rom: bytes):
    """Floors written inside place descriptions must follow the FR convention.

    Only *reachable* strings count: relocating a French text leaves its English
    original stranded at the old offset with no pointer left, and those orphaned
    bytes are never shown to the player.
    """
    offenders = {}
    for label in ("B1F", "B2F", "B3F", "B4F", "1F", "2F", "3F", "4F", "5F", "6F"):
        needle = TextEncoder.encode_pokemon(label).rstrip(b"\xFF")
        for match in re.finditer(re.escape(needle), rom):
            hit = match.start()
            start = hit
            while start > 0 and rom[start - 1] != 0xFF and hit - start < 400:
                start -= 1
            text = _decode_at(rom, start)
            # Undecodable bytes are graphics/sample data, not player-visible text.
            if "<0x" in text or len(text) < 12 or not _FRENCH_HINT.search(text):
                continue
            if _PROSE_TOKEN.search(text) and _pointer_slots(rom, start):
                offenders[start] = text

    assert not offenders, "French text still spelling an English floor: " + "; ".join(
        f"{offset:#x} {text[:60]!r}" for offset, text in sorted(offenders.items())[:10]
    )


def test_french_floor_labels_are_actually_reachable(rom: bytes):
    """Positive control: the French labels are wired, not merely present."""
    for label in ("RDC", "1E", "-1"):
        cells = _standalone_cells(rom, label)
        assert cells, f"French floor label {label!r} missing from the ROM"
        assert any(
            struct.pack("<I", GBA_BASE + cell) in rom for cell in cells
        ), f"French floor label {label!r} is present but unreachable"
