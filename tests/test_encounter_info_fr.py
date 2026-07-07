"""
Regression guard for the Pokémon "encounter info" memo screen (nature +
catch location + level), fixed in GitHub issue #5.

Before the fix, the standard "met in the wild" template read as a single
run with no verb and a duplicated level marker:

    Nature Hardi . Base Ombre, N. Lv 10

(stray space before the period, missing "Rencontré à", and a literal "N. "
sitting right in front of the {LV_2} level-icon control code, which already
renders the level indicator on its own). The fix in
``languages/fr/combined_fr.txt`` removes the stray space, adds the missing
verb, and drops the redundant "N. " so the icon is the only level marker.

Follow-up (B-508 « Lv » → « N. »): the level marker is a single item, but it
was the FRLG extra-symbol icon ``<0xF9><0x05>`` which draws the English « Lv ».
``languages/fr/patches/summary_lv_labels.py`` rewrites that icon in place to
the text « N. » (``C8 AD``, same length), so the memo now reads « au N. 10. ».
The expected live bytes below therefore carry ``c8ad00f7`` (« N. » + space +
level) where they used to carry ``f90500f7`` (icon + space + level).

Follow-up (issue #66): that literal space between « N. » and the level
number rendered as « N. 10 » instead of « N.10 », shifting the digits right.
``summary_lv_labels.py`` now rotates the space byte past the level-control
code and trailing period to the very end of the string (still same length,
no repointing), so the expected bytes carry ``c8adf701ad00ff`` (« N. » +
level + « . » + trailing invisible space + terminator) instead of
``c8ad00f701adff``.

Why this asserts raw bytes via the LIVE pointer, not decoded text at the
static offset
---------------------------------------------------------------------------
The corrected French text is longer than the English original it replaces,
so the build relocates it into free space and repoints every referrer (see
``test_nature_names_fr.py`` for the same "Lax" pitfall) — decoding the
original combined_fr.txt offset directly would show the untouched English
string and falsely look unfixed. Raw bytes are compared (rather than
`TextDecoder`-decoded text) because the control-code argument bytes (e.g.
the 0x00 that follows an <0xF7> buffer-select code) coincidentally map to
printable glyphs in the CFRU charmap, which would make a naive decode
misread a control code as a real character.

Run standalone:   pytest tests/test_encounter_info_fr.py -v
Run via Makefile: make test-rom
"""

import json
import struct
import unittest
from pathlib import Path

import pytest

FR_ROM = Path("output/roms/GenedRom-fr.gba")
ENGLISH_TEXTS = Path("output/extracted/extracted_texts/englishrom_texts.json")

POINTER_BASE = 0x08000000

# offset -> expected live raw bytes (hex, terminator included).
EXPECTED_BYTES = {
    0x419782: "c8d5e8e9e6d900f700adfed0ddd5001bd7dcd5e2dbd9adff",
    0x41979D: "c8d5e8e9e6d900f700adfed0ddd5001bd7dcd5e2dbd9adff",
    0x4197B8: "c8d5e8e9e6d900f700adfeccd9e2d7e3e2e8e6d900dad5e8ddd8dde5e9d900d5e9fec8adf701ad00ff",
    0x4197ED: "c8d5e8e9e6d900f700adfeccd9e2d7e3e2e8e6d900dad5e8ddd8dde5e9d900d5e9fec8adf701ad00ff",
    0x419822: "c8d5e8e9e6d900f700adfeccd9e2d7e3e2e8e61b001600f702b800d5e900c8adf701ad00ff",
    0x419841: "c8d5e8e9e6d900f700adfeccd9e2d7e3e2e8e61b001600f702b800d5e900c8adf701ad00ff",
    0x419860: "c8d5e8e9e6d900f700adfebbe4e4d5e6d9e1e1d9e2e800e6d9e2d7e3e2e8e61b001600f702b8fed5e900c8adf701ad00ff",
    0x41988A: "c8d5e8e9e6d900f700adfebbe4e4d5e6d9e1e1d9e2e800e6d9e2d7e3e2e8e61b001600f702b8fed5e900c8adf701ad00ff",
    0x4198B4: "c8d5e8e9e6d900f700adfe06d7e0e3e700f000f702fe1600c8adf701ad00ff",
    0x4198D5: "c8d5e8e9e6d900f700adfe06d7e0e3e700f000f702fe1600c8adf701ad00ff",
    0x41992F: "c8d5e8e9e6d900f700adfeccd9e2d7e3e2e8e6d900dad5e8ddd8dde5e9d9005c1bd7e0e3e700f0fef70200d5e900c8adf7015dad00ff",
    0x41996D: "c8d5e8e9e6d900f700adfeccd9e2d7e3e2e8e6d900dad5e8ddd8dde5e9d9005c1bd7e0e3e700f0fef70200d5e900c8adf7015dad00ff",
    0x4199AB: "c8d5e8e9e6d900f700ad00bbe4e4d5e6d9e1e1d9e2e8fee6d9e2d7e3e2e8e6d900dad5e8ddd8dde5e9d9005c1bd7e0e3e700f0fef70200d5e900c8adf7015dad00ff",
    0x4199F4: "c8d5e8e9e6d900f700ad00bbe4e4d5e6d9e1e1d9e2e8fee6d9e2d7e3e2e8e6d900dad5e8ddd8dde5e9d9005c1bd7e0e3e700f0fef70200d5e900c8adf7015dad00ff",
}

# "N." (0xc8 0xad) glued directly in front of the <0xF9> level-icon code —
# the redundant, doubled-up level marker from the bug report.
REDUNDANT_N_BEFORE_ICON = bytes.fromhex("c8adf9")

REPORTED_BUG_OFFSETS = (0x419822, 0x419841)


def _live_bytes_for(rom: bytes, pointer_offsets) -> set:
    """Read the raw (terminator-included) bytes every pointer resolves to."""
    blobs = set()
    for p in pointer_offsets:
        site = int(p, 16) if isinstance(p, str) else p
        ptr = struct.unpack_from("<I", rom, site)[0]
        if ptr < POINTER_BASE or ptr >= POINTER_BASE + len(rom):
            continue
        target = ptr - POINTER_BASE
        end = rom.find(b"\xff", target)
        blobs.add(bytes(rom[target : end + 1]))
    return blobs


@pytest.mark.skipif(not FR_ROM.exists(), reason="FR ROM not built")
@pytest.mark.skipif(not ENGLISH_TEXTS.exists(), reason="English extraction not built")
class TestEncounterInfoFr(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = FR_ROM.read_bytes()
        data = json.loads(ENGLISH_TEXTS.read_text(encoding="utf-8"))
        cls.by_offset = {
            t["offset"]: t
            for t in data["texts"]
            if isinstance(t.get("offset"), int)
        }

    def test_all_variants_match_expected_live_bytes(self):
        for offset, expected_hex in EXPECTED_BYTES.items():
            entry = self.by_offset.get(offset)
            self.assertIsNotNone(entry, f"0x{offset:06X} missing from English extraction")
            pointer_offsets = entry.get("pointer_offsets") or []
            self.assertTrue(pointer_offsets, f"0x{offset:06X} has no known pointer")
            blobs = _live_bytes_for(self.rom, pointer_offsets)
            expected = bytes.fromhex(expected_hex)
            self.assertEqual(
                blobs,
                {expected},
                f"0x{offset:06X}: live pointer(s) resolve to {[b.hex() for b in blobs]!r}, "
                f"expected [{expected.hex()!r}]",
            )

    def test_reported_bug_offsets_no_longer_read_as_reported(self):
        """Issue #5: no redundant 'N.' glued in front of the {LV_2}
        level-icon control code (it already renders the level marker)."""
        for offset in REPORTED_BUG_OFFSETS:
            entry = self.by_offset[offset]
            for blob in _live_bytes_for(self.rom, entry["pointer_offsets"]):
                self.assertNotIn(
                    REDUNDANT_N_BEFORE_ICON, blob,
                    f"0x{offset:06X}: redundant 'N.' before level icon in {blob.hex()!r}",
                )


if __name__ == "__main__":
    unittest.main()
