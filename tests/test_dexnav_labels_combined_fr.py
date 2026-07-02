"""
Build-independent unit tests for DexNav habitat/method/UI labels in
``combined_fr.txt``.

Context
-------
The DexNav screen (route encounter tracker) shows several short pointer-based
strings — habitat tabs ("Water"/"Land"), terrain names ("Sand", "Reeds"...),
encounter methods ("Old Rod", "Surf/Good Rod"...), the chain counter, and the
Register/Scan/Cancel button prompts. These were entirely untranslated
(English) because they were simply missing (or still English) in
``combined_fr.txt``. See ticket "Manque traduction DexNav".

Note: the header column titles visible on the same screen ("SEARCH LEVEL",
"METHOD", "HIDDEN ABILITY", "HELD ITEMS") are baked into the DexNavBG.png
background graphic upstream in CFRU, not pointer text — they are out of scope
for this source-level test (tracked separately as a graphics-patch follow-up).

Like ``tests/test_location_names_combined_fr.py``, this test reads the source
of truth directly so a silent revert (e.g. a future bulk regeneration of
``combined_fr.txt``) is caught before a rebuild ever happens.
"""

import re
from pathlib import Path

import pytest

COMBINED_FR = Path(__file__).resolve().parent.parent / "languages/fr/combined_fr.txt"

_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")


def _load_last_wins() -> dict[int, str]:
    mapping: dict[int, str] = {}
    with COMBINED_FR.open("r", encoding="utf-8", newline="") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            m = _LINE_RE.match(line)
            if not m:
                continue
            offset = int(m.group(1), 16)
            mapping[offset] = m.group(2)
    return mapping


# (offset, expected_fr, english_name)
DEXNAV_LABELS = [
    (0xA439B0, "Eau", "Water"),
    (0xA439B6, "Terre", "Land"),
    (0xA439BB, "Fleurs roses", "Pink Flowers"),
    (0xA439C8, "Fleurs jaunes", "Yellow Flowers"),
    (0xA439D7, "Fleurs rouges", "Red Flowers"),
    (0xA439E3, "Fleurs bleues", "Blue Flowers"),
    (0xA439F0, "Fleurs rose-violet", "Pink-Purple Flowers"),
    (0xA43A04, "Fleurs bleu-jaune", "Blue-Yellow Flowers"),
    (0xA43A1E, "Sable", "Sand"),
    (0xA43A23, "Roseaux", "Reeds"),
    (0xA43A29, "Eau profonde", "Deep Water"),
    (0xA43A34, "Chaîne :", "Chain:"),
    (0xA43A4B, "À pied", "Walk"),
    (0xA43A55, "Surf sur lave", "Lava Surf"),
    (0xA43A5F, "Canne rouillée", "Old Rod"),
    (0xA43A67, "Bonne canne", "Good Rod"),
    (0xA43A70, "Super canne", "Super Rod"),
    (0xA43A7A, "Surf/Canne rouillée", "Surf/Old Rod"),
    (0xA43A87, "Surf/Bonne canne", "Surf/Good Rod"),
    (0xA43A95, "Surf/Super canne", "Surf/Super Rod"),
    (0xA43AA4, "Horde", "Swarm"),
    (0xA43AB3, "Indisponible", "Unavailable"),
    (0xA43ABF, "Enregistrer", "Register"),
    (0xA43AC8, "Analyser", "Scan"),
    (0xA43ACD, "Annuler", "Cancel"),
]


@pytest.fixture(scope="module")
def combined() -> dict[int, str]:
    if not COMBINED_FR.is_file():
        pytest.fail(f"Source of truth not found: {COMBINED_FR}")
    return _load_last_wins()


class TestDexNavLabelsCombinedFR:
    """Every DexNav habitat/method/UI label must resolve to its French text."""

    @pytest.mark.parametrize(
        "offset, expected_fr, en_name",
        DEXNAV_LABELS,
        ids=[en for (_o, _fr, en) in DEXNAV_LABELS],
    )
    def test_label_translation_matches(self, combined, offset, expected_fr, en_name):
        assert offset in combined, (
            f"Offset 0x{offset:06X} [{en_name}] is missing from combined_fr.txt — "
            "the DexNav label entry was dropped."
        )
        actual = combined[offset].strip()
        assert actual == expected_fr, (
            f"Label 0x{offset:06X} [{en_name}]: expected {expected_fr!r}, "
            f"got {actual!r} (a fix script or rewrite likely overwrote the live entry)."
        )
