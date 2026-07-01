"""E2E: comprehensive verification of every P-29 location name *in game*.

Parent ticket **P-29 — Noms des lieux** lists location names that are wrong or
untranslated on the world map, in zone-name pop-ups, and in dialogue.  Earlier
slices fixed parts of this:

  * B-52 recovered the toponyms ``c7c1ede`` had silently reverted.
  * B-51 standardised every ``Cinder Volcano`` reference to ``Volcan Cendré``.
  * The World-Map *label* table (0x72xxxx / 0xB5xxxx) was translated and is
    guarded by ``tests/test_location_names_fr.py`` (byte read at the label
    offset).

This suite is the **e2e slice (T-25)**.  It does not trust a single storage
offset — it reads the built FR ROM the way the **engine** does and proves that
for every P-29 location the player can only ever *see* French:

  1. ``test_worldmap_label_renders_french`` — the Region-Map label table renders
     the canonical French name (world-map screen).
  2. ``test_canonical_french_name_is_pointer_reachable`` — the canonical French
     name is wired into the Region/Town-Map name tables via at least one live
     GBA pointer (so the zone-name pop-up / fly menu actually shows it).
  3. ``test_no_live_pointer_reaches_english_form`` — the comprehensive sweep:
     *nowhere* in the ROM may an active pointer resolve to a standalone English
     form of a P-29 name.  Orphaned English bytes left behind by relocation are
     fine; only **reachable** ones are bugs.  This generalises B-52's
     Thundercap/Dehara guards to the whole P-29 list and is what catches the
     untranslated zone-name strings (Icy Hole, Polder Town, Newmoon Island,
     Dehara City, Pokémon Day Care, Fallshore City).
  4. ``test_all_p29_items_are_covered`` — the dataset covers every bullet of the
     parent ticket, so the suite can't silently drift out of sync with P-29.

Run standalone:   pytest tests/e2e/test_location_names_e2e.py -v
Needs the built ROM (``output/roms/GenedRom-fr.gba``); marked ``rom``.

Scope note — the in-game *fly banner* table at 0x78D7xx (``Bellin Town``,
``Crater Town``, ``Blizzard City``, ``Tehl Town``, ``Cinder Volcano West`` …) is
almost entirely English and is explicitly **out of scope** here, per B-51's
note ("broader P-29 map-name work").  Only the P-29-listed names are asserted;
exact standalone matching means partial banners like ``Cinder Volcano West`` are
not mistaken for a P-29 ``Cinder Volcano`` violation.
"""

import struct
import unittest
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder, TextEncoder

FR_ROM = Path("output/roms/GenedRom-fr.gba")
GBA_BASE = 0x08000000


def _decode_at(rom: bytes, offset: int, limit: int = 200) -> str:
    chunk = rom[offset : offset + limit]
    end = chunk.find(b"\xff")
    raw = chunk if end == -1 else chunk[: end + 1]
    return TextDecoder.decode_pokemon(raw, preserve_unknown=True)


def _find_all(rom: bytes, needle: bytes) -> list:
    out, pos = [], 0
    while True:
        p = rom.find(needle, pos)
        if p == -1:
            break
        out.append(p)
        pos = p + 1
    return out


def _pointer_count(rom: bytes, offset: int) -> int:
    """How many 32-bit LE pointers in the ROM target ``offset``."""
    return rom.count(struct.pack("<I", offset + GBA_BASE))


def _reachable_standalone(rom: bytes, text: str) -> list:
    """Offsets where ``text`` is a *standalone* 0xFF-terminated string AND is
    targeted by at least one live GBA pointer.

    Standalone == the decoded string from that offset equals ``text`` exactly,
    so substrings inside longer strings (e.g. "Cinder Volcano West", or
    "Rive-d'Automne" inside "Ville de Fallshore") never trigger a false positive.
    """
    enc = TextEncoder.encode_pokemon(text)
    hits = []
    for p in _find_all(rom, enc):
        if _decode_at(rom, p).rstrip() != text:
            continue
        n = _pointer_count(rom, p)
        if n > 0:
            hits.append((hex(p), n))
    return hits


# ── P-29 dataset ──────────────────────────────────────────────────────────────
# (label_id, canonical_fr, [forbidden English standalone forms],
#  worldmap_offset, pointer_reachable)
#
# `worldmap_offset` (Region-Map label table) is given where one exists so the
# label test can read it directly; `pointer_reachable` marks names that are
# wired into the Region/Town-Map name tables via pointers (zone pop-up / fly
# menu).
P29_LOCATIONS = [
    # english bullet,     fr_canon,            english_forms,                             worldmap_off, ptr
    ("Icy Hole",          "Gouffre Gelé",           ["Icy Hole"],                              0x721304,     True),
    ("ourg Gurum (B)",    "Gurenbourg",       [],                                        0xB500A0,     False),
    ("Fullmoon Island",   "Île Pleinelune",     ["Fullmoon Island"],                       0xB535C8,     False),
    ("Newmoon Island",    "Île Nouvellune",     ["Newmoon Island"],                        0xB531D8,     True),
    ("Glimmer Island",    "Île Scintillante",  ["Glimmer Isle", "Glimmer Island"],        0x7214E8,     False),
    ("Polder Town",       "Polderive",            ["Polder Town"],                           0xB522A4,     True),
    ("Redwood Village",   "Rougebois",        ["Redwood Village"],                       0xB537AC,     False),
    ("Antisis Sewers",    "Égouts d'Antésia",  ["Antisis Sewers"],                        0xB50214,     True),
    ("Thundercap Mt.",    "Mont Foudroyant",["Thundercap Mt.", "Thundercap"],          0xB5026C,     True),
    ("Epidimy Town",      "Épidia",    ["Epidimy Town"],                          0x721968,     True),
    ("Fallshore City",    "Rivapolis",              ["Fallshore City", "Ville de Fallshore"],  0x720E74,     True),
    ("Dehara City",       "Daherapolis",            ["Dehara City", "Ville de Dehara"],        0xB514E4,     True),
    ("Cinder Volcano",    "Volcan Cendré",     ["Cinder Volcano"],                        0xB503CC,     True),
    ("Pokemon Day Care",  "Pension Pokémon",   ["Pokemon Day Care", "Pokémon Day Care"],  0xB52274,     True),
]

_LABELS = [(loc[1], loc[3]) for loc in P29_LOCATIONS]
_POINTER_NAMES = [loc[1] for loc in P29_LOCATIONS if loc[4]]
_ENGLISH_FORMS = [(loc[1], form) for loc in P29_LOCATIONS for form in loc[2]]


@pytest.mark.rom
class TestP29LocationNamesE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not FR_ROM.exists():
            raise unittest.SkipTest(f"FR ROM not found: {FR_ROM}")
        cls.rom = FR_ROM.read_bytes()

    def test_worldmap_label_renders_french(self):
        """Every P-29 Region-Map label reads its canonical French name."""
        failures = []
        for fr, off in _LABELS:
            got = _decode_at(self.rom, off).strip()
            if got != fr:
                failures.append(f"0x{off:08X}: expected {fr!r}, got {got!r}")
        self.assertEqual(failures, [], "World-Map label regressions:\n" + "\n".join(failures))

    def test_canonical_french_name_is_pointer_reachable(self):
        """Each pointer-driven P-29 name is reachable by a live GBA pointer.

        Proves the French string is actually wired into the Region/Town-Map
        name tables the engine reads for the zone pop-up / fly menu — not just
        present as dead bytes somewhere.
        """
        unreachable = []
        for fr in _POINTER_NAMES:
            if not _reachable_standalone(self.rom, fr):
                unreachable.append(fr)
        self.assertEqual(
            unreachable, [],
            "Canonical French names with no live pointer (won't render in game): "
            f"{unreachable}",
        )

    def test_no_live_pointer_reaches_english_form(self):
        """No active ROM pointer may resolve to a standalone English P-29 name.

        The comprehensive in-game sweep: orphaned English bytes are tolerated,
        reachable ones are bugs.  Catches the untranslated zone-name strings.
        """
        violations = []
        for fr, form in _ENGLISH_FORMS:
            hits = _reachable_standalone(self.rom, form)
            if hits:
                violations.append(f"{form!r} (should be {fr!r}) reachable at {hits}")
        self.assertEqual(
            violations, [],
            "English location names still reachable in game:\n" + "\n".join(violations),
        )

    def test_all_p29_items_are_covered(self):
        """Guard: the dataset stays in sync with the 14 parent-ticket bullets."""
        # P-29 lists 14 distinct locations; keep this honest if the list grows.
        self.assertEqual(
            len(P29_LOCATIONS), 14,
            "P29_LOCATIONS drifted from the 14 parent-ticket bullets",
        )
        # Every entry must have a canonical French form and at least one
        # verification axis (a label offset or pointer reachability).
        for name, fr, forms, off, ptr in P29_LOCATIONS:
            self.assertTrue(fr, f"{name}: missing canonical French form")
            self.assertTrue(off or ptr, f"{name}: no verification axis")


if __name__ == "__main__":
    unittest.main()
