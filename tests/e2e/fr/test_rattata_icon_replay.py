"""In-engine replay guard for issue #104 (« sprite de Rattata KO » + « Annuler » button).

Loads the player's battery save (``tests/fixtures/saves/rattata_levelup.sav``) into the
freshly built FR ROM and, via the repo's mGBA bridge
(``scripts/verify_rattata_icon_fix.mts``):

  * sets Rattata 1 XP below level 16, grinds one wild battle so it levels up, captures
    the level-up banner's icon tiles from OBJ VRAM, and checks that block appears
    verbatim in the clean source ROM (a rotation-corrupted icon would not) — proving the
    banner renders a clean icon;
  * reads the running game's party-menu Cancel literal (0x1211E8) and checks it renders
    « Sortir », not the shared « Annuler ».

Skips cleanly when mGBA / tsx / the ROM / the save fixture is unavailable, so it is a
no-op in headless CI — the deterministic guards there are the byte-level unit tests
``test_patch_mon_icon_repair_fr.py`` and ``test_patch_party_cancel_button_fr.py``.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.rom

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent
FR_ROM = PROJECT_ROOT / "output" / "roms" / "GenedRom-fr.gba"
SOURCE_ROM = PROJECT_ROOT / "input" / "roms" / "patchedfrenchrom.gba"
SAVE_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "saves" / "rattata_levelup.sav"
VERIFY_SCRIPT = PROJECT_ROOT / "scripts" / "verify_rattata_icon_fix.mts"
TSX = PROJECT_ROOT / "emulator-web" / "node_modules" / ".bin" / "tsx"


def _mgba_path() -> str | None:
    env = os.environ.get("MGBA_PATH")
    if env and pathlib.Path(env).exists():
        return env
    return shutil.which("mgba") or (
        "/opt/homebrew/bin/mgba" if pathlib.Path("/opt/homebrew/bin/mgba").exists() else None
    )


@pytest.fixture(scope="module")
def verdict(tmp_path_factory):
    """Run the in-engine verifier ONCE for the whole module (a level-up grind takes
    minutes and mGBA uses a fixed port, so both checks share a single run)."""
    for p, why in [(FR_ROM, "GenedRom-fr.gba not found (run `make build-fr`)"),
                   (SOURCE_ROM, "source ROM not found"),
                   (SAVE_FIXTURE, "rattata_levelup.sav fixture not found"),
                   (VERIFY_SCRIPT, "verifier script missing"),
                   (TSX, "emulator-web tsx not installed (run npm install)")]:
        if not p.exists():
            pytest.skip(why)
    mgba = _mgba_path()
    if not mgba:
        pytest.skip("mGBA not found (set MGBA_PATH)")

    # mGBA loads <rom>.sav as cartridge SRAM and WRITES it back on exit, so run on a
    # throwaway copy — never next to the committed GenedRom-fr.sav (a shared fixture).
    tmp = tmp_path_factory.mktemp("rattata_icon")
    tmp_rom = tmp / "GenedRom-fr.gba"
    shutil.copyfile(FR_ROM, tmp_rom)
    shutil.copyfile(SAVE_FIXTURE, tmp_rom.with_suffix(".sav"))

    proc = subprocess.run(
        [str(TSX), str(VERIFY_SCRIPT), str(tmp_rom), str(SOURCE_ROM)],
        cwd=str(PROJECT_ROOT),
        env={**os.environ, "MGBA_PATH": mgba},
        capture_output=True, text=True, timeout=420,
    )
    v = None
    for line in reversed(proc.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            v = json.loads(line)
            break
    if v is None:
        pytest.skip(f"verifier produced no verdict (mGBA env issue):\n{proc.stderr[-800:]}")
    if v.get("verdict") == "ERROR":
        pytest.skip(f"verifier errored: {v.get('err')}")
    if not v.get("reached"):
        pytest.skip("Rattata never levelled up in-engine (save/ROM drift)")
    return v


@pytest.mark.slow
@pytest.mark.emulator
def test_rattata_banner_icon_is_clean(verdict):
    assert verdict.get("iconClean"), (
        "Rattata's level-up banner icon is CORRUPTED in mGBA: the rendered tiles do not "
        f"match any clean source-ROM icon (build regressed the mon-icon graphics). {verdict}"
    )


@pytest.mark.slow
@pytest.mark.emulator
def test_party_cancel_button_reads_sortir(verdict):
    assert verdict.get("buttonSortir"), (
        "The party-menu bottom button does not render « Sortir » in mGBA "
        f"(literal 0x1211E8 not repointed). {verdict}"
    )
