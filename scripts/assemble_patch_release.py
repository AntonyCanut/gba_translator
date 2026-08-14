#!/usr/bin/env python3
"""Agrège et vérifie les artefacts BPS produits par les jobs de build."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_file_metadata(value: object, label: str, manifest_path: Path) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"métadonnées {label} absentes dans {manifest_path}")
    filename = value.get("file")
    checksum = value.get("sha256")
    size = value.get("size_bytes")
    if not isinstance(filename, str) or Path(filename).name != filename:
        raise ValueError(f"nom {label} invalide dans {manifest_path}")
    if (
        not isinstance(checksum, str)
        or len(checksum) != 64
        or any(char not in "0123456789abcdef" for char in checksum)
    ):
        raise ValueError(f"SHA-256 {label} invalide dans {manifest_path}")
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise ValueError(f"taille {label} invalide dans {manifest_path}")


def assemble_patch_release(
    artifacts_dir: Path,
    output_dir: Path,
    build_number: int,
    required_codes: set[str] | None = None,
) -> dict:
    """Vérifie les artefacts par langue et crée une release BPS cohérente."""
    artifacts_dir = artifacts_dir.resolve()
    output_dir = output_dir.resolve()
    try:
        output_dir.relative_to(artifacts_dir.parent)
    except ValueError as exc:
        raise ValueError("le dossier de sortie doit rester près des artefacts") from exc
    if output_dir == artifacts_dir.parent:
        raise ValueError("le dossier de sortie ne peut pas être le dossier parent")

    manifest_paths = sorted(artifacts_dir.glob("patch-*/RELEASE_MANIFEST.json"))
    if not manifest_paths:
        raise ValueError("aucun manifeste de patch trouvé")

    entries: list[dict] = []
    seen_codes: set[str] = set()
    seen_names: set[str] = set()
    verified_patches: list[tuple[Path, dict]] = []

    for manifest_path in manifest_paths:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("format") != "BPS1":
            raise ValueError(f"format invalide dans {manifest_path}")
        if manifest.get("build_number") != build_number:
            raise ValueError(f"numéro de build incohérent dans {manifest_path}")
        languages = manifest.get("languages")
        if not isinstance(languages, list) or len(languages) != 1:
            raise ValueError(f"{manifest_path} doit décrire exactement une langue")

        entry = languages[0]
        code = entry.get("code")
        patch_name = entry.get("patch")
        if not isinstance(code, str) or not code or code in seen_codes:
            raise ValueError(f"code langue absent ou dupliqué dans {manifest_path}")
        if (
            not isinstance(patch_name, str)
            or Path(patch_name).name != patch_name
            or not patch_name.endswith(".bps")
            or patch_name in seen_names
        ):
            raise ValueError(f"nom de patch invalide ou dupliqué dans {manifest_path}")
        for field in ("name", "native_name", "status", "version_label"):
            if not isinstance(entry.get(field), str) or not entry[field]:
                raise ValueError(f"champ {field} absent dans {manifest_path}")
        _validate_file_metadata(entry.get("source"), "source", manifest_path)
        _validate_file_metadata(entry.get("target"), "cible", manifest_path)

        patch_path = manifest_path.parent / patch_name
        if not patch_path.is_file():
            raise ValueError(f"patch absent: {patch_path}")
        if patch_path.stat().st_size != entry.get("patch_size_bytes"):
            raise ValueError(f"taille déclarée invalide pour {patch_path}")
        with patch_path.open("rb") as handle:
            if handle.read(4) != b"BPS1":
                raise ValueError(f"en-tête BPS1 invalide pour {patch_path}")
        if sha256(patch_path) != entry.get("patch_sha256"):
            raise ValueError(f"SHA-256 invalide pour {patch_path}")

        seen_codes.add(code)
        seen_names.add(patch_name)
        entries.append(entry)
        verified_patches.append((patch_path, entry))

    if required_codes:
        missing = sorted(required_codes - seen_codes)
        unexpected = sorted(seen_codes - required_codes)
        if missing:
            raise ValueError(f"langues requises absentes: {', '.join(missing)}")
        if unexpected:
            raise ValueError(f"langues inattendues: {', '.join(unexpected)}")

    entries.sort(key=lambda entry: (entry["code"] != "fr", entry["code"]))
    verified_patches.sort(key=lambda item: (item[1]["code"] != "fr", item[1]["code"]))

    output_dir.mkdir(parents=True, exist_ok=True)
    for pattern in ("pokemon_unbound_*.bps", "RELEASE_MANIFEST.json", "SHA256SUMS.txt"):
        for old_path in output_dir.glob(pattern):
            if old_path.is_file() or old_path.is_symlink():
                old_path.unlink()
    checksum_lines: list[str] = []
    for patch_path, entry in verified_patches:
        destination = output_dir / entry["patch"]
        shutil.copyfile(patch_path, destination)
        checksum_lines.append(f"{entry['patch_sha256']}  {entry['patch']}")

    combined = {
        "build_number": build_number,
        "format": "BPS1",
        "languages": entries,
    }
    (output_dir / "RELEASE_MANIFEST.json").write_text(
        json.dumps(combined, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "SHA256SUMS.txt").write_text(
        "\n".join(checksum_lines) + "\n", encoding="utf-8"
    )
    return combined


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--build-number", type=int, required=True)
    parser.add_argument("--required", nargs="*", default=[])
    args = parser.parse_args()
    try:
        assemble_patch_release(
            args.artifacts,
            args.output,
            args.build_number,
            required_codes=set(args.required),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
