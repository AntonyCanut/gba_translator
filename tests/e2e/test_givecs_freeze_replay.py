"""End-to-end replay guard for the give-CS freeze (ticket « Problème pas de
gain d'objet »).

This is the "on this sequence" test the ticket asks for: it loads the user's
savestate taken just before the post-Zeph kidnapping cutscene
(``tests/fixtures/saves/givecs_freeze.ss9``) into the freshly built French ROM
and mashes A through the whole cutscene up to and past the give-CS box
« Alors, prends cette CS pour aller le voir. ». On a buggy build the field-move
description word-wrap spins forever and the screen stops changing; this test
asserts the sequence reaches the give-CS map and never stalls.

It drives mGBA headlessly through the toolkit's full-featured EmulatorBridge
(``Test/Unbound/src/cooker/emulator.py``), which lives in the sibling toolkit
repo. The test skips cleanly when mGBA, the bridge, or the ROM is unavailable
(so it is a no-op in headless CI) — the deterministic CI guard is the static
``test_givecs_move_desc_freeze.py``. Point ``UNBOUND_TOOLKIT`` at the toolkit
checkout to run it locally.
"""

from __future__ import annotations

import importlib.util
import os
import pathlib
import sys
import time

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
FR_ROM_PATH = PROJECT_ROOT / "output" / "roms" / "GenedRom-fr.gba"
SAVESTATE = PROJECT_ROOT / "tests" / "fixtures" / "saves" / "givecs_freeze.ss9"

# Unbound RAM addresses (verified for this build, not FireRed-US defaults).
ADDR_MAP_GROUP = 0x02031DBC
ADDR_MAP_NUMBER = 0x02031DBD
GIVE_CS_MAP = (46, 0)  # the field map where the hillbilly hands over the CS

KEY_A = 0
MAX_PRESSES = 420
STALL_ITERS = 30  # consecutive A-presses with no VRAM change => frozen


def _load_emulator_bridge():
    """Import EmulatorBridge from the sibling toolkit repo, or skip."""
    candidates = []
    env = os.environ.get("UNBOUND_TOOLKIT")
    if env:
        candidates.append(pathlib.Path(env))
    candidates += [
        PROJECT_ROOT.parent / "Unbound",
        PROJECT_ROOT.parent.parent / "Test" / "Unbound",
    ]
    for root in candidates:
        mod = root / "src" / "cooker" / "emulator.py"
        if mod.exists():
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            spec = importlib.util.spec_from_file_location("unbound_cooker_emulator", mod)
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except Exception as exc:  # pragma: no cover - environment dependent
                pytest.skip(f"toolkit EmulatorBridge import failed: {exc}")
            return module.EmulatorBridge
    pytest.skip("toolkit EmulatorBridge not found (set UNBOUND_TOOLKIT)")


@pytest.mark.slow
def test_give_cs_sequence_does_not_freeze():
    if not FR_ROM_PATH.exists():
        pytest.skip("GenedRom-fr.gba not found (run `make build-fr`)")
    if not SAVESTATE.exists():
        pytest.skip("givecs_freeze.ss9 fixture not found")

    EmulatorBridge = _load_emulator_bridge()
    bridge = EmulatorBridge()
    try:
        try:
            bridge.start(str(FR_ROM_PATH), headless=True)
        except Exception as exc:
            pytest.skip(f"mGBA could not start: {exc}")
        time.sleep(1)
        bridge.load_state(str(SAVESTATE))
        bridge.advance_frames(2)

        last_hash = None
        stall = 0
        reached_give_cs = False
        for _ in range(MAX_PRESSES):
            bridge.press_key(KEY_A, frames=2)
            bridge.advance_frames(10)
            if (bridge.read_u8(ADDR_MAP_GROUP), bridge.read_u8(ADDR_MAP_NUMBER)) == GIVE_CS_MAP:
                reached_give_cs = True
            vram = bridge.get_vram_hash()
            if vram == last_hash:
                stall += 1
            else:
                stall = 0
                last_hash = vram
            if stall >= STALL_ITERS:
                pytest.fail(
                    "give-CS sequence froze: screen unchanged for "
                    f"{stall} A-presses on map "
                    f"{bridge.read_u8(ADDR_MAP_GROUP)}.{bridge.read_u8(ADDR_MAP_NUMBER)} "
                    "(word-wrap spinning on an unterminated move description)"
                )

        assert reached_give_cs, (
            "replay never reached the give-CS map "
            f"{GIVE_CS_MAP[0]}.{GIVE_CS_MAP[1]} — cutscene did not progress"
        )
    finally:
        try:
            bridge.stop()
        except Exception:
            pass
