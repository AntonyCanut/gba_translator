#!/usr/bin/env python3
"""Vérifie les portes finales DE et produit le rapport de certification."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_translation_coverage import classify, parse_combined  # noqa: E402
from src.core.live_english_audit import filter_english_findings, find_live_english  # noqa: E402
from src.i18n.de_release import DeReleaseManifest, REQUIRED_SURFACES  # noqa: E402

TEXT_REGION = (0x1E00000, 0x1FB0000)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(rows: object) -> str:
    encoded = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _live_findings(rom: Path) -> list:
    extraction = ROOT / "output/extracted/extracted_texts/englishrom_texts.json"
    payload = json.loads(extraction.read_text(encoding="utf-8"))
    entries = payload["texts"] if isinstance(payload, dict) else payload
    return filter_english_findings(
        find_live_english(
            (ROOT / "input/roms/englishrom.gba").read_bytes(),
            rom.read_bytes(),
            (ROOT / "input/roms/spanishrom.gba").read_bytes(),
            entries,
        ),
        source_region=TEXT_REGION,
    )


def _coverage() -> dict[str, int]:
    en = parse_combined(ROOT / "languages/en/combined_en.txt")
    de = parse_combined(ROOT / "languages/de/combined_de.txt")
    counts = Counter(classify(text, de, offset) for offset, text in en.items())
    return {
        "reference": len(en),
        "translated": counts["translated"],
        "untranslated": counts["untranslated"],
        "missing": counts["missing"],
        "orphan": len(set(de) - set(en)),
    }


def run(manifest_path: Path, report_dir: Path) -> tuple[dict, list[str]]:
    manifest = DeReleaseManifest.load(manifest_path)
    rom = ROOT / "output/roms/GenedRom-de.gba"
    failures: list[str] = []

    descriptor = yaml.safe_load((ROOT / "languages/de/lang.yaml").read_text(encoding="utf-8"))
    if descriptor.get("status") != "complete":
        failures.append("languages/de/lang.yaml n'est pas complete")

    coverage = _coverage()
    if coverage != manifest.coverage:
        failures.append(f"couverture DE inattendue: {coverage} != {manifest.coverage}")

    findings = _live_findings(rom)
    residue_rows = [
        {
            "source_offset": f"0x{item.source_offset:08X}",
            "target_offset": f"0x{item.target_offset:08X}",
            "text": item.english_text,
            "classification": manifest.classify_live_english(item.source_offset),
        }
        for item in findings
    ]
    residue_digest = _digest(residue_rows)
    if len(findings) != manifest.live_english_count:
        failures.append(f"résidus anglais: {len(findings)} != {manifest.live_english_count}")
    if residue_digest != manifest.live_english_sha256:
        failures.append(f"empreinte résidus anglais inattendue: {residue_digest}")
    unclassified = [row["source_offset"] for row in residue_rows if not row["classification"]]
    if unclassified:
        failures.append(f"résidus anglais non classés: {', '.join(unclassified[:10])}")

    sprite_paths = sorted(
        path for path in (ROOT / "languages/de/sprites").iterdir()
        if path.suffix in {".png", ".bmp"}
    )
    graphic_rows = [(path.name, _sha256(path)) for path in sprite_paths]
    graphic_digest = _digest(graphic_rows)
    if len(graphic_rows) != manifest.graphics_count or graphic_digest != manifest.graphics_sha256:
        failures.append("baseline des graphismes DE modifiée")

    rom_digest = _sha256(rom)
    if rom_digest != manifest.rom_sha256:
        failures.append(f"empreinte ROM DE inattendue: {rom_digest}")

    collision_path = ROOT / "output/reports/de_collision_audit.json"
    collision = json.loads(collision_path.read_text(encoding="utf-8"))
    if collision.get("collision_count") != 0:
        failures.append("collision de cellules dans la ROM DE")

    if set(manifest.surfaces) != REQUIRED_SURFACES:
        failures.append("inventaire des surfaces E2E incomplet")
    failures.extend(f"preuve absente: {path}" for path in manifest.missing_evidence(ROOT))

    report = {
        "status": "pass" if not failures else "fail",
        "rom": {"path": str(rom.relative_to(ROOT)), "sha256": rom_digest},
        "coverage": coverage,
        "collisions": collision.get("collision_count"),
        "live_english": {
            "count": len(findings),
            "sha256": residue_digest,
            "entries": residue_rows,
        },
        "graphics": {"count": len(graphic_rows), "sha256": graphic_digest, "assets": graphic_rows},
        "surfaces": manifest.surfaces,
        "failures": failures,
    }
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "de_release_certification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown = [
        "# Certification finale DE",
        "",
        f"Statut : **{report['status'].upper()}**",
        f"ROM : `{rom_digest}`",
        f"Couverture brute : {coverage['translated']}/{coverage['reference']}",
        f"Résidus anglais revus : {len(findings)} (`{residue_digest}`)",
        f"Collisions : {collision.get('collision_count')}",
        f"Assets graphiques : {len(graphic_rows)} (`{graphic_digest}`)",
        "",
        "Le JSON voisin liste chaque résidu, sa classification et chaque hash d'asset.",
    ]
    if failures:
        markdown.extend(["", "## Échecs", *[f"- {failure}" for failure in failures]])
    (report_dir / "de_release_certification.md").write_text(
        "\n".join(markdown) + "\n", encoding="utf-8"
    )
    return report, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "languages/de/release.yaml")
    parser.add_argument("--report-dir", type=Path, default=ROOT / "output/reports")
    args = parser.parse_args()
    report, failures = run(args.manifest, args.report_dir)
    print(json.dumps({"status": report["status"], "failures": failures}, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
