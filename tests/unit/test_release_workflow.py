"""Gardes de régression du workflow de publication BPS."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def _build_steps() -> list[dict]:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]["build"]["steps"]


def test_patch_artifact_upload_retries_a_transient_failure_safely() -> None:
    """A failed finalize (for example HTTP 403) must get one clean retry."""
    steps = _build_steps()
    primary = next(step for step in steps if step.get("id") == "upload_patch")
    retry = next(step for step in steps if step.get("id") == "retry_upload_patch")

    assert primary["uses"] == "actions/upload-artifact@v4"
    assert primary["continue-on-error"] is True
    assert primary["with"]["if-no-files-found"] == "error"

    assert retry["uses"] == primary["uses"]
    assert retry["if"] == "steps.upload_patch.outcome == 'failure'"
    assert retry.get("continue-on-error") is not True
    assert retry["with"]["name"] == primary["with"]["name"]
    assert retry["with"]["path"] == primary["with"]["path"]
    assert retry["with"]["if-no-files-found"] == "error"
    assert retry["with"]["overwrite"] is True


def test_workflow_never_uploads_a_rom() -> None:
    """Les échanges entre jobs doivent contenir BPS et métadonnées, jamais de ROM."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    uploads = [
        step
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if step.get("uses", "").startswith("actions/upload-artifact@")
    ]

    assert uploads
    assert all(".gba" not in step["with"]["path"] for step in uploads)
    assert all(".bps" in step["with"]["path"] for step in uploads)
    assert all("RELEASE_MANIFEST.json" in step["with"]["path"] for step in uploads)
    assert all("patch" in step["with"]["name"] for step in uploads)


def test_workflow_publishes_an_immutable_version_and_a_rolling_latest() -> None:
    """Chaque build doit rester disponible après le remplacement de latest."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    publish = next(
        step
        for step in workflow["jobs"]["release"]["steps"]
        if step.get("id") == "publish_releases"
    )

    assert publish["env"]["VERSION_TAG"] == "v2.1.${{ github.run_number }}"
    assert publish["env"]["LATEST_TAG"] == "latest"
    script = publish["run"]
    assert 'gh release view "${VERSION_TAG}"' in script
    assert 'gh release download "${VERSION_TAG}"' in script
    assert "cmp --" in script
    assert "gh release edit" not in script
    assert "--clobber" not in script
    assert 'gh release create "${VERSION_TAG}"' in script
    assert 'gh release delete "${LATEST_TAG}"' in script
    assert 'gh release create "${LATEST_TAG}"' in script
    assert "RELEASE_MANIFEST.json" in script
    assert "SHA256SUMS.txt" in script


def test_release_matrix_covers_every_buildable_language() -> None:
    """Une langue buildable ne doit pas disparaître silencieusement des releases."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    entries = workflow["jobs"]["build"]["strategy"]["matrix"]["include"]

    assert {entry["lang"] for entry in entries} == {"fr", "it", "de", "indie"}


def test_release_requires_every_patch_before_creating_an_immutable_version() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["release"]["steps"]
    assemble = next(
        step for step in steps if step.get("name") == "Assemble verified release metadata"
    )
    assert "--required fr it de indie" in assemble["run"]
    publish_index = next(i for i, step in enumerate(steps) if step.get("id") == "publish_releases")
    assert not any(step.get("name", "").startswith("Fail if") for step in steps[publish_index + 1 :])


def test_ci_without_private_roms_keeps_fast_and_standard_suites_rom_free() -> None:
    """Un checkout propre doit exécuter les suites non-ROM sans fichier privé."""
    workflow = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    fast_run = next(
        step["run"]
        for step in workflow["jobs"]["python-tests-fast"]["steps"]
        if step.get("name") == "Run fast unit tests"
    )
    standard_run = next(
        step["run"]
        for step in workflow["jobs"]["python-tests-standard"]["steps"]
        if step.get("name") == "Run standard tests"
    )

    assert "not rom" in fast_run
    assert "not rom" in standard_run


def test_playwright_ci_uses_private_inputs_only_on_trusted_pushes() -> None:
    """Les secrets ROM ne doivent jamais être demandés aux PR de forks."""
    workflow = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    job = workflow["jobs"]["playwright-tests"]
    names = {step.get("name") for step in job["steps"]}

    assert job["if"] == "github.event_name == 'push' && github.ref == 'refs/heads/master'"
    assert "Download and verify private ROM inputs" in names
    assert "Build French ROM locally" in names


def test_trusted_ci_runs_python_rom_tests_with_private_inputs() -> None:
    workflow = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    job = workflow["jobs"]["python-tests-rom"]
    names = {step.get("name") for step in job["steps"]}

    assert job["if"] == "github.event_name == 'push' && github.ref == 'refs/heads/master'"
    assert "Download and verify private ROM inputs" in names
    assert "Build French ROM locally" in names
    run = next(step["run"] for step in job["steps"] if step.get("name") == "Run ROM tests")
    assert 'rom and not emulator' in run
