"""
Regression guard: the "Cinder Volcano" location name must use a single,
consistent French form — **Volcan Cendreux** — everywhere it appears.

Why this test exists
--------------------
Before standardization (ticket P-29 slice), the location surfaced under at
least six competing forms scattered across dialogue, statue lore and Region
Map signs:

    Cinder Volcano        (fully untranslated)
    Volcan Cinder         (half-translated)
    Volcan de Cinder      (Region Map sub-area)
    Volcan de Cendres     (statue warning)
    Volcan Cendre         (statue lore + Region Map signs)
    V. Cendre             (abbreviated Region Map sign)

The canonical World Map *label* (0xB503CC) was already "Volcan Cendreux"
(guarded by tests/test_location_names_fr.py::test_volcan_cendreux), but the
in-dialogue references drifted.  This test pins every living reference to the
single canonical form so a future combined_fr.txt rewrite or pipeline run can
never silently re-introduce a variant.

The decisive source of truth is ``combined_fr.txt`` (last duplicate wins).
We assert on the *living* entry for each offset, then sanity-check that the
canonical bytes actually made it into the built ROM.

Run standalone:   pytest tests/test_cinder_volcano_standardization_fr.py -v
"""

import re
import struct
import unittest
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder, TextEncoder

REPO_ROOT = Path(__file__).resolve().parent.parent
COMBINED = REPO_ROOT / "combined_fr.txt"
FR_ROM = REPO_ROOT / "output" / "roms" / "GenedRom-fr.gba"

CANONICAL = "Volcan Cendreux"

# Deviant place-name forms that must never reappear in a living entry.
# Note: ``Cendre(?!ux)`` deliberately allows the canonical "Cendreux"; the
# negative look-ahead only fires on the bare "Cendre" / "Cendres" variants.
_DEVIANT_PATTERNS = [
    re.compile(r"Cinder\s+Volcano", re.IGNORECASE),       # untranslated
    re.compile(r"Volcan\s+Cinder", re.IGNORECASE),        # half-translated
    re.compile(r"Volcan\s+de\s+Cinder", re.IGNORECASE),   # Region Map sub-area
    re.compile(r"Volcan\s+de\s+Cendres"),                 # statue warning
    re.compile(r"Volcan\s+Cendre(?!ux)"),                 # bare "Cendre"
    re.compile(r"\bV\.\s*Cendre(?!ux)"),                  # abbreviated sign
    # "Cinder Volcano" split across a CFRU line-break code (\n / \l):
    re.compile(r"Cinder\\[lnp]Volcano", re.IGNORECASE),
]


def _living_entries(text: str) -> dict:
    """Parse combined_fr.txt -> {offset_int: full_line_text}, last wins."""
    entries = {}
    for line in text.splitlines():
        m = re.match(r"\s*0x([0-9A-Fa-f]+):(.*)", line)
        if not m:
            continue
        entries[int(m.group(1), 16)] = m.group(2)
    return entries


class TestCinderVolcanoStandardizationFR(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.combined = COMBINED.read_text(encoding="utf-8")
        cls.entries = _living_entries(cls.combined)

    def test_no_variant_in_any_living_entry(self):
        """No living combined_fr.txt entry keeps a non-canonical Cinder form."""
        offenders = []
        for offset, body in self.entries.items():
            for pat in _DEVIANT_PATTERNS:
                m = pat.search(body)
                if m:
                    offenders.append((hex(offset), m.group(0), body.strip()[:80]))
        self.assertEqual(
            offenders,
            [],
            "Non-canonical Cinder Volcano variants still present in "
            f"living entries (expected only {CANONICAL!r}):\n"
            + "\n".join(f"  {o[0]}: matched {o[1]!r} in {o[2]!r}" for o in offenders),
        )

    def test_canonical_form_is_used(self):
        """The canonical form is present (sanity: standardization happened)."""
        # Contiguous occurrences only; line-break-split ones are covered above.
        count = self.combined.count(CANONICAL)
        self.assertGreaterEqual(
            count,
            10,
            f"Expected the canonical {CANONICAL!r} to dominate, found {count}",
        )


@pytest.mark.rom
class TestCinderVolcanoInBuiltROM(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not FR_ROM.exists():
            raise unittest.SkipTest(f"FR ROM not found: {FR_ROM}")
        cls.rom = FR_ROM.read_bytes()

    def test_canonical_bytes_present(self):
        """Encoded 'Volcan Cendreux' bytes were injected into the FR ROM."""
        needle = TextEncoder.encode_pokemon(CANONICAL).rstrip(b"\xff")
        self.assertIn(
            needle,
            self.rom,
            "Canonical 'Volcan Cendreux' bytes not found in built FR ROM",
        )

    def test_no_live_pointer_to_english_dialogue(self):
        """No active GBA pointer reaches a dead English 'Cinder Volcano' dialogue.

        The FR build patches the EN ROM: when the French string is longer than
        the English original it is relocated to free space and the script
        pointer is repointed, leaving the original English bytes physically in
        place but **unreferenced**.  This guards that every standardized
        dialogue/lore/sign reference is reached only by its relocated French
        copy — never by a live pointer to the leftover English bytes.

        Known out-of-scope exception: the in-game area banner 'Cinder Volcano
        West' (0x78D7C8) lives in a map-name region that is NOT driven by
        combined_fr.txt and whose sibling banners ('Grim Woods', 'Crater Town')
        are likewise still English.  Translating that table belongs to the
        broader P-29 map-name work, not to variant standardization, so it is
        explicitly allowed here.
        """
        base = 0x08000000
        rom = self.rom
        needle = TextEncoder.encode_pokemon("Cinder Volcano").rstrip(b"\xff")
        west = TextEncoder.encode_pokemon("Cinder Volcano West").rstrip(b"\xff")

        offending = []
        pos = 0
        while True:
            p = rom.find(needle, pos)
            if p == -1:
                break
            pos = p + 1
            # Allow the out-of-scope 'Cinder Volcano West' map banner.
            if rom[p : p + len(west)] == west:
                continue
            # Scan back to the string start (byte after previous terminator).
            start = p
            while start > 0 and rom[start - 1] != 0xFF:
                start -= 1
            if rom.count(struct.pack("<I", start + base)) > 0:
                end = rom.find(b"\xff", start)
                txt = TextDecoder.decode_pokemon(
                    rom[start : end + 1], preserve_unknown=True
                )
                offending.append((hex(start), txt[:60]))

        self.assertEqual(
            offending,
            [],
            "Live pointer(s) still reach untranslated 'Cinder Volcano' "
            f"dialogue (engine would show English):\n{offending}",
        )


if __name__ == "__main__":
    unittest.main()
