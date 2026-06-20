"""
Build-independent unit tests for the "Prison Bottle" / "Prison Stone" key-item
references in ``combined_fr.txt``.

Why a *source-level* test (no ROM required)
-------------------------------------------
The story dialogue repeatedly names two plot items — the *Prison Bottle* and the
*Prison Stone* — whose canonical French forms are **"Bouteille Prison"** and
**"Pierre Prison"**. These strings live in ``combined_fr.txt`` (the source of
truth) and reach the ROM through the build pipeline.

What they guard against
-----------------------
``combined_fr.txt`` has ~957 duplicated offsets where **the last entry wins**
(the lowercase block at the bottom of the file is the live one). A later
duplicate that kept the raw English term silently reverts the visible dialogue:

* ticket P-61  — offset ``0x1f3a061`` kept ``Prison Stone`` over the translated
  ``Pierre Prison`` of an earlier duplicate;
* this ticket  — offset ``0x1f3a9f2`` kept ``Prison Bottle`` over the translated
  ``Bouteille Prison`` of an earlier duplicate.

These assertions read the source file directly (last-wins), so any future
regenerate-from-scratch that resurrects an English term is caught in the fast
unit profile — before a rebuild, on any machine, with no ROM or mGBA.

Run standalone:  pytest tests/test_prison_terms_combined_fr.py -v
Fast profile:    python3 -m pytest tests/ -m "not slow and not stress and not emulator"
"""

import re
from pathlib import Path

import pytest

# combined_fr.txt lives at the repository root, next to the Makefile.
COMBINED_FR = Path(__file__).resolve().parent.parent / "combined_fr.txt"

# Line format: "0x<hex offset>: <French text>"  (text may contain ': ' itself)
_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")


def _load_last_wins() -> dict[int, str]:
    """Parse combined_fr.txt into {offset:int -> French text}, last entry wins.

    Offsets are case-insensitive and zero-padding-insensitive (0x1F3A9F2 and
    0x01f3a9f2 are the same key), mirroring the build pipeline's normalization.
    """
    mapping: dict[int, str] = {}
    with COMBINED_FR.open("r", encoding="utf-8", newline="") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            m = _LINE_RE.match(line)
            if not m:
                continue
            offset = int(m.group(1), 16)
            mapping[offset] = m.group(2)  # later occurrence overwrites earlier
    return mapping


# (offset, expected French substring, banned English term) for the specific
# dialogue lines whose live value was — or could be — reverted to English.
PRISON_DIALOGUE = [
    # P-61 (Prison Stone)
    (0x1F3A061, "Prison Stone",  "Pierre Prison"),
    # This ticket (Prison Bottle)
    (0x1F3A9F2, "Prison Bottle", "Bouteille Prison"),
]

# English terms that must never be the live value of *any* offset. These are the
# raw in-game item names; once translated they should never resurface.
BANNED_ENGLISH_TERMS = ("Prison Bottle", "Prison Stone")


@pytest.fixture(scope="module")
def combined() -> dict[int, str]:
    if not COMBINED_FR.is_file():
        pytest.fail(f"Source of truth not found: {COMBINED_FR}")
    return _load_last_wins()


class TestPrisonTermsCombinedFR:
    """The plot-item names must resolve to their French forms, never English."""

    def test_source_file_exists_and_parses(self, combined):
        """Sanity: combined_fr.txt parses into a non-trivial offset map."""
        assert len(combined) > 1000, (
            f"Parsed only {len(combined)} offsets from {COMBINED_FR.name}; "
            "the file format may have changed."
        )

    @pytest.mark.parametrize(
        "offset, banned_en, expected_fr",
        PRISON_DIALOGUE,
        ids=[f"{o:07X}:{en}" for (o, en, _fr) in PRISON_DIALOGUE],
    )
    def test_dialogue_uses_french_term(self, combined, offset, banned_en, expected_fr):
        """Last-wins value carries the French term, not the English one."""
        assert offset in combined, (
            f"Offset 0x{offset:07X} is missing from combined_fr.txt — "
            "the dialogue entry was dropped."
        )
        actual = combined[offset]
        assert banned_en not in actual, (
            f"Offset 0x{offset:07X} still contains the English term "
            f"{banned_en!r} (a later duplicate overwrote the translated entry): "
            f"{actual!r}"
        )
        assert expected_fr in actual, (
            f"Offset 0x{offset:07X} should contain {expected_fr!r}; got {actual!r}"
        )

    def test_no_english_prison_term_is_live_anywhere(self, combined):
        """No live (last-wins) entry may keep a raw English Prison item name."""
        offenders = {
            f"0x{off:07X}": text
            for off, text in combined.items()
            if any(term in text for term in BANNED_ENGLISH_TERMS)
        }
        assert not offenders, (
            "Untranslated English Prison item name(s) found as the live value:\n"
            + "\n".join(f"  {k}: {v!r}" for k, v in offenders.items())
        )


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
