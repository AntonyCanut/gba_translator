#!/usr/bin/env python3
"""Inventorie les chaînes entièrement anglaises encore vivantes dans la ROM FR."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Iterable

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.live_english_audit import (  # noqa: E402
    AuditClassification,
    EnglishException,
    LiveEnglishFinding,
    classify_findings,
    filter_english_findings,
    find_live_english,
)

TEXT_REGION = (0x1E00000, 0x1FB0000)
VALID_CATEGORIES = {"delivered", "intentional", "base-unused"}


def text_digest(text: str) -> str:
    """Empreinte stable qui rend chaque revue sensible au texte exact."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_reviews(
    path: Path,
    findings: Iterable[LiveEnglishFinding],
) -> tuple[list[EnglishException], list[str]]:
    """Charge l'inventaire revu et signale toute entrée devenue obsolète."""
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    records = payload.get("entries")
    if not isinstance(records, dict):
        raise ValueError(f"{path}: 'entries' doit être un mapping")

    finding_by_key = {
        (finding.source_offset, text_digest(finding.english_text)): finding
        for finding in findings
    }
    reviews: list[EnglishException] = []
    stale: list[str] = []
    for raw_offset, raw_review in records.items():
        offset = int(raw_offset, 0) if isinstance(raw_offset, str) else int(raw_offset)
        if (
            not isinstance(raw_review, list)
            or len(raw_review) != 2
            or raw_review[0] not in VALID_CATEGORIES
            or not isinstance(raw_review[1], str)
        ):
            raise ValueError(
                f"{path}: revue invalide pour {raw_offset!r}; "
                "attendu [catégorie, sha256]"
            )
        category, digest = raw_review
        finding = finding_by_key.get((offset, digest))
        if finding is None:
            stale.append(f"{offset:#x}:{digest[:12]}")
            continue
        reviews.append(
            EnglishException(
                source_offset=offset,
                category=category,
                english_text=finding.english_text,
                reason=f"revue explicite dans {path.name}",
            )
        )
    return reviews, stale


def run_audit(
    *,
    english_rom: Path,
    french_rom: Path,
    spanish_rom: Path,
    extraction: Path,
    reviews_path: Path,
) -> tuple[AuditClassification, list[str]]:
    """Exécute le balayage et applique l'inventaire de revue."""
    payload = json.loads(extraction.read_text(encoding="utf-8"))
    entries = payload["texts"] if isinstance(payload, dict) else payload
    findings = filter_english_findings(
        find_live_english(
            english_rom.read_bytes(),
            french_rom.read_bytes(),
            spanish_rom.read_bytes(),
            entries,
        ),
        source_region=TEXT_REGION,
    )
    reviews, stale = load_reviews(reviews_path, findings)
    return classify_findings(findings, reviews), stale


def _print_group(label: str, findings: Iterable[LiveEnglishFinding]) -> None:
    rows = list(findings)
    print(f"\n{label} ({len(rows)})")
    for finding in rows:
        preview = finding.english_text.replace("\n", r"\n")
        if len(preview) > 110:
            preview = preview[:107] + "..."
        print(
            f"  {finding.source_offset:#010x} -> {finding.target_offset:#010x} "
            f"[{len(finding.pointer_sites)} ptr] {preview}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--english", type=Path, default=REPO_ROOT / "input/roms/englishrom.gba"
    )
    parser.add_argument(
        "--french", type=Path, default=REPO_ROOT / "output/roms/GenedRom-fr.gba"
    )
    parser.add_argument(
        "--spanish", type=Path, default=REPO_ROOT / "input/roms/spanishrom.gba"
    )
    parser.add_argument(
        "--extraction",
        type=Path,
        default=REPO_ROOT
        / "output/extracted/extracted_texts/englishrom_texts.json",
    )
    parser.add_argument(
        "--reviews",
        type=Path,
        default=REPO_ROOT / "languages/fr/live_english_reviews.yaml",
    )
    args = parser.parse_args()

    classification, stale = run_audit(
        english_rom=args.english,
        french_rom=args.french,
        spanish_rom=args.spanish,
        extraction=args.extraction,
        reviews_path=args.reviews,
    )
    _print_group("Contenu livré encore anglais", classification.delivered)
    _print_group("Anglais volontaire", classification.intentional)
    _print_group("Contenu inutilisé du jeu de base", classification.base_unused)
    _print_group("Nouvelles détections non classées", classification.unclassified)
    if stale:
        print(f"\nRevues obsolètes ({len(stale)}): " + ", ".join(stale))

    return 1 if classification.unclassified or stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
