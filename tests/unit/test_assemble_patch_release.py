"""Tests de l'agrégation des métadonnées BPS issues des jobs parallèles."""

from __future__ import annotations

import hashlib
import json

import pytest

from scripts.assemble_patch_release import assemble_patch_release


def _write_language_artifact(root, code: str, payload: bytes) -> None:
    artifact = root / f"patch-{code}"
    artifact.mkdir(parents=True)
    patch_name = f"pokemon_unbound_{code}.bps"
    (artifact / patch_name).write_bytes(payload)
    entry = {
        "code": code,
        "name": code.upper(),
        "native_name": code.upper(),
        "status": "complete",
        "version_label": f"{code.upper()}.2.1.42",
        "patch": patch_name,
        "patch_sha256": hashlib.sha256(payload).hexdigest(),
        "patch_size_bytes": len(payload),
        "source": {"file": "englishrom.gba", "sha256": "a" * 64, "size_bytes": 32},
        "target": {"file": f"GenedRom-{code}.gba", "sha256": "b" * 64, "size_bytes": 32},
    }
    (artifact / "RELEASE_MANIFEST.json").write_text(
        json.dumps({"build_number": 42, "format": "BPS1", "languages": [entry]}),
        encoding="utf-8",
    )


def test_assemble_patch_release_verifies_and_combines_parallel_artifacts(tmp_path) -> None:
    """La release finale doit livrer patchs, manifeste global et checksums."""
    artifacts = tmp_path / "artifacts"
    output = tmp_path / "release"
    _write_language_artifact(artifacts, "it", b"BPS1-it")
    _write_language_artifact(artifacts, "fr", b"BPS1-fr")

    manifest = assemble_patch_release(
        artifacts, output, build_number=42, required_codes={"fr", "it"}
    )

    assert [entry["code"] for entry in manifest["languages"]] == ["fr", "it"]
    assert sorted(path.name for path in output.iterdir()) == [
        "RELEASE_MANIFEST.json",
        "SHA256SUMS.txt",
        "pokemon_unbound_fr.bps",
        "pokemon_unbound_it.bps",
    ]
    assert json.loads((output / "RELEASE_MANIFEST.json").read_text()) == manifest
    assert "pokemon_unbound_fr.bps" in (output / "SHA256SUMS.txt").read_text()


def test_assemble_patch_release_rejects_a_corrupted_patch(tmp_path) -> None:
    """Le job final doit refuser un BPS modifié après le job de build."""
    artifacts = tmp_path / "artifacts"
    _write_language_artifact(artifacts, "fr", b"BPS1-original")
    (artifacts / "patch-fr/pokemon_unbound_fr.bps").write_bytes(b"BPS1-corrompu")

    with pytest.raises(ValueError, match="SHA-256"):
        assemble_patch_release(artifacts, tmp_path / "release", build_number=42)


def test_assemble_patch_release_rejects_a_missing_required_language(tmp_path) -> None:
    artifacts = tmp_path / "artifacts"
    _write_language_artifact(artifacts, "fr", b"BPS1-fr")

    with pytest.raises(ValueError, match="langues requises absentes: it"):
        assemble_patch_release(
            artifacts,
            tmp_path / "release",
            build_number=42,
            required_codes={"fr", "it"},
        )


def test_assemble_patch_release_rejects_incoherent_metadata(tmp_path) -> None:
    artifacts = tmp_path / "artifacts"
    _write_language_artifact(artifacts, "fr", b"BPS1-fr")
    manifest_path = artifacts / "patch-fr/RELEASE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["languages"][0]["patch_size_bytes"] = 999
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(ValueError, match="taille déclarée"):
        assemble_patch_release(artifacts, tmp_path / "release", build_number=42)
