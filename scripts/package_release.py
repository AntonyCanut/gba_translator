#!/usr/bin/env python3
"""Package every built language ROM into a single release.

Collects the per-language ROMs declared in the ``languages/`` registry, copies
them into ``output/release/``, zips each one, and writes checksums plus a
manifest so the three languages can be shipped together.

    python3 scripts/package_release.py            # all built languages
    python3 scripts/package_release.py fr it      # a subset

A full ``.gba`` is shipped per language rather than an IPS patch: Unbound is a
32 MB ROM whose translated text lives above 0x1000000, which the 24-bit IPS
offset field cannot address.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.i18n import RegistryError, load_registry  # noqa: E402

RELEASE_DIR = REPO_ROOT / "output/release"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("languages", nargs="*", help="Language codes (default: all)")
    parser.add_argument("--build-number", type=int, default=0)
    args = parser.parse_args()

    try:
        registry = load_registry()
    except RegistryError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.languages:
        try:
            configs = [registry.get(code) for code in args.languages]
        except RegistryError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
    else:
        configs = registry.buildable()

    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {"build_number": args.build_number, "languages": []}
    checksum_lines = []
    missing = []

    for config in configs:
        rom = config.output_rom_path(REPO_ROOT)
        if not rom.exists():
            missing.append(config)
            print(f"⚠ {config.name}: ROM not built yet ({rom.relative_to(REPO_ROOT)}) — skipped")
            continue

        dest = RELEASE_DIR / config.output_rom
        shutil.copy2(rom, dest)
        zip_path = RELEASE_DIR / f"{rom.stem}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(dest, arcname=config.output_rom)

        rom_hash = sha256(dest)
        checksum_lines.append(f"{rom_hash}  {config.output_rom}")
        entry = {
            "code": config.code,
            "name": config.name,
            "native_name": config.native_name,
            "status": config.status,
            "version_label": config.version_label,
            "rom": config.output_rom,
            "zip": zip_path.name,
            "sha256": rom_hash,
            "size_bytes": dest.stat().st_size,
        }
        manifest["languages"].append(entry)
        print(f"✓ {config.name:8} → {dest.relative_to(REPO_ROOT)}  ({rom_hash[:12]}…)")

    (RELEASE_DIR / "RELEASE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (RELEASE_DIR / "SHA256SUMS.txt").write_text(
        "\n".join(checksum_lines) + "\n", encoding="utf-8"
    )

    print(f"\n📦 Release written to {RELEASE_DIR.relative_to(REPO_ROOT)}/")
    print(f"   languages packaged: {len(manifest['languages'])}")
    if missing:
        codes = ", ".join(c.code for c in missing)
        print(f"   ⚠ not built (skipped): {codes}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
