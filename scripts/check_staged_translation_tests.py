#!/usr/bin/env python3
"""Require a unit-test manifest entry for every staged combined translation."""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import yaml

import check_translation_integrity as integrity


COMBINED_PATH_RE = re.compile(r"^languages/([^/]+)/combined_([^/]+)\.txt$")


@dataclass(frozen=True)
class AddedTranslation:
    """A non-empty translation line added to a combined file in the Git index."""

    lang: str
    offset: int
    text: str


def _language_for_path(path: str) -> Optional[str]:
    """Return the language code when *path* is a canonical combined file."""

    match = COMBINED_PATH_RE.fullmatch(path)
    if match and match.group(1) == match.group(2):
        return match.group(1)
    return None


def parse_added_translations(diff: str) -> List[AddedTranslation]:
    """Extract added, non-empty translation entries from a zero-context Git diff."""

    additions: List[AddedTranslation] = []
    current_lang: Optional[str] = None
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            current_lang = None
            continue
        if line.startswith("+++ b/"):
            current_lang = _language_for_path(line[6:])
            continue
        if not current_lang or not line.startswith("+"):
            continue
        match = integrity.LINE_RE.match(line[1:])
        if not match:
            continue
        text = match.group(2).strip()
        if text:
            additions.append(AddedTranslation(current_lang, int(match.group(1), 16), text))
    return additions


def _load_last_wins_text(text: str) -> Dict[int, str]:
    """Parse combined-file content with the build's case-insensitive last-wins rule."""

    mapping: Dict[int, str] = {}
    for line in text.splitlines():
        match = integrity.LINE_RE.match(line)
        if match:
            mapping[int(match.group(1), 16)] = match.group(2).strip()
    return mapping


def _manifest_entries(text: str, path: str) -> Tuple[integrity.ProtectedEntry, ...]:
    """Load a staged manifest using the shared validation rules."""

    return integrity.parse_manifest(yaml.safe_load(text) or {}, Path(path))


def validate_added_translations(
    additions: Iterable[AddedTranslation], staged_files: Mapping[str, str]
) -> List[str]:
    """Return a failure for every added translation lacking an exact unit-test guard."""

    failures: List[str] = []
    seen = set()
    for addition in additions:
        key = (addition.lang, addition.offset)
        if key in seen:
            continue
        seen.add(key)
        combined_path = f"languages/{addition.lang}/combined_{addition.lang}.txt"
        manifest_path = f"languages/{addition.lang}/protected_entries.yaml"
        combined_text = staged_files.get(combined_path)
        manifest_text = staged_files.get(manifest_path)
        label = f"[{addition.lang}] 0x{addition.offset:06X}"
        if combined_text is None:
            failures.append(f"{label}: fichier combined absent de l'index")
            continue
        if manifest_text is None:
            failures.append(f"{label}: protected_entries.yaml absent de l'index")
            continue
        try:
            entries = _manifest_entries(manifest_text, manifest_path)
        except (TypeError, ValueError, yaml.YAMLError) as error:
            failures.append(f"{label}: manifeste de test invalide ({error})")
            continue
        entry = next((item for item in entries if item.offset == addition.offset), None)
        if entry is None:
            failures.append(f"{label}: aucune entrée de test unitaire dans protected_entries.yaml")
            continue
        if entry.absent:
            failures.append(f"{label}: le manifeste impose absent: true pour une traduction ajoutée")
            continue
        resolved = _load_last_wins_text(combined_text).get(addition.offset)
        if resolved != entry.expected:
            failures.append(
                f"{label}: le test attend « {entry.expected} », mais la valeur live est « {resolved} »"
            )
    return failures


def _git_output(args: Sequence[str]) -> str:
    """Return Git output or raise a concise exception suitable for a pre-commit hook.

    Decoded leniently: a staged BINARY file (savestate fixture, ROM…) makes the
    diff contain raw non-UTF-8 bytes; those lines are irrelevant to the parser
    and must not crash the hook.
    """

    result = subprocess.run(["git", *args], check=False, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip() or "git command failed")
    return result.stdout.decode("utf-8", "replace")


def _staged_files(langs: Iterable[str]) -> Dict[str, str]:
    """Read the combined file and manifest for each affected language from the index."""

    files: Dict[str, str] = {}
    for lang in set(langs):
        for path in (
            f"languages/{lang}/combined_{lang}.txt",
            f"languages/{lang}/protected_entries.yaml",
        ):
            files[path] = _git_output(["show", f":{path}"])
    return files


def main() -> int:
    """Validate staged translation additions and print actionable failures."""

    try:
        additions = parse_added_translations(_git_output(["diff", "--cached", "--unified=0", "--no-ext-diff"]))
        if not additions:
            return 0
        failures = validate_added_translations(additions, _staged_files(item.lang for item in additions))
    except RuntimeError as error:
        print(f"❌ Impossible de vérifier la couverture des traductions : {error}", file=sys.stderr)
        return 1

    if not failures:
        print(f"✓ {len({(item.lang, item.offset) for item in additions})} nouvelle(s) traduction(s) couverte(s) par un test unitaire.")
        return 0

    print("❌ Chaque nouvelle traduction doit avoir un test unitaire exact avant le commit :", file=sys.stderr)
    for failure in failures:
        print(f"  - {failure}", file=sys.stderr)
    print(
        "Ajoutez ou mettez à jour languages/<lang>/protected_entries.yaml dans le même commit, "
        "puis relancez les tests. Le hook ne doit jamais être forcé.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
