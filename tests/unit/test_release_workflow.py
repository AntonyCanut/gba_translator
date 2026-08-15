"""Gardes de régression du workflow de publication BPS."""

import os
import subprocess
import textwrap
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
PATCH_ASSETS = (
    "pokemon_unbound_fr.bps",
    "pokemon_unbound_it.bps",
    "pokemon_unbound_de.bps",
    "pokemon_unbound_indie.bps",
    "RELEASE_MANIFEST.json",
    "SHA256SUMS.txt",
)


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
    assert 'gh release create "${VERSION_TAG}"' in script
    assert workflow["concurrency"]["group"] == "patch-release"
    assert workflow["concurrency"]["cancel-in-progress"] is False
    assert "LATEST_BUILD" in script
    assert 'if [ "${LATEST_BUILD}" -gt "${BUILD_NUMBER}" ]' in script
    assert 'gh release edit "${LATEST_TAG}"' in script
    assert "--clobber" in script
    assert 'gh release delete "${LATEST_TAG}"' not in script
    assert "RELEASE_MANIFEST.json" in script
    assert "SHA256SUMS.txt" in script


def _run_publish_scenario(
    tmp_path: Path,
    *,
    latest_assets: tuple[str, ...],
    latest_manifest: str = "",
) -> tuple[subprocess.CompletedProcess, str]:
    publish = next(
        step
        for step in _build_steps()
        if step.get("id") == "publish_releases"
    )
    patches = tmp_path / "patches"
    patches.mkdir()
    for name in PATCH_ASSETS:
        (patches / name).write_text("fixture\n", encoding="utf-8")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    gh_log = tmp_path / "gh.log"
    fake_gh = fake_bin / "gh"
    fake_gh.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            printf '%s\\n' "$*" >> "${GH_LOG}"
            if [[ "$1 $2 $3" == "release view v2.1.43" ]]; then
              exit 0
            fi
            if [[ "$1 $2 $3" == "release download v2.1.43" ]]; then
              mkdir -p "$5"
              cp patches/* "$5/"
              exit 0
            fi
            if [[ "$1 $2 $3" == "release view latest" ]]; then
              if [[ "$*" == *"--json assets"* ]]; then
                printf '%s\\n' "${FAKE_LATEST_ASSETS}"
              fi
              exit 0
            fi
            if [[ "$1 $2 $3" == "release download latest" ]]; then
              if [[ -z "${FAKE_LATEST_MANIFEST}" ]]; then
                echo 'no assets match the file pattern' >&2
                exit 1
              fi
              mkdir -p "$5"
              printf '%s' "${FAKE_LATEST_MANIFEST}" > "$5/RELEASE_MANIFEST.json"
              exit 0
            fi
            if [[ "$1 $2 $3" == "release edit latest" ]] ||
               [[ "$1 $2 $3" == "release delete-asset latest" ]] ||
               [[ "$1 $2 $3" == "release upload latest" ]] ||
               [[ "$1" == "api" ]]; then
              exit 0
            fi
            echo "unexpected gh command: $*" >&2
            exit 90
            """
        ),
        encoding="utf-8",
    )
    fake_gh.chmod(0o755)
    fake_git = fake_bin / "git"
    fake_git.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            if [[ "$1" == "rev-parse" ]]; then
              echo abc1234
            else
              echo 'fixture commit'
            fi
            """
        ),
        encoding="utf-8",
    )
    fake_git.chmod(0o755)
    env = os.environ | {
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "GH_LOG": str(gh_log),
        "FAKE_LATEST_ASSETS": "\n".join(latest_assets),
        "FAKE_LATEST_MANIFEST": latest_manifest,
        "GITHUB_OUTPUT": str(tmp_path / "github-output"),
        "GITHUB_REPOSITORY": "AntonyKervazoCanut/gba_translator",
        "GITHUB_SHA": "1111111111111111111111111111111111111111",
        "VERSION_TAG": "v2.1.43",
        "LATEST_TAG": "latest",
        "BUILD_NUMBER": "43",
    }

    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", publish["run"]],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result, gh_log.read_text(encoding="utf-8")


def test_release_migrates_a_legacy_latest_without_manifest(tmp_path: Path) -> None:
    """Un ancien ``latest`` avec ROMs ne doit pas bloquer sa migration BPS."""
    # Arrange
    legacy_roms = tuple(f"Gened{'Rom'}-{code}.gba" for code in ("de", "fr", "it"))

    # Act
    result, calls = _run_publish_scenario(tmp_path, latest_assets=legacy_roms)

    # Assert
    assert result.returncode == 0, result.stderr
    assert "release download latest" not in calls
    for legacy_rom in legacy_roms:
        assert f"release delete-asset latest {legacy_rom} --yes" in calls
    assert "release upload latest" in calls
    assert (
        "api --method PATCH "
        "repos/AntonyKervazoCanut/gba_translator/git/refs/tags/latest "
        "-f sha=1111111111111111111111111111111111111111 -F force=true"
    ) in calls


def test_release_rejects_a_non_numeric_latest_manifest(tmp_path: Path) -> None:
    """Un manifeste distant invalide ne doit déclencher aucune mutation de release."""
    # Arrange
    manifest = '{"build_number":"invalide"}'

    # Act
    result, calls = _run_publish_scenario(
        tmp_path,
        latest_assets=("RELEASE_MANIFEST.json",),
        latest_manifest=manifest,
    )

    # Assert
    assert result.returncode != 0
    assert "Invalid latest patch build number" in result.stdout
    assert "release edit latest" not in calls
    assert "release delete-asset latest" not in calls
    assert "release upload latest" not in calls
    assert "api --method PATCH" not in calls


def test_release_keeps_a_newer_latest_untouched(tmp_path: Path) -> None:
    """Un rerun d'un ancien build ne doit jamais faire régresser ``latest``."""
    # Arrange
    manifest = '{"build_number":44}'

    # Act
    result, calls = _run_publish_scenario(
        tmp_path,
        latest_assets=PATCH_ASSETS,
        latest_manifest=manifest,
    )

    # Assert
    assert result.returncode == 0, result.stderr
    assert "latest reste sur le build supérieur 44." in result.stdout
    assert "release edit latest" not in calls
    assert "release delete-asset latest" not in calls
    assert "release upload latest" not in calls
    assert "api --method PATCH" not in calls


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
    fr_rom_name = "Gened" + "Rom-fr.gba"
    de_rom_name = "Gened" + "Rom-de.gba"

    aggregate = package["scripts"]["test:e2e"]
    assert aggregate.startswith("python3 scripts/materialize_test_roms.py fr de && ")
    assert f"ROM_PATH=$(pwd)/output/roms/{fr_rom_name}" in aggregate
    assert "--project=german" in aggregate
    assert f"ROM_PATH=$(pwd)/output/roms/{de_rom_name}" in aggregate
    assert package["scripts"]["test:e2e:german"].startswith(
        "python3 scripts/materialize_test_roms.py de && "
    )
    assert package["scripts"]["test:e2e:hp-bar"].startswith(
        "python3 scripts/materialize_test_roms.py fr it de && "
    )
    report = package["scripts"]["test:e2e:report"]
    assert report.startswith(
        "python3 scripts/materialize_test_roms.py fr && "
    )
    assert "--project=boot" in report
    assert "--project=german" not in report
