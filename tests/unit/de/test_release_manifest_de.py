"""Contrat versionné de la certification finale allemande."""

from __future__ import annotations

from pathlib import Path

from src.i18n.de_release import REQUIRED_SURFACES, DeReleaseManifest

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "languages/de/release.yaml"


def test_release_manifest_covers_every_requested_surface() -> None:
    manifest = DeReleaseManifest.load(MANIFEST)

    assert set(manifest.surfaces) == REQUIRED_SURFACES
    assert all(manifest.surfaces[name] for name in REQUIRED_SURFACES)


def test_release_manifest_evidence_exists() -> None:
    manifest = DeReleaseManifest.load(MANIFEST)

    missing = manifest.missing_evidence(ROOT)

    assert missing == []


def test_live_english_acceptance_is_bounded_and_explained() -> None:
    manifest = DeReleaseManifest.load(MANIFEST)

    assert manifest.live_english_count > 0
    assert len(manifest.live_english_sha256) == 64
    assert manifest.classify_live_english(0x01EEFE4C) == "credits"
    assert manifest.classify_live_english(0x01F94275) == "competitive_labels"
    assert manifest.classify_live_english(0x01F46E5D) == "reviewed_content"
    assert all(rule.reason.strip() for rule in manifest.live_english_rules)


def test_graphic_baseline_is_content_addressed() -> None:
    manifest = DeReleaseManifest.load(MANIFEST)

    assert manifest.graphics_count >= 50
    assert len(manifest.graphics_sha256) == 64
    assert manifest.captures_count == 1
    assert len(manifest.captures_sha256) == 64
