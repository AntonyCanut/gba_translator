"""E2E guard: the in-battle trainer defeat-speech template is not corrupted.

Ticket B-78 "Combats & Dialogues" — follow-up
---------------------------------------------
Winning a trainer battle flashed a nonsensical **"Mike Campeur"** (trainer name
+ an unrelated class name) where the trainer's defeat quote belongs — EN shows
"I ran out of energy to fight!", FR should show "Plus d'énergie pour me
battre !". The line also had no wait code, so it flashed by.

Mechanism: ``gBattleStringsTable[0]`` (STRINGID 0, the in-battle defeat-speech
slot) has its body at the FIXED offset 0x3FB219; the table pointer at 0x3FDF3C
is 0x083FB219 and is never repointed. Its body must be the language-neutral
control-code template ``{FD24}`` (= print the loaded lose-text). The FR pipeline
mis-encodes that buffer token (``{FD24}`` → FD1D = trainer NAME) and overflows
the tightly-packed cluster in place, so STRINGID 0 ends up reading
``{FD1D} {FD2E}`` → name + class → "Mike Campeur".

``patch_battle_string_templates_fr.py`` (wired into ``make build-fr``) restores
the EN bytes of the cluster 0x3FB219..0x3FB264, so STRINGID 0 is ``{FD24}``
again and the engine prints the FR defeat quote it loaded (verified in mGBA:
"Plus d'énergie pour me battre !<FC09>", which now also waits for a button).

A green result proves the built ROM ships the lose-text template, not the
"Mike Campeur" name+class corruption.

Run standalone:  pytest tests/e2e/test_battle_defeat_speech_template_fr.py -v
"""

from __future__ import annotations

import struct

import pytest

GBA_BASE = 0x08000000
STRINGID0_PTR_OFF = 0x3FDF3C       # gBattleStringsTable[0] entry (4-byte pointer)
STRINGID0_BODY_OFF = 0x3FB219      # in-battle trainer-defeat-speech template body
CLUSTER_END = 0x3FB265             # exclusive — start of the next (Exp-points) entry

_FD24_TEMPLATE = b"\xfd\x24\xff"               # {FD24} + terminator (correct body)
_CAMPEUR_CORRUPTION = b"\xfd\x1d\x00\xfd\x2e"  # {FD1D} space {FD2E} = "<name> <class>"


@pytest.fixture
def en_bytes(en_rom_path):
    return en_rom_path.read_bytes()


@pytest.fixture
def fr_bytes(fr_rom_path):
    return fr_rom_path.read_bytes()


def test_stringid0_pointer_is_fixed(fr_bytes):
    """The defeat-speech table entry must still point at the fixed body offset."""
    ptr = struct.unpack_from("<I", fr_bytes, STRINGID0_PTR_OFF)[0]
    assert ptr == GBA_BASE + STRINGID0_BODY_OFF, (
        f"gBattleStringsTable[0] points at 0x{ptr:08X}, expected "
        f"0x{GBA_BASE + STRINGID0_BODY_OFF:08X}"
    )


def test_defeat_speech_template_is_fd24(fr_bytes):
    """STRINGID 0 body must be the {FD24} lose-text template, not name+class."""
    body = fr_bytes[STRINGID0_BODY_OFF : STRINGID0_BODY_OFF + 3]
    assert body == _FD24_TEMPLATE, (
        f"0x3FB219 must be the {{FD24}} defeat-speech template; got {body.hex()} "
        "(the 'Mike Campeur' corruption is fd1d00fd2e...)"
    )


def test_no_mike_campeur_corruption(fr_bytes):
    """The name+class corruption pattern must be gone from STRINGID 0's slot."""
    cluster = fr_bytes[STRINGID0_BODY_OFF:CLUSTER_END]
    assert not cluster.startswith(_CAMPEUR_CORRUPTION), (
        "STRINGID 0 still starts with the {FD1D} {FD2E} (name+class) corruption "
        "that rendered as 'Mike Campeur'"
    )


def test_cluster_matches_english_layout(en_bytes, fr_bytes):
    """The control-code/switch-out cluster is language-neutral and must match EN,
    so every fixed pointer in it lands on the right string."""
    en_cluster = en_bytes[STRINGID0_BODY_OFF:CLUSTER_END]
    fr_cluster = fr_bytes[STRINGID0_BODY_OFF:CLUSTER_END]
    assert fr_cluster == en_cluster, (
        "battle-string template cluster 0x3FB219..0x3FB264 diverges from EN "
        "(it is a packed run of fixed-pointer control-code templates and would "
        "misalign if any entry changed length)"
    )
