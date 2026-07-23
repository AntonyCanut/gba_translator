"""Regression guards for the ROM release workflow."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def _build_steps() -> list[dict]:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]["build"]["steps"]


def test_artifact_upload_retries_a_transient_failure_safely() -> None:
    """A failed finalize (for example HTTP 403) must get one clean retry."""
    steps = _build_steps()
    primary = next(step for step in steps if step.get("id") == "upload_rom")
    retry = next(step for step in steps if step.get("id") == "retry_upload_rom")

    assert primary["uses"] == "actions/upload-artifact@v4"
    assert primary["continue-on-error"] is True
    assert primary["with"]["if-no-files-found"] == "error"

    assert retry["uses"] == primary["uses"]
    assert retry["if"] == "steps.upload_rom.outcome == 'failure'"
    assert retry.get("continue-on-error") is not True
    assert retry["with"]["name"] == primary["with"]["name"]
    assert retry["with"]["path"] == primary["with"]["path"]
    assert retry["with"]["if-no-files-found"] == "error"
    assert retry["with"]["overwrite"] is True
