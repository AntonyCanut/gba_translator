#!/usr/bin/env python3
"""Crée les patchs BPS redistribuables de toutes les langues construites."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zlib
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.core.bps import apply_bps_patch, create_bps_patch
from src.i18n import LanguageConfig, RegistryError, load_registry

RELEASE_DIR = REPO_ROOT / "output/release"


def sha256(path: Path) -> str:
    """Calcule le SHA-256 d'un fichier sans le charger intégralement."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def crc32(payload: bytes) -> str:
    """Retourne un CRC32 canonique sur huit chiffres hexadécimaux."""
    return f"{zlib.crc32(payload):08x}"


class PatchReleasePackager:
    """Génère et vérifie les artefacts BPS d'une release multilingue."""

    def __init__(self, root: Path = REPO_ROOT, release_dir: Path | None = None) -> None:
        self.root = root
        self.release_dir = release_dir or root / "output/release"

    def _remove_previous_artifacts(self) -> None:
        self.release_dir.mkdir(parents=True, exist_ok=True)
        for pattern in (
            "*.gba",
            "*.zip",
            "pokemon_unbound_*.bps",
            "RELEASE_MANIFEST.json",
            "SHA256SUMS.txt",
        ):
            for path in self.release_dir.glob(pattern):
                path.unlink()

    def package(
        self, configs: Iterable[LanguageConfig], build_number: int = 0
    ) -> dict:
        """Crée un BPS par langue et écrit le manifeste de release.

        Args:
            configs: Descripteurs des langues à empaqueter.
            build_number: Numéro injecté dans la version de la ROM cible.

        Returns:
            Manifeste sérialisé dans ``RELEASE_MANIFEST.json``.

        Raises:
            FileNotFoundError: Si une ROM source ou construite est absente.
            RuntimeError: Si le round-trip du patch ne reproduit pas la cible.
        """
        self._remove_previous_artifacts()
        manifest = {"build_number": build_number, "format": "BPS1", "languages": []}
        checksum_lines: list[str] = []

        for config in configs:
            source = config.patch_source_path(self.root)
            target = config.output_rom_path(self.root)
            if source is None or target is None:
                raise FileNotFoundError(
                    f"{config.code}: source ou cible de patch non déclarée"
                )
            if not source.is_file():
                raise FileNotFoundError(f"ROM source absente: {source}")
            if not target.is_file():
                raise FileNotFoundError(f"ROM construite absente: {target}")

            source_bytes = source.read_bytes()
            target_bytes = target.read_bytes()
            patch_bytes = create_bps_patch(source_bytes, target_bytes)
            if apply_bps_patch(source_bytes, patch_bytes) != target_bytes:
                raise RuntimeError(f"{config.code}: le round-trip BPS diffère de la cible")

            patch_name = f"pokemon_unbound_{config.code}.bps"
            patch_path = self.release_dir / patch_name
            patch_path.write_bytes(patch_bytes)
            patch_hash = sha256(patch_path)
            checksum_lines.append(f"{patch_hash}  {patch_name}")
            manifest["languages"].append(
                {
                    "code": config.code,
                    "name": config.name,
                    "native_name": config.native_name,
                    "status": config.status,
                    "version_label": (
                        f"{config.version_label.rsplit('.', 1)[0]}.{build_number}"
                    ),
                    "patch": patch_name,
                    "patch_sha256": patch_hash,
                    "patch_size_bytes": len(patch_bytes),
                    "source": {
                        "file": source.name,
                        "sha256": sha256(source),
                        "crc32": crc32(source_bytes),
                        "size_bytes": source.stat().st_size,
                    },
                    "target": {
                        "file": target.name,
                        "sha256": sha256(target),
                        "crc32": crc32(target_bytes),
                        "size_bytes": target.stat().st_size,
                    },
                }
            )
            print(
                f"✓ {config.name:8} → {patch_path.relative_to(self.root)} "
                f"({patch_hash[:12]}…)"
            )

        manifest_path = self.release_dir / "RELEASE_MANIFEST.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (self.release_dir / "SHA256SUMS.txt").write_text(
            "\n".join(checksum_lines) + "\n", encoding="utf-8"
        )
        print(f"\n📦 Release BPS écrite dans {self.release_dir.relative_to(self.root)}/")
        return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("languages", nargs="*", help="Codes langue (défaut : toutes)")
    parser.add_argument("--build-number", type=int, default=0)
    args = parser.parse_args()

    try:
        registry = load_registry()
        configs = (
            [registry.get(code) for code in args.languages]
            if args.languages
            else registry.buildable()
        )
        PatchReleasePackager().package(configs, build_number=args.build_number)
    except (RegistryError, FileNotFoundError, RuntimeError) as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
