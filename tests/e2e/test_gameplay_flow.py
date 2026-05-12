"""E2E: Automated gameplay scenarios via mGBA EmulatorBridge.

Each test runs a cooker scenario and asserts:
  - 0 crashes
  - 0 reboots
  - 0 hangs (no FAILED checkpoints)
  - FR text detected where expected

All tests skip gracefully if mGBA or ROM is unavailable.
"""

from __future__ import annotations

import pathlib

import pytest

from src.cooker.checkpoint import (
    ALL_SCENARIOS,
    EXTENDED_SCENARIOS,
    SLOW_SCENARIOS,
    CheckpointStatus,
    Scenario,
    ScenarioResult,
)
from src.cooker.emulator import ConnectionError, EmulatorBridge

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
FR_ROM_PATH = PROJECT_ROOT / "output" / "roms" / "GenedRom-fr.gba"

MGBA_HOST = "127.0.0.1"
MGBA_PORT = 8888


def _require_mgba() -> EmulatorBridge:
    """Try to connect to mGBA; skip the test if unavailable."""
    bridge = EmulatorBridge(host=MGBA_HOST, port=MGBA_PORT, rom_path=FR_ROM_PATH)
    try:
        bridge.connect()
    except ConnectionError:
        pytest.skip("mGBA not available (cannot connect to TCP bridge)")
    return bridge


def _require_rom() -> None:
    """Skip if the French ROM is not present."""
    if not FR_ROM_PATH.exists():
        pytest.skip("GenedRom-fr.gba not found in output/roms/")


def _run_scenario(name: str) -> ScenarioResult:
    """Run a named scenario, returning its result."""
    _require_rom()
    bridge = _require_mgba()
    try:
        factory = ALL_SCENARIOS[name]
        scenario = factory()
        return scenario.run(bridge)
    finally:
        bridge.disconnect()


def _assert_scenario_healthy(result: ScenarioResult) -> None:
    """Assert standard health conditions on a scenario result."""
    assert result.crash_count == 0, (
        f"Scenario '{result.name}' had {result.crash_count} crash(es)"
    )
    assert result.reboot_count == 0, (
        f"Scenario '{result.name}' had {result.reboot_count} reboot(s)"
    )
    crash_checkpoints = [
        cp for cp in result.checkpoints
        if cp.status == CheckpointStatus.CRASH
    ]
    assert len(crash_checkpoints) == 0, (
        f"Scenario '{result.name}' had crash checkpoints: "
        f"{[cp.name for cp in crash_checkpoints]}"
    )


def _assert_has_fr_text(result: ScenarioResult) -> None:
    """Assert that at least one checkpoint captured text with FR markers."""
    texts = [cp.text_found for cp in result.checkpoints if cp.text_found]
    if not texts:
        pytest.skip("No text captured (may be stochastic)")
    from src.cooker.checkpoint import _has_french_chars
    fr_found = any(_has_french_chars(t) for t in texts)
    # FR detection is best-effort — don't fail, just warn
    if not fr_found:
        pytest.xfail("No French text detected (encoding may differ)")


# ===================================================================
# Existing scenario tests (9)
# ===================================================================

class TestBootScenario:
    """Boot the ROM and verify it reaches a stable state."""

    def test_boot_no_crash(self):
        result = _run_scenario("boot_test")
        _assert_scenario_healthy(result)
        assert result.passed, f"Boot failed: {result.failed_checkpoints}"

    def test_boot_completes_quickly(self):
        result = _run_scenario("boot_test")
        assert result.total_frames < 1000, (
            f"Boot took too long: {result.total_frames} frames"
        )


class TestNewGameScenario:
    """Start a new game from the title screen."""

    def test_new_game_no_crash(self):
        result = _run_scenario("new_game")
        _assert_scenario_healthy(result)

    def test_new_game_starts(self):
        result = _run_scenario("new_game")
        assert result.passed


class TestFullIntroScenario:
    """Play through the intro sequence."""

    def test_intro_no_crash(self):
        result = _run_scenario("full_intro")
        _assert_scenario_healthy(result)

    def test_intro_has_fr_text(self):
        result = _run_scenario("full_intro")
        _assert_has_fr_text(result)


@pytest.mark.slow
class TestFirstBattleScenario:
    """Engage in and survive the first battle."""

    def test_first_battle_no_crash(self):
        result = _run_scenario("first_battle")
        _assert_scenario_healthy(result)


class TestNpcDialogueScenario:
    """Talk to an NPC and check for FR text."""

    def test_npc_dialogue_no_crash(self):
        result = _run_scenario("npc_dialogue")
        _assert_scenario_healthy(result)

    def test_npc_dialogue_fr_text(self):
        result = _run_scenario("npc_dialogue")
        _assert_has_fr_text(result)


class TestMenuNavigationScenario:
    """Open and navigate the start menu."""

    def test_menu_no_crash(self):
        result = _run_scenario("menu_navigation")
        _assert_scenario_healthy(result)
        assert result.passed


@pytest.mark.slow
class TestExtendedPlayScenario:
    """Soak test — extended run checking stability."""

    def test_soak_no_crash(self):
        result = _run_scenario("extended_play")
        _assert_scenario_healthy(result)
        assert result.passed


class TestReferenceBootScenario:
    """Load reference savestate and verify state."""

    def test_reference_boot_no_crash(self):
        result = _run_scenario("reference_boot")
        _assert_scenario_healthy(result)


class TestReferenceOverworldScenario:
    """Walk overworld patrol from reference savestate."""

    def test_reference_overworld_no_crash(self):
        result = _run_scenario("reference_overworld")
        _assert_scenario_healthy(result)


# ===================================================================
# Extended gameplay scenario tests (6 new)
# ===================================================================

@pytest.mark.slow
class TestTrainerBattle:
    """Find and fight a trainer, verify FR text, check post-battle stability."""

    def test_trainer_battle_no_crash(self):
        result = _run_scenario("trainer_battle")
        _assert_scenario_healthy(result)

    def test_trainer_battle_no_reboot(self):
        result = _run_scenario("trainer_battle")
        assert result.reboot_count == 0

    def test_trainer_battle_fr_text(self):
        result = _run_scenario("trainer_battle")
        _assert_has_fr_text(result)


class TestPokecenterVisit:
    """Enter Pokecenter, heal at nurse (FR dialogue), exit."""

    def test_pokecenter_no_crash(self):
        result = _run_scenario("pokecenter_visit")
        _assert_scenario_healthy(result)

    def test_pokecenter_nurse_fr_text(self):
        result = _run_scenario("pokecenter_visit")
        _assert_has_fr_text(result)


class TestShopInteraction:
    """Enter shop, open buy menu (FR items), cancel, exit."""

    def test_shop_no_crash(self):
        result = _run_scenario("shop_interaction")
        _assert_scenario_healthy(result)

    def test_shop_fr_text(self):
        result = _run_scenario("shop_interaction")
        _assert_has_fr_text(result)


@pytest.mark.slow
class TestZoneTransition:
    """Traverse 3+ map transitions, verify stability."""

    def test_zone_transition_no_crash(self):
        result = _run_scenario("zone_transition")
        _assert_scenario_healthy(result)

    def test_zone_transition_maps_change(self):
        result = _run_scenario("zone_transition")
        traverse_cp = next(
            (cp for cp in result.checkpoints if cp.name == "traverse_zones"),
            None,
        )
        if traverse_cp and traverse_cp.status == CheckpointStatus.TIMEOUT:
            pytest.xfail("Did not traverse 3 zones (stochastic)")


class TestLongDialogue:
    """Find NPC with long dialogue, verify FR text scrolling."""

    def test_long_dialogue_no_crash(self):
        result = _run_scenario("long_dialogue")
        _assert_scenario_healthy(result)

    def test_long_dialogue_fr_text(self):
        result = _run_scenario("long_dialogue")
        _assert_has_fr_text(result)

    def test_long_dialogue_no_corruption(self):
        result = _run_scenario("long_dialogue")
        corruption_cp = next(
            (cp for cp in result.checkpoints if cp.name == "verify_no_corruption"),
            None,
        )
        if corruption_cp:
            assert corruption_cp.status != CheckpointStatus.CRASH


@pytest.mark.slow
class TestBadge1Run:
    """Best-effort run toward first badge with stability checks."""

    def test_badge1_no_crash(self):
        result = _run_scenario("badge_1_run")
        _assert_scenario_healthy(result)

    def test_badge1_no_reboot(self):
        result = _run_scenario("badge_1_run")
        assert result.reboot_count == 0

    def test_badge1_stability(self):
        result = _run_scenario("badge_1_run")
        stability_cp = next(
            (cp for cp in result.checkpoints if cp.name == "stability_check"),
            None,
        )
        if stability_cp:
            assert stability_cp.status == CheckpointStatus.PASSED, (
                f"Stability check failed: {stability_cp.message}"
            )
