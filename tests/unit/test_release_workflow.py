"""Gardes de régression du workflow de publication BPS."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def _build_steps() -> list[dict]:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]["release"]["steps"]


def test_release_validates_the_tracked_bundle_without_private_inputs() -> None:
    """Réintroduire un téléchargement ou build ROM doit casser cette garde."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = _build_steps()
    script = "\n".join(str(step.get("run", "")) for step in steps)

    assert set(workflow["jobs"]) == {"release"}
    assert "verify_patch_bundle.py" in script
    assert "patches" in script
    assert "curl" not in script
    assert "ROM_URL" not in script
    assert "build-fr" not in script
    assert "build-all" not in script


def test_workflow_never_uploads_a_rom() -> None:
    """Les échanges entre jobs doivent contenir BPS et métadonnées, jamais de ROM."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    uploads = [
        step
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if step.get("uses", "").startswith("actions/upload-artifact@")
    ]

    assert uploads == []
    assert ".gba" not in WORKFLOW.read_text(encoding="utf-8")


def test_workflow_publishes_an_immutable_version_and_a_rolling_latest() -> None:
    """Chaque build doit rester disponible après le remplacement de latest."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    publish = next(
        step
        for step in workflow["jobs"]["release"]["steps"]
        if step.get("id") == "publish_releases"
    )

    assert publish["env"]["VERSION_TAG"] == "${{ steps.bundle.outputs.version_tag }}"
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


def test_release_requires_every_patch_before_creating_an_immutable_version() -> None:
    steps = _build_steps()
    verify = next(step for step in steps if step.get("name") == "Validate tracked patch bundle")
    resolve = next(step for step in steps if step.get("id") == "bundle")

    assert "--required fr it de indie" in verify["run"]
    assert "build_number" in resolve["run"]
    assert "version_tag=v2.1." in resolve["run"]


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


def test_ci_never_downloads_or_builds_a_private_rom() -> None:
    """Les E2E ROM sont locaux ; la CI publique reste entièrement ROM-less."""
    workflow = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    text = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "python-tests-rom" not in workflow["jobs"]
    assert "playwright-tests" not in workflow["jobs"]
    assert "ROM_URL" not in text
    assert "input/roms" not in text
    patch_job = workflow["jobs"]["patch-bundle"]
    script = "\n".join(str(step.get("run", "")) for step in patch_job["steps"])
    assert "verify_patch_bundle.py" in script


def test_local_e2e_commands_materialize_the_patch_before_playwright() -> None:
    package = yaml.safe_load((ROOT / "package.json").read_text(encoding="utf-8"))

    assert package["scripts"]["test:e2e"].startswith(
        "python3 scripts/materialize_test_roms.py fr && "
    )
    assert package["scripts"]["test:e2e:german"].startswith(
        "python3 scripts/materialize_test_roms.py de && "
    )
    assert package["scripts"]["test:e2e:hp-bar"].startswith(
        "python3 scripts/materialize_test_roms.py fr it de && "
    )
