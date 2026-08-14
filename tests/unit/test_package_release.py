"""Tests du packaging de release exclusivement en patchs BPS."""

from __future__ import annotations

import hashlib
import json
import zlib

import pytest

from scripts.package_release import PatchReleasePackager
from src.core.bps import apply_bps_patch
from src.i18n import LanguageConfig


def test_packager_writes_only_a_verified_bps_and_metadata(tmp_path) -> None:
    """Réintroduire une ROM ou un ZIP dans la release doit faire échouer ce test."""
    source = tmp_path / "input/roms/base.gba"
    target = tmp_path / "output/roms/target.gba"
    release_dir = tmp_path / "output/release"
    source.parent.mkdir(parents=True)
    target.parent.mkdir(parents=True)
    release_dir.mkdir(parents=True)
    source.write_bytes(b"ROM-source-0123456789")
    target.write_bytes(b"ROM-cible--01234-FR-789")
    (release_dir / "ancien.gba").write_bytes(b"interdit")
    (release_dir / "ancien.zip").write_bytes(b"interdit")
    (release_dir / "pokemon_unbound_obsolete.bps").write_bytes(b"obsolete")
    (release_dir / "RELEASE_MANIFEST.json").write_text("périmé")
    (release_dir / "SHA256SUMS.txt").write_text("périmé")
    config = LanguageConfig(
        code="fr",
        name="French",
        native_name="Français",
        status="complete",
        build="dedicated",
        builder_language="french",
        combined="languages/fr/combined_fr.txt",
        output_rom="target.gba",
        patch_source="input/roms/base.gba",
        version_label="FR.2.1.0",
    )

    packager = PatchReleasePackager(root=tmp_path, release_dir=release_dir)
    manifest = packager.package([config], build_number=42)

    patch_path = release_dir / "pokemon_unbound_fr.bps"
    assert apply_bps_patch(source.read_bytes(), patch_path.read_bytes()) == target.read_bytes()
    assert sorted(path.suffix for path in release_dir.iterdir()) == [".bps", ".json", ".txt"]
    assert manifest["format"] == "BPS1"
    assert manifest["build_number"] == 42
    entry = manifest["languages"][0]
    assert entry["version_label"] == "FR.2.1.42"
    assert entry["patch"] == "pokemon_unbound_fr.bps"
    assert entry["source"]["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert entry["source"]["crc32"] == f"{zlib.crc32(source.read_bytes()):08x}"
    assert entry["target"]["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
    assert entry["target"]["crc32"] == f"{zlib.crc32(target.read_bytes()):08x}"
    assert entry["target"]["file"] == "target.gba"
    assert json.loads((release_dir / "RELEASE_MANIFEST.json").read_text()) == manifest
    checksums = (release_dir / "SHA256SUMS.txt").read_text()
    assert "pokemon_unbound_fr.bps" in checksums
    assert ".gba" not in checksums


def test_packager_removes_stale_metadata_before_a_validation_failure(tmp_path) -> None:
    release_dir = tmp_path / "output/release"
    release_dir.mkdir(parents=True)
    (release_dir / "RELEASE_MANIFEST.json").write_text("périmé")
    (release_dir / "SHA256SUMS.txt").write_text("périmé")
    config = LanguageConfig(
        code="fr",
        name="French",
        native_name="Français",
        status="complete",
        build="dedicated",
        builder_language="french",
        combined="languages/fr/combined_fr.txt",
        output_rom="missing.gba",
        patch_source="input/roms/missing.gba",
        version_label="FR.2.1.0",
    )

    with pytest.raises(FileNotFoundError):
        PatchReleasePackager(root=tmp_path, release_dir=release_dir).package([config])

    assert not (release_dir / "RELEASE_MANIFEST.json").exists()
    assert not (release_dir / "SHA256SUMS.txt").exists()
