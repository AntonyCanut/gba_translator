"""Validation et matérialisation locale du bundle BPS de release."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zlib
from collections.abc import Iterable
from pathlib import Path

from src.core.bps import BpsError, apply_bps_patch, inspect_bps_patch

MANIFEST_NAME = "RELEASE_MANIFEST.json"
CHECKSUMS_NAME = "SHA256SUMS.txt"


class PatchBundleError(RuntimeError):
    """Signale un bundle absent, corrompu ou incohérent."""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _metadata(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise PatchBundleError(f"métadonnées {label} absentes")
    filename = value.get("file")
    sha256 = value.get("sha256")
    crc32 = value.get("crc32")
    size = value.get("size_bytes")
    if not isinstance(filename, str) or Path(filename).name != filename:
        raise PatchBundleError(f"nom {label} invalide")
    if (
        not isinstance(sha256, str)
        or len(sha256) != 64
        or any(char not in "0123456789abcdef" for char in sha256)
    ):
        raise PatchBundleError(f"SHA-256 {label} invalide")
    if (
        not isinstance(crc32, str)
        or len(crc32) != 8
        or any(char not in "0123456789abcdef" for char in crc32)
    ):
        raise PatchBundleError(f"CRC32 {label} invalide")
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise PatchBundleError(f"taille {label} invalide")
    return value


class PatchBundle:
    """Représente le bundle BPS canonique d'une release multilingue."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def verify(self, required_codes: set[str] | None = None) -> dict:
        """Vérifie tous les fichiers et contrats BPS sans charger de ROM."""
        try:
            manifest = json.loads(
                (self.directory / MANIFEST_NAME).read_text(encoding="utf-8")
            )
            if manifest.get("format") != "BPS1":
                raise PatchBundleError("format de bundle invalide")
            build_number = manifest.get("build_number")
            if (
                not isinstance(build_number, int)
                or isinstance(build_number, bool)
                or build_number <= 0
            ):
                raise PatchBundleError("numéro de build invalide")
            languages = manifest.get("languages")
            if not isinstance(languages, list) or not languages:
                raise PatchBundleError("aucune langue dans le bundle")

            expected_checksums: dict[str, str] = {}
            seen_codes: set[str] = set()
            expected_files = {MANIFEST_NAME, CHECKSUMS_NAME}
            for entry in languages:
                if not isinstance(entry, dict):
                    raise PatchBundleError("entrée de langue invalide")
                code = entry.get("code")
                patch_name = entry.get("patch")
                if not isinstance(code, str) or not code or code in seen_codes:
                    raise PatchBundleError("code langue absent ou dupliqué")
                if (
                    not isinstance(patch_name, str)
                    or Path(patch_name).name != patch_name
                    or patch_name != f"pokemon_unbound_{code}.bps"
                ):
                    raise PatchBundleError(f"{code}: nom de patch invalide")
                patch_path = self.directory / patch_name
                patch = patch_path.read_bytes()
                patch_hash = _sha256_bytes(patch)
                if len(patch) != entry.get("patch_size_bytes"):
                    raise PatchBundleError(f"{code}: taille de patch invalide")
                if patch_hash != entry.get("patch_sha256"):
                    raise PatchBundleError(f"{code}: SHA-256 du patch invalide")

                source = _metadata(entry.get("source"), f"source {code}")
                target = _metadata(entry.get("target"), f"cible {code}")
                info = inspect_bps_patch(patch)
                if (
                    info.source_size != source["size_bytes"]
                    or info.source_crc32 != source["crc32"]
                ):
                    raise PatchBundleError(f"{code}: contrat source BPS incohérent")
                if (
                    info.target_size != target["size_bytes"]
                    or info.target_crc32 != target["crc32"]
                ):
                    raise PatchBundleError(f"{code}: contrat cible BPS incohérent")

                seen_codes.add(code)
                expected_files.add(patch_name)
                expected_checksums[patch_name] = patch_hash

            if required_codes is not None and seen_codes != required_codes:
                missing = sorted(required_codes - seen_codes)
                unexpected = sorted(seen_codes - required_codes)
                details = []
                if missing:
                    details.append(f"absentes: {', '.join(missing)}")
                if unexpected:
                    details.append(f"inattendues: {', '.join(unexpected)}")
                raise PatchBundleError(f"langues du bundle {'; '.join(details)}")

            actual_files = {
                path.name for path in self.directory.iterdir() if path.is_file()
            }
            if actual_files != expected_files:
                raise PatchBundleError("fichiers absents ou inattendus dans le bundle")
            checksum_lines = (
                self.directory / CHECKSUMS_NAME
            ).read_text(encoding="utf-8").splitlines()
            actual_checksums = {}
            for line in checksum_lines:
                parts = line.split("  ")
                if len(parts) != 2 or Path(parts[1]).name != parts[1]:
                    raise PatchBundleError("ligne SHA256SUMS invalide")
                actual_checksums[parts[1]] = parts[0]
            if actual_checksums != expected_checksums:
                raise PatchBundleError("SHA256SUMS incohérent")
            return manifest
        except PatchBundleError:
            raise
        except (BpsError, OSError, ValueError, json.JSONDecodeError) as exc:
            raise PatchBundleError(f"bundle BPS invalide: {exc}") from exc

    def materialize(self, code: str, source_path: Path, output_path: Path) -> Path:
        """Applique localement le patch d'une langue et vérifie la cible."""
        manifest = self.verify()
        entry = next(
            (item for item in manifest["languages"] if item["code"] == code),
            None,
        )
        if entry is None:
            raise PatchBundleError(f"langue absente du bundle: {code}")
        try:
            source = source_path.read_bytes()
        except OSError as exc:
            raise PatchBundleError(f"ROM source locale absente: {source_path}") from exc
        source_metadata = _metadata(entry["source"], f"source {code}")
        if (
            len(source) != source_metadata["size_bytes"]
            or _sha256_bytes(source) != source_metadata["sha256"]
            or f"{zlib.crc32(source):08x}" != source_metadata["crc32"]
        ):
            raise PatchBundleError(f"{code}: ROM source locale incompatible")

        patch = (self.directory / entry["patch"]).read_bytes()
        try:
            target = apply_bps_patch(source, patch)
        except BpsError as exc:
            raise PatchBundleError(f"{code}: application BPS impossible: {exc}") from exc
        target_metadata = _metadata(entry["target"], f"cible {code}")
        if (
            len(target) != target_metadata["size_bytes"]
            or _sha256_bytes(target) != target_metadata["sha256"]
            or f"{zlib.crc32(target):08x}" != target_metadata["crc32"]
        ):
            raise PatchBundleError(f"{code}: cible matérialisée incohérente")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            shutil.copyfile(output_path, output_path.with_suffix(output_path.suffix + ".bak"))
        with tempfile.NamedTemporaryFile(
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(target)
        temporary.replace(output_path)
        return output_path

    def promote_from(
        self, generated_directory: Path, required_codes: set[str]
    ) -> dict:
        """Copie un bundle local validé vers l'emplacement canonique suivi."""
        source_bundle = PatchBundle(generated_directory)
        manifest = source_bundle.verify(required_codes=required_codes)
        source_files = {
            MANIFEST_NAME,
            CHECKSUMS_NAME,
            *(entry["patch"] for entry in manifest["languages"]),
        }
        self.directory.mkdir(parents=True, exist_ok=True)
        unexpected = [
            path
            for path in self.directory.iterdir()
            if path.is_file()
            and path.name not in source_files
            and not path.name.startswith("pokemon_unbound_")
        ]
        if unexpected:
            raise PatchBundleError("fichier inattendu dans la destination canonique")
        for path in self.directory.glob("pokemon_unbound_*.bps"):
            path.unlink()
        for name in source_files:
            shutil.copyfile(generated_directory / name, self.directory / name)
        return self.verify(required_codes=required_codes)
