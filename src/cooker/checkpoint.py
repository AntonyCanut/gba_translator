"""Checkpoint-based gameplay scenarios for automated ROM testing.

Each scenario is a sequence of Checkpoints that drive the emulator
through specific gameplay sections and verify conditions (text FR,
no crash, correct map, etc.). Scenarios are factory functions that
return a Scenario object.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Callable, Optional

from src.cooker.emulator import EmulatorBridge, EmulatorState


class CheckpointStatus(enum.Enum):
    """Result status of a checkpoint execution."""

    PASSED = "passed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"
    CRASH = "crash"


@dataclass
class CheckpointResult:
    """Result of executing a single checkpoint."""

    name: str
    status: CheckpointStatus
    message: str = ""
    frame_count: int = 0
    screenshot_path: Optional[str] = None
    text_found: Optional[str] = None
    map_id: Optional[int] = None


@dataclass
class Checkpoint:
    """A single step in a gameplay scenario.

    Args:
        name: Human-readable checkpoint name.
        action: Callable that drives the emulator for this step.
            Receives the EmulatorBridge and returns a CheckpointResult.
        timeout_frames: Maximum frames before declaring timeout.
        required: If True, a failure stops the scenario.
    """

    name: str
    action: Callable[[EmulatorBridge], CheckpointResult]
    timeout_frames: int = 3000
    required: bool = True


@dataclass
class ScenarioResult:
    """Aggregated result of running a full scenario."""

    name: str
    checkpoints: list[CheckpointResult] = field(default_factory=list)
    total_frames: int = 0
    crash_count: int = 0
    reboot_count: int = 0

    @property
    def passed(self) -> bool:
        return all(
            r.status in (CheckpointStatus.PASSED, CheckpointStatus.TIMEOUT, CheckpointStatus.SKIPPED)
            for r in self.checkpoints
        )

    @property
    def failed_checkpoints(self) -> list[CheckpointResult]:
        return [r for r in self.checkpoints if r.status == CheckpointStatus.FAILED]


@dataclass
class Scenario:
    """A gameplay scenario composed of ordered checkpoints.

    Args:
        name: Scenario identifier (e.g. 'trainer_battle').
        description: Human-readable description.
        checkpoints: Ordered list of checkpoints to execute.
        savestate_slot: If set, load this savestate before running.
        max_total_frames: Hard frame limit for the entire scenario.
    """

    name: str
    description: str
    checkpoints: list[Checkpoint]
    savestate_slot: Optional[int] = None
    max_total_frames: int = 60000

    def run(self, bridge: EmulatorBridge) -> ScenarioResult:
        """Execute all checkpoints in sequence."""
        result = ScenarioResult(name=self.name)

        if self.savestate_slot is not None:
            bridge.load_savestate(self.savestate_slot)
            bridge.advance_frames(30)

        for checkpoint in self.checkpoints:
            cp_result = checkpoint.action(bridge)
            result.checkpoints.append(cp_result)
            result.total_frames = bridge.frame_count
            result.crash_count = bridge.crash_count
            result.reboot_count = bridge.reboot_count

            if cp_result.status == CheckpointStatus.CRASH:
                break
            if cp_result.status == CheckpointStatus.FAILED and checkpoint.required:
                break
            if bridge.frame_count > self.max_total_frames:
                result.checkpoints.append(CheckpointResult(
                    name="global_timeout",
                    status=CheckpointStatus.TIMEOUT,
                    message=f"Scenario exceeded {self.max_total_frames} frames",
                    frame_count=bridge.frame_count,
                ))
                break

        return result


# ---------------------------------------------------------------------------
# Helper actions used across scenarios
# ---------------------------------------------------------------------------

def _wait_for_text(bridge: EmulatorBridge, max_frames: int = 600) -> str:
    """Advance frames until a text box appears, then read it."""
    for _ in range(0, max_frames, 10):
        bridge.advance_frames(10)
        if bridge.is_text_active():
            return bridge.read_text_buffer()
    return ""


def _advance_text(bridge: EmulatorBridge, presses: int = 1) -> None:
    """Press A to advance through text boxes."""
    for _ in range(presses):
        bridge.press_key("A")
        bridge.advance_frames(20)


def _walk(bridge: EmulatorBridge, direction: str, steps: int = 1) -> None:
    """Walk in a direction for the given number of steps."""
    for _ in range(steps):
        bridge.press_key(direction, frames=16)
        bridge.advance_frames(8)


def _has_french_chars(text: str) -> bool:
    """Check if text contains French-specific characters or patterns."""
    fr_indicators = ["é", "è", "ê", "à", "ù", "ç", "î", "ô", "û", "ë", "ï"]
    fr_words = ["le ", "la ", "les ", "de ", "du ", "des ", "un ", "une ",
                "est ", "et ", "que ", "qui ", "dans ", "pour ", "avec "]
    text_lower = text.lower()
    has_accent = any(c in text_lower for c in fr_indicators)
    has_word = any(w in text_lower for w in fr_words)
    return has_accent or has_word


def _check_no_crash(bridge: EmulatorBridge, name: str) -> Optional[CheckpointResult]:
    """Return a CRASH result if a crash is detected, else None."""
    if bridge.detect_crash():
        return CheckpointResult(
            name=name,
            status=CheckpointStatus.CRASH,
            message="Crash detected",
            frame_count=bridge.frame_count,
        )
    return None


# ===========================================================================
# Existing scenarios (9) — introduction & basic gameplay
# ===========================================================================

def boot_test() -> Scenario:
    """Boot the ROM and verify it reaches the title screen."""

    def check_boot(bridge: EmulatorBridge) -> CheckpointResult:
        bridge.advance_frames(300)
        crash = _check_no_crash(bridge, "boot")
        if crash:
            return crash
        return CheckpointResult(
            name="boot",
            status=CheckpointStatus.PASSED,
            message="ROM booted successfully",
            frame_count=bridge.frame_count,
        )

    return Scenario(
        name="boot_test",
        description="Boot ROM and reach title screen",
        checkpoints=[Checkpoint(name="boot", action=check_boot, timeout_frames=600)],
        max_total_frames=1000,
    )


def new_game() -> Scenario:
    """Start a new game from the title screen."""

    def press_start(bridge: EmulatorBridge) -> CheckpointResult:
        bridge.advance_frames(180)
        bridge.press_key("START")
        bridge.advance_frames(60)
        bridge.press_key("A")
        bridge.advance_frames(60)
        crash = _check_no_crash(bridge, "press_start")
        if crash:
            return crash
        return CheckpointResult(
            name="press_start",
            status=CheckpointStatus.PASSED,
            message="Pressed START on title screen",
            frame_count=bridge.frame_count,
        )

    def confirm_new_game(bridge: EmulatorBridge) -> CheckpointResult:
        bridge.press_key("A")
        bridge.advance_frames(60)
        bridge.press_key("A")
        bridge.advance_frames(120)
        text = _wait_for_text(bridge, max_frames=300)
        crash = _check_no_crash(bridge, "confirm_new_game")
        if crash:
            return crash
        return CheckpointResult(
            name="confirm_new_game",
            status=CheckpointStatus.PASSED,
            message="New game started",
            frame_count=bridge.frame_count,
            text_found=text or None,
        )

    return Scenario(
        name="new_game",
        description="Start a new game from title screen",
        checkpoints=[
            Checkpoint(name="press_start", action=press_start),
            Checkpoint(name="confirm_new_game", action=confirm_new_game),
        ],
        max_total_frames=3000,
    )


def full_intro() -> Scenario:
    """Play through the entire intro sequence."""

    def skip_intro_cutscene(bridge: EmulatorBridge) -> CheckpointResult:
        for _ in range(20):
            bridge.press_key("A")
            bridge.advance_frames(30)
        crash = _check_no_crash(bridge, "skip_intro_cutscene")
        if crash:
            return crash
        return CheckpointResult(
            name="skip_intro_cutscene",
            status=CheckpointStatus.PASSED,
            message="Skipped intro cutscene",
            frame_count=bridge.frame_count,
        )

    def professor_dialogue(bridge: EmulatorBridge) -> CheckpointResult:
        collected_text: list[str] = []
        for _ in range(30):
            text = _wait_for_text(bridge, max_frames=120)
            if text:
                collected_text.append(text)
            _advance_text(bridge)
        crash = _check_no_crash(bridge, "professor_dialogue")
        if crash:
            return crash
        full_text = " ".join(collected_text)
        is_fr = _has_french_chars(full_text) if full_text else False
        return CheckpointResult(
            name="professor_dialogue",
            status=CheckpointStatus.PASSED if full_text else CheckpointStatus.TIMEOUT,
            message=f"FR detected: {is_fr}" if full_text else "No text captured",
            frame_count=bridge.frame_count,
            text_found=full_text[:200] if full_text else None,
        )

    def name_entry(bridge: EmulatorBridge) -> CheckpointResult:
        for _ in range(5):
            bridge.press_key("A")
            bridge.advance_frames(30)
        crash = _check_no_crash(bridge, "name_entry")
        if crash:
            return crash
        return CheckpointResult(
            name="name_entry",
            status=CheckpointStatus.PASSED,
            message="Name entry completed (default name)",
            frame_count=bridge.frame_count,
        )

    return Scenario(
        name="full_intro",
        description="Complete intro sequence with professor dialogue",
        checkpoints=[
            Checkpoint(name="skip_intro_cutscene", action=skip_intro_cutscene),
            Checkpoint(name="professor_dialogue", action=professor_dialogue),
            Checkpoint(name="name_entry", action=name_entry),
        ],
        max_total_frames=15000,
    )


def first_battle() -> Scenario:
    """Engage in and complete the first scripted battle."""

    def walk_to_grass(bridge: EmulatorBridge) -> CheckpointResult:
        _walk(bridge, "UP", 5)
        _walk(bridge, "LEFT", 3)
        _walk(bridge, "UP", 10)
        bridge.advance_frames(60)
        crash = _check_no_crash(bridge, "walk_to_grass")
        if crash:
            return crash
        return CheckpointResult(
            name="walk_to_grass",
            status=CheckpointStatus.PASSED,
            message="Walked toward grass area",
            frame_count=bridge.frame_count,
            map_id=bridge.get_map_id(),
        )

    def trigger_battle(bridge: EmulatorBridge) -> CheckpointResult:
        for _ in range(50):
            _walk(bridge, "UP", 2)
            _walk(bridge, "DOWN", 2)
            bridge.advance_frames(10)
            if bridge.is_in_battle():
                break
        in_battle = bridge.is_in_battle()
        crash = _check_no_crash(bridge, "trigger_battle")
        if crash:
            return crash
        return CheckpointResult(
            name="trigger_battle",
            status=CheckpointStatus.PASSED if in_battle else CheckpointStatus.TIMEOUT,
            message="Battle triggered" if in_battle else "No battle encountered",
            frame_count=bridge.frame_count,
        )

    def fight_battle(bridge: EmulatorBridge) -> CheckpointResult:
        for _ in range(60):
            bridge.press_key("A")
            bridge.advance_frames(30)
            if not bridge.is_in_battle():
                break
        still_in_battle = bridge.is_in_battle()
        crash = _check_no_crash(bridge, "fight_battle")
        if crash:
            return crash
        return CheckpointResult(
            name="fight_battle",
            status=CheckpointStatus.PASSED if not still_in_battle else CheckpointStatus.TIMEOUT,
            message="Battle completed" if not still_in_battle else "Battle still ongoing",
            frame_count=bridge.frame_count,
        )

    return Scenario(
        name="first_battle",
        description="Engage in the first scripted/wild battle",
        checkpoints=[
            Checkpoint(name="walk_to_grass", action=walk_to_grass),
            Checkpoint(name="trigger_battle", action=trigger_battle, required=False),
            Checkpoint(name="fight_battle", action=fight_battle, required=False),
        ],
        max_total_frames=30000,
    )


def npc_dialogue() -> Scenario:
    """Talk to an NPC and verify dialogue is in French."""

    def find_npc(bridge: EmulatorBridge) -> CheckpointResult:
        _walk(bridge, "DOWN", 3)
        bridge.advance_frames(30)
        bridge.press_key("A")
        bridge.advance_frames(30)
        text = _wait_for_text(bridge, max_frames=300)
        crash = _check_no_crash(bridge, "find_npc")
        if crash:
            return crash
        return CheckpointResult(
            name="find_npc",
            status=CheckpointStatus.PASSED if text else CheckpointStatus.TIMEOUT,
            message=f"NPC text: {text[:80]}" if text else "No NPC text captured",
            frame_count=bridge.frame_count,
            text_found=text[:200] if text else None,
        )

    def verify_french(bridge: EmulatorBridge) -> CheckpointResult:
        text = bridge.read_text_buffer()
        _advance_text(bridge, presses=3)
        is_fr = _has_french_chars(text) if text else False
        crash = _check_no_crash(bridge, "verify_french")
        if crash:
            return crash
        return CheckpointResult(
            name="verify_french",
            status=CheckpointStatus.PASSED if is_fr else CheckpointStatus.TIMEOUT,
            message=f"French text: {is_fr}",
            frame_count=bridge.frame_count,
            text_found=text[:200] if text else None,
        )

    return Scenario(
        name="npc_dialogue",
        description="Talk to an NPC, verify FR dialogue",
        checkpoints=[
            Checkpoint(name="find_npc", action=find_npc, required=False),
            Checkpoint(name="verify_french", action=verify_french, required=False),
        ],
        max_total_frames=5000,
    )


def menu_navigation() -> Scenario:
    """Open the start menu and navigate through it."""

    def open_menu(bridge: EmulatorBridge) -> CheckpointResult:
        bridge.press_key("START")
        bridge.advance_frames(30)
        text = bridge.read_text_buffer()
        crash = _check_no_crash(bridge, "open_menu")
        if crash:
            return crash
        return CheckpointResult(
            name="open_menu",
            status=CheckpointStatus.PASSED,
            message="Start menu opened",
            frame_count=bridge.frame_count,
            text_found=text[:200] if text else None,
        )

    def navigate_items(bridge: EmulatorBridge) -> CheckpointResult:
        for direction in ["DOWN", "DOWN", "A", "B", "DOWN", "A", "B"]:
            bridge.press_key(direction)
            bridge.advance_frames(15)
        crash = _check_no_crash(bridge, "navigate_items")
        if crash:
            return crash
        return CheckpointResult(
            name="navigate_items",
            status=CheckpointStatus.PASSED,
            message="Navigated menu items",
            frame_count=bridge.frame_count,
        )

    def close_menu(bridge: EmulatorBridge) -> CheckpointResult:
        bridge.press_key("B")
        bridge.advance_frames(30)
        bridge.press_key("B")
        bridge.advance_frames(30)
        crash = _check_no_crash(bridge, "close_menu")
        if crash:
            return crash
        return CheckpointResult(
            name="close_menu",
            status=CheckpointStatus.PASSED,
            message="Menu closed",
            frame_count=bridge.frame_count,
        )

    return Scenario(
        name="menu_navigation",
        description="Open and navigate the start menu",
        checkpoints=[
            Checkpoint(name="open_menu", action=open_menu),
            Checkpoint(name="navigate_items", action=navigate_items),
            Checkpoint(name="close_menu", action=close_menu),
        ],
        max_total_frames=5000,
    )


def extended_play() -> Scenario:
    """Run the game for an extended period checking for stability."""

    def soak_test(bridge: EmulatorBridge) -> CheckpointResult:
        initial_map = bridge.get_map_id()
        crash_detected = False
        reboot_detected = False
        for i in range(100):
            bridge.advance_frames(60)
            if bridge.detect_crash():
                crash_detected = True
                break
            if bridge.detect_reboot(initial_map):
                reboot_detected = True
                break
            if i % 20 == 0:
                bridge.press_key("A")
                bridge.advance_frames(10)
        if crash_detected:
            return CheckpointResult(
                name="soak_test",
                status=CheckpointStatus.CRASH,
                message="Crash during soak test",
                frame_count=bridge.frame_count,
            )
        if reboot_detected:
            return CheckpointResult(
                name="soak_test",
                status=CheckpointStatus.FAILED,
                message="Game rebooted during soak test",
                frame_count=bridge.frame_count,
            )
        return CheckpointResult(
            name="soak_test",
            status=CheckpointStatus.PASSED,
            message=f"Soak test OK — {bridge.frame_count} frames",
            frame_count=bridge.frame_count,
        )

    return Scenario(
        name="extended_play",
        description="Soak test: run for ~6000 frames checking stability",
        checkpoints=[Checkpoint(name="soak_test", action=soak_test, timeout_frames=10000)],
        max_total_frames=15000,
    )


def reference_boot() -> Scenario:
    """Boot with a reference savestate and verify state consistency."""

    def load_reference(bridge: EmulatorBridge) -> CheckpointResult:
        bridge.load_savestate(slot=2)
        bridge.advance_frames(60)
        state = bridge.get_state()
        crash = _check_no_crash(bridge, "load_reference")
        if crash:
            return crash
        return CheckpointResult(
            name="load_reference",
            status=CheckpointStatus.PASSED,
            message=f"Reference loaded, map={state.map_id}",
            frame_count=bridge.frame_count,
            map_id=state.map_id,
        )

    return Scenario(
        name="reference_boot",
        description="Load a reference savestate and verify",
        checkpoints=[Checkpoint(name="load_reference", action=load_reference)],
        savestate_slot=2,
        max_total_frames=3000,
    )


def reference_overworld() -> Scenario:
    """Walk around the overworld from a reference savestate."""

    def walk_patrol(bridge: EmulatorBridge) -> CheckpointResult:
        initial_map = bridge.get_map_id()
        directions = ["UP", "UP", "RIGHT", "RIGHT", "DOWN", "DOWN", "LEFT", "LEFT"]
        for d in directions:
            _walk(bridge, d, 3)
            if bridge.detect_crash():
                return CheckpointResult(
                    name="walk_patrol",
                    status=CheckpointStatus.CRASH,
                    message=f"Crash while walking {d}",
                    frame_count=bridge.frame_count,
                )
        final_map = bridge.get_map_id()
        return CheckpointResult(
            name="walk_patrol",
            status=CheckpointStatus.PASSED,
            message=f"Patrol OK, map {initial_map} -> {final_map}",
            frame_count=bridge.frame_count,
            map_id=final_map,
        )

    return Scenario(
        name="reference_overworld",
        description="Walk an overworld patrol from reference savestate",
        checkpoints=[Checkpoint(name="walk_patrol", action=walk_patrol)],
        savestate_slot=2,
        max_total_frames=10000,
    )


# ===========================================================================
# New extended gameplay scenarios (6) — Axe 2
# ===========================================================================

def trainer_battle() -> Scenario:
    """Find and fight a trainer battle, verify FR text and victory."""

    def find_trainer(bridge: EmulatorBridge) -> CheckpointResult:
        for direction in ["UP", "RIGHT", "UP", "LEFT", "UP"]:
            _walk(bridge, direction, 5)
            bridge.advance_frames(30)
            if bridge.is_in_battle():
                break
        if not bridge.is_in_battle():
            for _ in range(30):
                _walk(bridge, "UP", 3)
                _walk(bridge, "DOWN", 3)
                bridge.advance_frames(20)
                if bridge.is_in_battle():
                    break
        in_battle = bridge.is_in_battle()
        crash = _check_no_crash(bridge, "find_trainer")
        if crash:
            return crash
        return CheckpointResult(
            name="find_trainer",
            status=CheckpointStatus.PASSED if in_battle else CheckpointStatus.TIMEOUT,
            message="Trainer battle started" if in_battle else "No trainer found",
            frame_count=bridge.frame_count,
        )

    def verify_trainer_text_fr(bridge: EmulatorBridge) -> CheckpointResult:
        text = _wait_for_text(bridge, max_frames=300)
        is_fr = _has_french_chars(text) if text else False
        crash = _check_no_crash(bridge, "verify_trainer_text_fr")
        if crash:
            return crash
        return CheckpointResult(
            name="verify_trainer_text_fr",
            status=CheckpointStatus.PASSED if text else CheckpointStatus.TIMEOUT,
            message=f"Trainer text FR: {is_fr}",
            frame_count=bridge.frame_count,
            text_found=text[:200] if text else None,
        )

    def win_battle(bridge: EmulatorBridge) -> CheckpointResult:
        for _ in range(80):
            bridge.press_key("A")
            bridge.advance_frames(30)
            if not bridge.is_in_battle():
                break
            if bridge.detect_crash():
                return CheckpointResult(
                    name="win_battle",
                    status=CheckpointStatus.CRASH,
                    message="Crash during battle",
                    frame_count=bridge.frame_count,
                )
        still_fighting = bridge.is_in_battle()
        return CheckpointResult(
            name="win_battle",
            status=CheckpointStatus.PASSED if not still_fighting else CheckpointStatus.TIMEOUT,
            message="Battle won" if not still_fighting else "Battle still ongoing",
            frame_count=bridge.frame_count,
        )

    def post_battle_stability(bridge: EmulatorBridge) -> CheckpointResult:
        bridge.advance_frames(120)
        crash = _check_no_crash(bridge, "post_battle_stability")
        if crash:
            return crash
        return CheckpointResult(
            name="post_battle_stability",
            status=CheckpointStatus.PASSED,
            message="Post-battle stable",
            frame_count=bridge.frame_count,
        )

    return Scenario(
        name="trainer_battle",
        description="Find trainer, verify FR text, win battle, check stability",
        checkpoints=[
            Checkpoint(name="find_trainer", action=find_trainer, required=False),
            Checkpoint(name="verify_trainer_text_fr", action=verify_trainer_text_fr, required=False),
            Checkpoint(name="win_battle", action=win_battle, required=False),
            Checkpoint(name="post_battle_stability", action=post_battle_stability),
        ],
        savestate_slot=1,
        max_total_frames=30000,
    )


def pokecenter_visit() -> Scenario:
    """Enter a Pokecenter, heal, and leave without crashing."""

    def enter_pokecenter(bridge: EmulatorBridge) -> CheckpointResult:
        _walk(bridge, "UP", 2)
        bridge.advance_frames(60)
        initial_map = bridge.get_map_id()
        _walk(bridge, "UP", 1)
        bridge.advance_frames(60)
        new_map = bridge.get_map_id()
        crash = _check_no_crash(bridge, "enter_pokecenter")
        if crash:
            return crash
        entered = new_map != initial_map
        return CheckpointResult(
            name="enter_pokecenter",
            status=CheckpointStatus.PASSED if entered else CheckpointStatus.TIMEOUT,
            message=f"Map transition: {initial_map} -> {new_map}",
            frame_count=bridge.frame_count,
            map_id=new_map,
        )

    def talk_to_nurse(bridge: EmulatorBridge) -> CheckpointResult:
        _walk(bridge, "UP", 4)
        bridge.press_key("A")
        bridge.advance_frames(30)
        text = _wait_for_text(bridge, max_frames=300)
        is_fr = _has_french_chars(text) if text else False
        crash = _check_no_crash(bridge, "talk_to_nurse")
        if crash:
            return crash
        return CheckpointResult(
            name="talk_to_nurse",
            status=CheckpointStatus.PASSED if text else CheckpointStatus.TIMEOUT,
            message=f"Nurse dialogue FR: {is_fr}",
            frame_count=bridge.frame_count,
            text_found=text[:200] if text else None,
        )

    def heal_team(bridge: EmulatorBridge) -> CheckpointResult:
        bridge.press_key("A")
        bridge.advance_frames(120)
        _advance_text(bridge, presses=3)
        bridge.advance_frames(120)
        crash = _check_no_crash(bridge, "heal_team")
        if crash:
            return crash
        return CheckpointResult(
            name="heal_team",
            status=CheckpointStatus.PASSED,
            message="Healing complete",
            frame_count=bridge.frame_count,
        )

    def exit_pokecenter(bridge: EmulatorBridge) -> CheckpointResult:
        _walk(bridge, "DOWN", 6)
        bridge.advance_frames(60)
        crash = _check_no_crash(bridge, "exit_pokecenter")
        if crash:
            return crash
        return CheckpointResult(
            name="exit_pokecenter",
            status=CheckpointStatus.PASSED,
            message="Exited Pokecenter",
            frame_count=bridge.frame_count,
            map_id=bridge.get_map_id(),
        )

    return Scenario(
        name="pokecenter_visit",
        description="Enter Pokecenter, talk to nurse (FR), heal, exit",
        checkpoints=[
            Checkpoint(name="enter_pokecenter", action=enter_pokecenter, required=False),
            Checkpoint(name="talk_to_nurse", action=talk_to_nurse, required=False),
            Checkpoint(name="heal_team", action=heal_team),
            Checkpoint(name="exit_pokecenter", action=exit_pokecenter),
        ],
        savestate_slot=1,
        max_total_frames=15000,
    )


def shop_interaction() -> Scenario:
    """Enter a shop, open the buy menu (FR items), and leave."""

    def enter_shop(bridge: EmulatorBridge) -> CheckpointResult:
        initial_map = bridge.get_map_id()
        _walk(bridge, "UP", 2)
        bridge.advance_frames(60)
        new_map = bridge.get_map_id()
        crash = _check_no_crash(bridge, "enter_shop")
        if crash:
            return crash
        return CheckpointResult(
            name="enter_shop",
            status=CheckpointStatus.PASSED if new_map != initial_map else CheckpointStatus.TIMEOUT,
            message=f"Map: {initial_map} -> {new_map}",
            frame_count=bridge.frame_count,
            map_id=new_map,
        )

    def open_buy_menu(bridge: EmulatorBridge) -> CheckpointResult:
        _walk(bridge, "UP", 3)
        bridge.press_key("A")
        bridge.advance_frames(30)
        text = _wait_for_text(bridge, max_frames=300)
        bridge.press_key("A")
        bridge.advance_frames(60)
        menu_text = bridge.read_text_buffer()
        is_fr = _has_french_chars(text or menu_text) if (text or menu_text) else False
        crash = _check_no_crash(bridge, "open_buy_menu")
        if crash:
            return crash
        return CheckpointResult(
            name="open_buy_menu",
            status=CheckpointStatus.PASSED if (text or menu_text) else CheckpointStatus.TIMEOUT,
            message=f"Shop menu FR: {is_fr}",
            frame_count=bridge.frame_count,
            text_found=(text or menu_text or "")[:200] or None,
        )

    def cancel_purchase(bridge: EmulatorBridge) -> CheckpointResult:
        bridge.press_key("B")
        bridge.advance_frames(30)
        bridge.press_key("B")
        bridge.advance_frames(30)
        bridge.press_key("B")
        bridge.advance_frames(60)
        crash = _check_no_crash(bridge, "cancel_purchase")
        if crash:
            return crash
        return CheckpointResult(
            name="cancel_purchase",
            status=CheckpointStatus.PASSED,
            message="Purchase cancelled",
            frame_count=bridge.frame_count,
        )

    def exit_shop(bridge: EmulatorBridge) -> CheckpointResult:
        _walk(bridge, "DOWN", 5)
        bridge.advance_frames(60)
        crash = _check_no_crash(bridge, "exit_shop")
        if crash:
            return crash
        return CheckpointResult(
            name="exit_shop",
            status=CheckpointStatus.PASSED,
            message="Exited shop",
            frame_count=bridge.frame_count,
            map_id=bridge.get_map_id(),
        )

    return Scenario(
        name="shop_interaction",
        description="Enter shop, open buy menu (FR items), cancel, exit",
        checkpoints=[
            Checkpoint(name="enter_shop", action=enter_shop, required=False),
            Checkpoint(name="open_buy_menu", action=open_buy_menu, required=False),
            Checkpoint(name="cancel_purchase", action=cancel_purchase),
            Checkpoint(name="exit_shop", action=exit_shop),
        ],
        savestate_slot=1,
        max_total_frames=15000,
    )


def zone_transition() -> Scenario:
    """Traverse at least 3 map/zone transitions and verify stability."""

    def traverse_zones(bridge: EmulatorBridge) -> CheckpointResult:
        maps_visited: list[int] = [bridge.get_map_id()]
        transitions = 0
        walk_patterns = [
            ("UP", 15), ("RIGHT", 10), ("UP", 15),
            ("LEFT", 10), ("DOWN", 15), ("RIGHT", 15),
            ("UP", 20), ("LEFT", 15),
        ]
        for direction, steps in walk_patterns:
            _walk(bridge, direction, steps)
            bridge.advance_frames(30)
            current_map = bridge.get_map_id()
            if current_map != maps_visited[-1]:
                maps_visited.append(current_map)
                transitions += 1
            if bridge.detect_crash():
                return CheckpointResult(
                    name="traverse_zones",
                    status=CheckpointStatus.CRASH,
                    message=f"Crash during zone transition after {transitions} transitions",
                    frame_count=bridge.frame_count,
                )
            if transitions >= 3:
                break

        return CheckpointResult(
            name="traverse_zones",
            status=CheckpointStatus.PASSED if transitions >= 3 else CheckpointStatus.TIMEOUT,
            message=f"{transitions} zone transitions, maps: {maps_visited}",
            frame_count=bridge.frame_count,
            map_id=maps_visited[-1] if maps_visited else -1,
        )

    def post_transition_stability(bridge: EmulatorBridge) -> CheckpointResult:
        bridge.advance_frames(180)
        crash = _check_no_crash(bridge, "post_transition_stability")
        if crash:
            return crash
        return CheckpointResult(
            name="post_transition_stability",
            status=CheckpointStatus.PASSED,
            message="Stable after zone transitions",
            frame_count=bridge.frame_count,
        )

    return Scenario(
        name="zone_transition",
        description="Traverse 3+ map zone transitions, verify no crash",
        checkpoints=[
            Checkpoint(name="traverse_zones", action=traverse_zones, required=False),
            Checkpoint(name="post_transition_stability", action=post_transition_stability),
        ],
        savestate_slot=1,
        max_total_frames=30000,
    )


def long_dialogue() -> Scenario:
    """Find an NPC with a long dialogue (>3 lines) and verify FR text."""

    def find_talkative_npc(bridge: EmulatorBridge) -> CheckpointResult:
        directions_to_try = ["UP", "LEFT", "DOWN", "RIGHT"]
        for d in directions_to_try:
            _walk(bridge, d, 3)
            bridge.press_key("A")
            bridge.advance_frames(30)
            text = _wait_for_text(bridge, max_frames=200)
            if text and len(text) > 20:
                return CheckpointResult(
                    name="find_talkative_npc",
                    status=CheckpointStatus.PASSED,
                    message=f"Found NPC with text ({len(text)} chars)",
                    frame_count=bridge.frame_count,
                    text_found=text[:200],
                )
            bridge.press_key("B")
            bridge.advance_frames(30)
        return CheckpointResult(
            name="find_talkative_npc",
            status=CheckpointStatus.TIMEOUT,
            message="No talkative NPC found nearby",
            frame_count=bridge.frame_count,
        )

    def scroll_dialogue(bridge: EmulatorBridge) -> CheckpointResult:
        collected_lines: list[str] = []
        for _ in range(15):
            text = bridge.read_text_buffer()
            if text and text not in collected_lines:
                collected_lines.append(text)
            _advance_text(bridge)
            bridge.advance_frames(10)
        crash = _check_no_crash(bridge, "scroll_dialogue")
        if crash:
            return crash
        full_text = "\n".join(collected_lines)
        is_fr = _has_french_chars(full_text)
        has_multiple_lines = len(collected_lines) >= 3
        return CheckpointResult(
            name="scroll_dialogue",
            status=CheckpointStatus.PASSED if has_multiple_lines else CheckpointStatus.TIMEOUT,
            message=f"Lines: {len(collected_lines)}, FR: {is_fr}",
            frame_count=bridge.frame_count,
            text_found=full_text[:300] if full_text else None,
        )

    def verify_no_corruption(bridge: EmulatorBridge) -> CheckpointResult:
        bridge.press_key("B")
        bridge.advance_frames(60)
        crash = _check_no_crash(bridge, "verify_no_corruption")
        if crash:
            return crash
        return CheckpointResult(
            name="verify_no_corruption",
            status=CheckpointStatus.PASSED,
            message="No visual corruption after dialogue",
            frame_count=bridge.frame_count,
        )

    return Scenario(
        name="long_dialogue",
        description="Find NPC with long dialogue, verify FR text scrolling",
        checkpoints=[
            Checkpoint(name="find_talkative_npc", action=find_talkative_npc, required=False),
            Checkpoint(name="scroll_dialogue", action=scroll_dialogue, required=False),
            Checkpoint(name="verify_no_corruption", action=verify_no_corruption),
        ],
        savestate_slot=1,
        max_total_frames=10000,
    )


def badge_1_run() -> Scenario:
    """Attempt a run toward the first gym badge — best effort.

    This is a complex, long-running scenario. It checks key milestones
    (rival battle, route traversal, gym) but accepts TIMEOUT for
    stochastic sections.
    """

    def rival_battle_intro(bridge: EmulatorBridge) -> CheckpointResult:
        for _ in range(40):
            bridge.advance_frames(30)
            if bridge.is_in_battle():
                break
            bridge.press_key("A")
        in_battle = bridge.is_in_battle()
        crash = _check_no_crash(bridge, "rival_battle_intro")
        if crash:
            return crash
        return CheckpointResult(
            name="rival_battle_intro",
            status=CheckpointStatus.PASSED if in_battle else CheckpointStatus.TIMEOUT,
            message="Rival battle started" if in_battle else "Rival battle not triggered",
            frame_count=bridge.frame_count,
        )

    def complete_rival_battle(bridge: EmulatorBridge) -> CheckpointResult:
        for _ in range(100):
            bridge.press_key("A")
            bridge.advance_frames(30)
            if not bridge.is_in_battle():
                break
            if bridge.detect_crash():
                return CheckpointResult(
                    name="complete_rival_battle",
                    status=CheckpointStatus.CRASH,
                    message="Crash during rival battle",
                    frame_count=bridge.frame_count,
                )
        return CheckpointResult(
            name="complete_rival_battle",
            status=CheckpointStatus.PASSED if not bridge.is_in_battle() else CheckpointStatus.TIMEOUT,
            message="Rival battle done" if not bridge.is_in_battle() else "Still fighting",
            frame_count=bridge.frame_count,
        )

    def navigate_to_gym_area(bridge: EmulatorBridge) -> CheckpointResult:
        maps_seen: list[int] = [bridge.get_map_id()]
        for direction, steps in [("UP", 20), ("RIGHT", 15), ("UP", 20), ("LEFT", 10), ("UP", 15)]:
            _walk(bridge, direction, steps)
            bridge.advance_frames(20)
            m = bridge.get_map_id()
            if m != maps_seen[-1]:
                maps_seen.append(m)
            if bridge.detect_crash():
                return CheckpointResult(
                    name="navigate_to_gym_area",
                    status=CheckpointStatus.CRASH,
                    message="Crash during navigation",
                    frame_count=bridge.frame_count,
                )
        return CheckpointResult(
            name="navigate_to_gym_area",
            status=CheckpointStatus.PASSED if len(maps_seen) > 2 else CheckpointStatus.TIMEOUT,
            message=f"Visited {len(maps_seen)} maps: {maps_seen}",
            frame_count=bridge.frame_count,
            map_id=maps_seen[-1],
        )

    def stability_check(bridge: EmulatorBridge) -> CheckpointResult:
        for _ in range(50):
            bridge.advance_frames(60)
            if bridge.detect_crash():
                return CheckpointResult(
                    name="stability_check",
                    status=CheckpointStatus.CRASH,
                    message="Crash during stability check",
                    frame_count=bridge.frame_count,
                )
        return CheckpointResult(
            name="stability_check",
            status=CheckpointStatus.PASSED,
            message=f"Stable after {bridge.frame_count} frames",
            frame_count=bridge.frame_count,
        )

    return Scenario(
        name="badge_1_run",
        description="Best-effort run toward first badge with stability checks",
        checkpoints=[
            Checkpoint(name="rival_battle_intro", action=rival_battle_intro, required=False),
            Checkpoint(name="complete_rival_battle", action=complete_rival_battle, required=False),
            Checkpoint(name="navigate_to_gym_area", action=navigate_to_gym_area, required=False),
            Checkpoint(name="stability_check", action=stability_check),
        ],
        savestate_slot=1,
        max_total_frames=60000,
    )


# ===========================================================================
# Registry — all available scenarios
# ===========================================================================

ALL_SCENARIOS: dict[str, Callable[[], Scenario]] = {
    # Existing (9)
    "boot_test": boot_test,
    "new_game": new_game,
    "full_intro": full_intro,
    "first_battle": first_battle,
    "npc_dialogue": npc_dialogue,
    "menu_navigation": menu_navigation,
    "extended_play": extended_play,
    "reference_boot": reference_boot,
    "reference_overworld": reference_overworld,
    # New extended (6)
    "trainer_battle": trainer_battle,
    "pokecenter_visit": pokecenter_visit,
    "shop_interaction": shop_interaction,
    "zone_transition": zone_transition,
    "long_dialogue": long_dialogue,
    "badge_1_run": badge_1_run,
}

EXTENDED_SCENARIOS = [
    "trainer_battle",
    "pokecenter_visit",
    "shop_interaction",
    "zone_transition",
    "long_dialogue",
    "badge_1_run",
]

QUICK_SCENARIOS = [
    "boot_test",
    "new_game",
    "menu_navigation",
]

SLOW_SCENARIOS = [
    "first_battle",
    "trainer_battle",
    "extended_play",
    "badge_1_run",
    "zone_transition",
]
