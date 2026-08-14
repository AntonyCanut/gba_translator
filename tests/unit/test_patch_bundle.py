"""Contrat du bundle BPS suivi et matérialisé uniquement en local."""

from __future__ import annotations

import hashlib
import json
import zlib
from pathlib import Path

import pytest

from src.core.bps import create_bps_patch
from src.core.patch_bundle import PatchBundle, PatchBundleError


def _file_metadata(name: str, payload: bytes) -> dict[str, object]:
    return {
        "file": name,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "crc32": f"{zlib.crc32(payload):08x}",
        "size_bytes": len(payload),
    }


def _write_bundle(directory: Path, code: str = "fr") -> tuple[bytes, bytes]:
    source = b"ROM-source-0123456789"
    target = b"ROM-cible--01234-FR-789"
    patch = create_bps_patch(source, target)
    patch_name = f"pokemon_unbound_{code}.bps"
    directory.mkdir(parents=True)
    (directory / patch_name).write_bytes(patch)
    patch_hash = hashlib.sha256(patch).hexdigest()
    manifest = {
        "build_number": 42,
        "format": "BPS1",
        "languages": [
            {
                "code": code,
                "name": "French",
                "native_name": "Français",
                "status": "complete",
                "version_label": "FR.2.1.42",
                "patch": patch_name,
                "patch_sha256": patch_hash,
                "patch_size_bytes": len(patch),
                "source": _file_metadata("englishrom.gba", source),
                "target": _file_metadata(f"GenedRom-{code}.gba", target),
            }
        ],
    }
    (directory / "RELEASE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (directory / "SHA256SUMS.txt").write_text(
        f"{patch_hash}  {patch_name}\n",
        encoding="utf-8",
    )
    return source, target


def test_verify_bundle_checks_bps_and_metadata_without_a_rom(tmp_path) -> None:
    """Supprimer la validation ROM-less doit rendre ce test rouge."""
    bundle_dir = tmp_path / "patches"
    _write_bundle(bundle_dir)

    manifest = PatchBundle(bundle_dir).verify(required_codes={"fr"})

    assert manifest["build_number"] == 42
    assert manifest["languages"][0]["code"] == "fr"


def test_verify_bundle_rejects_a_corrupted_patch(tmp_path) -> None:
    bundle_dir = tmp_path / "patches"
    _write_bundle(bundle_dir)
    patch_path = bundle_dir / "pokemon_unbound_fr.bps"
    patch_path.write_bytes(patch_path.read_bytes() + b"corruption")

    with pytest.raises(PatchBundleError, match="patch"):
        PatchBundle(bundle_dir).verify(required_codes={"fr"})


def test_materialize_rebuilds_a_local_rom_and_preserves_the_previous_one(tmp_path) -> None:
    """Les E2E consomment la cible du patch, jamais une ROM livrée par la CI."""
    bundle_dir = tmp_path / "patches"
    source, target = _write_bundle(bundle_dir)
    source_path = tmp_path / "englishrom.gba"
    output_path = tmp_path / "materialized/fr.gba"
    source_path.write_bytes(source)
    output_path.parent.mkdir(parents=True)
    output_path.write_bytes(b"ancienne cible")

    result = PatchBundle(bundle_dir).materialize("fr", source_path, output_path)

    assert result == output_path
    assert output_path.read_bytes() == target
    assert output_path.with_suffix(".gba.bak").read_bytes() == b"ancienne cible"


def test_materialize_rejects_the_wrong_local_source_before_writing(tmp_path) -> None:
    bundle_dir = tmp_path / "patches"
    _write_bundle(bundle_dir)
    source_path = tmp_path / "englishrom.gba"
    output_path = tmp_path / "materialized/fr.gba"
    source_path.write_bytes(b"mauvaise ROM")

    with pytest.raises(PatchBundleError, match="source"):
        PatchBundle(bundle_dir).materialize("fr", source_path, output_path)

    assert not output_path.exists()


def test_promote_copies_only_a_complete_verified_bundle(tmp_path) -> None:
    generated = tmp_path / "output/release"
    tracked = tmp_path / "patches"
    _write_bundle(generated)

    PatchBundle(tracked).promote_from(generated, required_codes={"fr"})

    assert sorted(path.name for path in tracked.iterdir()) == [
        "RELEASE_MANIFEST.json",
        "SHA256SUMS.txt",
        "pokemon_unbound_fr.bps",
    ]
    assert PatchBundle(tracked).verify(required_codes={"fr"})["build_number"] == 42
