import unittest
from unittest.mock import MagicMock, patch

from src.cooker.checkpoint import (
    CheckpointStatus,
    CheckpointResult,
    Checkpoint,
    Scenario,
    ScenarioResult,
    _has_french_chars,
)


class TestCheckpointStatus(unittest.TestCase):

    def test_status_values(self):
        self.assertEqual(CheckpointStatus.PASSED.value, "passed")
        self.assertEqual(CheckpointStatus.FAILED.value, "failed")
        self.assertEqual(CheckpointStatus.TIMEOUT.value, "timeout")
        self.assertEqual(CheckpointStatus.SKIPPED.value, "skipped")
        self.assertEqual(CheckpointStatus.CRASH.value, "crash")


class TestCheckpointResult(unittest.TestCase):

    def test_create_result(self):
        result = CheckpointResult(
            name="test_cp",
            status=CheckpointStatus.PASSED,
            message="OK",
            frame_count=100,
        )
        self.assertEqual(result.name, "test_cp")
        self.assertEqual(result.status, CheckpointStatus.PASSED)
        self.assertEqual(result.frame_count, 100)


class TestScenarioResult(unittest.TestCase):

    def test_passed_all_pass(self):
        result = ScenarioResult(name="test")
        result.checkpoints = [
            CheckpointResult("a", CheckpointStatus.PASSED),
            CheckpointResult("b", CheckpointStatus.PASSED),
        ]
        self.assertTrue(result.passed)

    def test_passed_with_timeout(self):
        result = ScenarioResult(name="test")
        result.checkpoints = [
            CheckpointResult("a", CheckpointStatus.PASSED),
            CheckpointResult("b", CheckpointStatus.TIMEOUT),
        ]
        self.assertTrue(result.passed)

    def test_not_passed_with_failure(self):
        result = ScenarioResult(name="test")
        result.checkpoints = [
            CheckpointResult("a", CheckpointStatus.PASSED),
            CheckpointResult("b", CheckpointStatus.FAILED),
        ]
        self.assertFalse(result.passed)

    def test_failed_checkpoints_list(self):
        result = ScenarioResult(name="test")
        failed = CheckpointResult("fail", CheckpointStatus.FAILED)
        result.checkpoints = [
            CheckpointResult("ok", CheckpointStatus.PASSED),
            failed,
        ]
        self.assertEqual(result.failed_checkpoints, [failed])

    def test_empty_scenario_passes(self):
        result = ScenarioResult(name="empty")
        self.assertTrue(result.passed)


class TestScenarioRun(unittest.TestCase):

    def _make_bridge(self):
        bridge = MagicMock()
        bridge.frame_count = 0
        bridge.crash_count = 0
        bridge.reboot_count = 0
        bridge.detect_crash.return_value = False
        return bridge

    def test_run_all_pass(self):
        bridge = self._make_bridge()

        def action_pass(b):
            return CheckpointResult("step", CheckpointStatus.PASSED, frame_count=b.frame_count)

        scenario = Scenario(
            name="test",
            description="test scenario",
            checkpoints=[
                Checkpoint(name="s1", action=action_pass),
                Checkpoint(name="s2", action=action_pass),
            ],
        )
        result = scenario.run(bridge)
        self.assertEqual(len(result.checkpoints), 2)
        self.assertTrue(result.passed)

    def test_run_stops_on_required_failure(self):
        bridge = self._make_bridge()

        def action_fail(b):
            return CheckpointResult("fail", CheckpointStatus.FAILED)

        def action_pass(b):
            return CheckpointResult("pass", CheckpointStatus.PASSED)

        scenario = Scenario(
            name="test",
            description="test",
            checkpoints=[
                Checkpoint(name="s1", action=action_fail, required=True),
                Checkpoint(name="s2", action=action_pass),
            ],
        )
        result = scenario.run(bridge)
        self.assertEqual(len(result.checkpoints), 1)

    def test_run_continues_on_optional_failure(self):
        bridge = self._make_bridge()

        def action_fail(b):
            return CheckpointResult("fail", CheckpointStatus.FAILED)

        def action_pass(b):
            return CheckpointResult("pass", CheckpointStatus.PASSED)

        scenario = Scenario(
            name="test",
            description="test",
            checkpoints=[
                Checkpoint(name="s1", action=action_fail, required=False),
                Checkpoint(name="s2", action=action_pass),
            ],
        )
        result = scenario.run(bridge)
        self.assertEqual(len(result.checkpoints), 2)

    def test_run_stops_on_crash(self):
        bridge = self._make_bridge()

        def action_crash(b):
            return CheckpointResult("crash", CheckpointStatus.CRASH)

        def action_pass(b):
            return CheckpointResult("pass", CheckpointStatus.PASSED)

        scenario = Scenario(
            name="test",
            description="test",
            checkpoints=[
                Checkpoint(name="s1", action=action_crash),
                Checkpoint(name="s2", action=action_pass),
            ],
        )
        result = scenario.run(bridge)
        self.assertEqual(len(result.checkpoints), 1)

    def test_run_loads_savestate(self):
        bridge = self._make_bridge()

        def action_pass(b):
            return CheckpointResult("pass", CheckpointStatus.PASSED, frame_count=0)

        scenario = Scenario(
            name="test",
            description="test",
            checkpoints=[Checkpoint(name="s1", action=action_pass)],
            savestate_slot=3,
        )
        scenario.run(bridge)
        bridge.load_savestate.assert_called_once_with(3)
        bridge.advance_frames.assert_called()

    def test_run_timeout_on_frame_limit(self):
        bridge = self._make_bridge()
        bridge.frame_count = 99999

        def action_pass(b):
            return CheckpointResult("pass", CheckpointStatus.PASSED, frame_count=b.frame_count)

        scenario = Scenario(
            name="test",
            description="test",
            checkpoints=[
                Checkpoint(name="s1", action=action_pass),
                Checkpoint(name="s2", action=action_pass),
            ],
            max_total_frames=100,
        )
        result = scenario.run(bridge)
        last = result.checkpoints[-1]
        self.assertEqual(last.status, CheckpointStatus.TIMEOUT)
        self.assertIn("exceeded", last.message)


class TestHasFrenchChars(unittest.TestCase):

    def test_french_accents(self):
        self.assertTrue(_has_french_chars("Bonjour le héros!"))
        self.assertTrue(_has_french_chars("très bien"))
        self.assertTrue(_has_french_chars("garçon"))

    def test_french_words(self):
        self.assertTrue(_has_french_chars("les enfants jouent"))
        self.assertTrue(_has_french_chars("dans la ville"))

    def test_english_text(self):
        self.assertFalse(_has_french_chars("Hello world"))
        self.assertFalse(_has_french_chars("Good morning"))

    def test_empty_text(self):
        self.assertFalse(_has_french_chars(""))


if __name__ == "__main__":
    unittest.main()
