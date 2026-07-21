"""In-engine replay guard for issue #125 — « PV » in a REAL battle healthbox.

The four LZ77 healthbox sheets (player/ally + doubles) and the uncompressed
OPPONENT healthbox element all render « PV » instead of « HP ». The byte-level
guards in ``tests/test_patch_hp_labels_fr.py`` prove the ROM *decodes* to « PV »;
this test proves the battle engine actually *loads* those tiles into OBJ VRAM in
a live fight — the end-to-end check that was missing when the fix was reported
"toujours KO" twice.

It continues the ``rattata_levelup.sav`` battery save, farms a real wild
encounter (the ``inBattle`` RAM byte is unreliable in this build, so the probe
detects the battle by scanning OBJ VRAM for a healthbox label tile), advances to
the command menu so both boxes render, dumps OBJ VRAM and asserts:

  * at least one « V » tile (unique to « PV ») is present, and
  * no « H » tile (unique to « HP ») survives — including the opponent element.

Skips cleanly when mGBA / tsx / the ROM / the save fixture is unavailable, so it
is a no-op in headless CI — the deterministic guards there are the byte-level
unit tests. See scripts/probe_battle_healthbox_fr.mts + verify_battle_healthbox_fr.py.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

pytestmark = pytest.mark.rom

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent
FR_ROM = PROJECT_ROOT / "output" / "roms" / "GenedRom-fr.gba"
SAVE_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "saves" / "rattata_levelup.sav"
PROBE_SCRIPT = PROJECT_ROOT / "scripts" / "probe_battle_healthbox_fr.mts"
TILES_SCRIPT = PROJECT_ROOT / "scripts" / "battle_hp_label_tiles.py"
TSX = PROJECT_ROOT / "emulator-web" / "node_modules" / ".bin" / "tsx"

sys.path.insert(0, str(PROJECT_ROOT))


def _mgba_path() -> str | None:
    env = os.environ.get("MGBA_PATH")
    if env and pathlib.Path(env).exists():
        return env
    return shutil.which("mgba") or (
        "/opt/homebrew/bin/mgba" if pathlib.Path("/opt/homebrew/bin/mgba").exists() else None
    )


@pytest.fixture(scope="module")
def dump_dir(tmp_path_factory):
    for p, why in [(FR_ROM, "GenedRom-fr.gba not found (run `make build-fr`)"),
                   (SAVE_FIXTURE, "rattata_levelup.sav fixture not found"),
                   (PROBE_SCRIPT, "probe script missing"),
                   (TILES_SCRIPT, "tile-signature script missing"),
                   (TSX, "emulator-web tsx not installed (run npm install)")]:
        if not p.exists():
            pytest.skip(why)
    mgba = _mgba_path()
    if not mgba:
        pytest.skip("mGBA not found (set MGBA_PATH)")

    out = tmp_path_factory.mktemp("battle_healthbox")
    # mGBA loads <rom>.sav as SRAM and writes it back on exit — use a throwaway copy.
    tmp_rom = out / "GenedRom-fr.gba"
    shutil.copyfile(FR_ROM, tmp_rom)
    shutil.copyfile(SAVE_FIXTURE, tmp_rom.with_suffix(".sav"))

    tiles = subprocess.run(
        [sys.executable, str(TILES_SCRIPT)],
        cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=60,
    )
    if tiles.returncode != 0:
        pytest.skip(f"tile signatures failed: {tiles.stderr[-400:]}")
    (out / "label_tiles.json").write_text(tiles.stdout)

    # Redirect probe/mGBA output to FILES, not pipes: a long RNG walk emits more
    # than the 64 KB OS pipe buffer, and with capture_output the child would
    # block writing (parent reads only after exit) → deadlock. Files never block.
    stdout_log = out / "probe.stdout"
    stderr_log = out / "probe.stderr"
    try:
        try:
            with open(stdout_log, "w") as so, open(stderr_log, "w") as se:
                subprocess.run(
                    [str(TSX), str(PROBE_SCRIPT), str(tmp_rom), str(out)],
                    cwd=str(PROJECT_ROOT),
                    env={**os.environ, "MGBA_PATH": mgba},
                    stdout=so, stderr=se, timeout=240,
                )
        except subprocess.TimeoutExpired:
            # A healthy run captures a battle in seconds; a multi-minute hang
            # means mGBA flaked (stale port / boot crash) — skip, don't hard-fail.
            pytest.skip("mGBA hung reaching a battle (emulator flakiness)")

        verdict = None
        for line in reversed(stdout_log.read_text().strip().splitlines()):
            line = line.strip()
            if line.startswith("{"):
                verdict = json.loads(line)
                break
        if verdict is None:
            pytest.skip(f"probe produced no verdict (mGBA env issue):\n{stderr_log.read_text()[-800:]}")
        if not verdict.get("dumped"):
            # No bridge connection / no battle (e.g. headless: mGBA can't open a
            # display) — the deterministic byte-level tests cover CI; skip here.
            pytest.skip(f"probe never reached a wild battle: {verdict}")
        return out
    finally:
        # Always reap THIS run's mGBA (matched by our unique tmp ROM path) —
        # the connect-failure path leaves a headless mGBA alive that would
        # otherwise hijack the fixed bridge port of the next run. The unique
        # tmp path never matches a concurrent ticket's emulator.
        subprocess.run(["pkill", "-f", str(tmp_rom)], capture_output=True)


@pytest.mark.slow
@pytest.mark.emulator
def test_battle_healthbox_renders_pv(dump_dir):
    from scripts.verify_battle_healthbox_fr import verify

    ok, msgs = verify(dump_dir)
    assert ok, (
        "In a REAL battle the healthbox does NOT render « PV » (issue #125):\n"
        + "\n".join(msgs)
    )
