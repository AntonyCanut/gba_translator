"""
Build-independent guard for the evolution message "Quoi ? {mon} évolue !"
at 0x3FE672 (issue #118: "QQuoi ?" showed a duplicated leading letter).

Context
-------
The real string starts at 0x3FE672 and has been correctly translated in
``combined_fr.txt`` for months ("Quoi ?\n{STR_VAR_1} évolue!"). A later fix
attempt (commit 5f5b2e0c, "translate evolution message 'is evolving!' to
'évolue !'") introduced two independent regressions that both wrote a
near-duplicate translation one byte INTO the same string, at 0x3fe673
(reading "hat?..." instead of "What?..."):

1. A phantom ``combined_fr.txt`` entry at ``0x3fe673``, picked up by the
   no-pointer in-place fallback and written directly over the real string.
2. A dedicated post-build patch script, ``scripts/patch_evolution_message_fr.py``
   (invoked unconditionally from ``make build-fr``), hardcoding the same
   wrong offset and bytes.

Writing "Quoi ..." starting one byte after the real string's own leading
"Q" produced "QQuoi ?" in the built ROM. Both sources have been removed;
this test guards against either one reappearing.

Run standalone:  pytest tests/test_evolution_message_fr.py -v
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMBINED_FR = REPO_ROOT / "languages/fr/combined_fr.txt"
MAKEFILE = REPO_ROOT / "Makefile"
DEAD_SCRIPT = REPO_ROOT / "scripts/patch_evolution_message_fr.py"
_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")

REAL_OFFSET = 0x3FE672
PHANTOM_OFFSET = 0x3FE673


def _load_last_wins() -> dict:
    """Parse combined_fr.txt into {offset:int -> French text}, last entry wins."""
    mapping = {}
    with COMBINED_FR.open("r", encoding="utf-8", newline="") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            m = _LINE_RE.match(line)
            if not m:
                continue
            mapping[int(m.group(1), 16)] = m.group(2)
    return mapping


def test_real_evolution_message_present_and_clean():
    live = _load_last_wins()
    assert REAL_OFFSET in live, "0x3FE672 (evolution message) missing from combined_fr.txt"
    text = live[REAL_OFFSET]
    assert text.startswith("Quoi"), f"0x3FE672 must start with 'Quoi', got: {text!r}"
    assert "QQuoi" not in text


def test_no_phantom_offset_one_byte_into_real_string():
    """0x3fe673 is one byte into the real 0x3FE672 string, not a distinct
    string. Any entry here is a phantom that overlaps and corrupts the real
    one when written in-place (no pointer to relocate it away)."""
    live = _load_last_wins()
    assert PHANTOM_OFFSET not in live, (
        f"0x3fe673 is a phantom offset (one byte into the real 0x3FE672 "
        f"evolution string) and must not be re-added to combined_fr.txt; "
        f"found: {live[PHANTOM_OFFSET]!r}"
    )


def test_dead_patch_script_not_reintroduced():
    """scripts/patch_evolution_message_fr.py hardcoded the same wrong
    offset (0x3fe673) and clobbered the real string on every build. Removed
    for good; guard against it (or its Makefile call) coming back."""
    assert not DEAD_SCRIPT.exists(), (
        "scripts/patch_evolution_message_fr.py must stay removed — it "
        "hardcoded offset 0x3fe673 and corrupted the real string at 0x3FE672"
    )
    makefile_text = MAKEFILE.read_text(encoding="utf-8")
    assert "patch_evolution_message_fr.py" not in makefile_text
