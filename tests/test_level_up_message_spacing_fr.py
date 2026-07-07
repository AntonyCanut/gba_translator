"""
Regression guard for GitHub issue #66 (follow-up): the level marker « N. »
must never have a literal space glued in front of the dynamic level value.

The original issue #5/#66 fix covered the Résumé header and the "met in the
wild" memo (``summary_lv_labels.py``, dynamic level inserted via the ``<0xF7>``
control code). This follow-up report ("shadow of the number not visible,
maybe add a space") turned out to be the exact same bug class in a different
family of strings: the CFRU evolution-condition / level-up flavour text
("Il monte au N. {STR_VAR_2} !", "Il évolue au N. {STR_VAR_2} !", the GTS
trade-negotiation screen, the Day-Care Lucky Egg dialogue, and the Macho
Brace / Power Item upgrade dialogues). These use the ``<0xFD><0x03>``
buffer-var control code instead of ``<0xF7>``, so the original
``summary_lv_labels.py::_patch_memos`` pattern (which only matches
``<0xF7>``) never touched them.

Unlike the original bug, this one lives directly in ``combined_fr.txt`` as a
plain literal space between "N." and the ``{STR_VAR_2}``/``{DYNAMIC}``/``{LV}``
placeholder (no positional-token constraint applies here — removing a plain
space byte does not shift which English control sequence a later ``{token}``
consumes), so the fix is a straight source-text edit rather than a
post-build binary patch.

Run standalone:   pytest tests/test_level_up_message_spacing_fr.py -v
Run via Makefile: make test-rom
"""

from pathlib import Path

import pytest

FR_ROM = Path("output/roms/GenedRom-fr.gba")

# The buggy shape: "N." (0xC8 0xAD) + literal space (0x00) + the dynamic
# level buffer-var control code (0xFD 0x03). Must never occur in the built
# ROM.
BUGGY_PATTERN = bytes.fromhex("c8ad00fd03")

# The fixed shape: "N." glued directly onto the dynamic level buffer-var,
# no space in between. At least one known site must show this.
FIXED_PATTERN = bytes.fromhex("c8adfd03")


@pytest.mark.rom
@pytest.mark.skipif(not FR_ROM.exists(), reason="FR ROM not built")
class TestLevelUpMessageSpacingFr:
    @classmethod
    def setup_class(cls):
        cls.rom = FR_ROM.read_bytes()

    def test_no_space_between_n_and_dynamic_level(self):
        idx = self.rom.find(BUGGY_PATTERN)
        assert idx == -1, (
            f"found 'N. ' + space + dynamic level at 0x{idx:07X} — "
            "the level digits will render shifted right (issue #66 follow-up)"
        )

    def test_fixed_pattern_present(self):
        assert FIXED_PATTERN in self.rom, (
            "expected at least one 'Il monte au N.<LEVEL>' style site with no "
            "space between the marker and the dynamic level"
        )
