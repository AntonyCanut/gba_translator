"""Validation de la parité FR→DE et du périmètre des tickets allemands."""

from __future__ import annotations

import fnmatch
import re
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

ALLOWED_CLASSIFICATIONS = {
    "pointer_text",
    "fixed_table",
    "asm_patch",
    "lz77_graphic",
    "font",
    "format_control",
    "rom_test",
}
ALLOWED_STATUSES = {"equivalent", "shared", "excluded"}
DE_BRANCH_PATTERN = re.compile(
    r"(?:^|[/_-])(?:de|german|allemand|deutsch)(?:[/_-]|$)", re.IGNORECASE
)
LANGUAGE_TEST_TOKENS = {
    "fr": ("fr", "french", "francais"),
    "de": ("de", "german", "allemand", "deutsch"),
}
TEST_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx"}


@dataclass(frozen=True)
class ParityEntry:
    """Décision de parité pour un traitement localisable FR."""

    source: str
    classification: str
    status: str
    target: str = ""
    reason: str = ""


@dataclass(frozen=True)
class ScopePolicy:
    """Chemins autorisés et interdits pour un ticket DE."""

    forbidden_prefixes: tuple[str, ...]
    forbidden_rom_globs: tuple[str, ...]
    shared_prefixes: tuple[str, ...]


@dataclass(frozen=True)
class ChangedPath:
    """Chemin et statut issus d'un diff Git name-status."""

    status: str
    path: str


@dataclass(frozen=True)
class DeParityManifest:
    """Inventaire versionné des traitements FR et de leur état DE."""

    descriptor_fields: tuple[ParityEntry, ...]
    build_steps: tuple[ParityEntry, ...]
    de_only_build_steps: tuple[ParityEntry, ...]
    patches: tuple[ParityEntry, ...]
    assets: tuple[ParityEntry, ...]
    rom_tests: tuple[ParityEntry, ...]
    de_only_rom_tests: tuple[ParityEntry, ...]
    scope: ScopePolicy

    @classmethod
    def load(cls, path: Path) -> DeParityManifest:
        """Charge le manifeste YAML et normalise ses sections.

        Args:
            path: Chemin du manifeste ``languages/de/parity.yaml``.

        Returns:
            Manifeste immuable prêt à valider.
        """
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if data.get("schema_version") != 1:
            raise ValueError(f"{path}: schema_version doit valoir 1")

        def entries(section: str) -> tuple[ParityEntry, ...]:
            return tuple(ParityEntry(**item) for item in data.get(section, ()))

        def test_exclusions(section: str) -> tuple[ParityEntry, ...]:
            raw = data.get(section) or {}
            reason = raw.get("reason", "")
            return tuple(
                ParityEntry(
                    source=source,
                    classification="rom_test",
                    status="excluded",
                    reason=reason,
                )
                for source in raw.get("sources", ())
            )

        raw_scope = data.get("scope_guard") or {}
        scope = ScopePolicy(
            forbidden_prefixes=tuple(raw_scope.get("forbidden_prefixes") or ()),
            forbidden_rom_globs=tuple(raw_scope.get("forbidden_rom_globs") or ()),
            shared_prefixes=tuple(raw_scope.get("shared_prefixes") or ()),
        )
        return cls(
            descriptor_fields=entries("descriptor_fields"),
            build_steps=entries("build_steps"),
            de_only_build_steps=entries("de_only_build_steps"),
            patches=entries("patches"),
            assets=entries("assets"),
            rom_tests=entries("rom_tests") + test_exclusions("rom_test_exclusions"),
            de_only_rom_tests=test_exclusions("de_only_rom_tests"),
            scope=scope,
        )

    def validate(self, root: Path) -> list[str]:
        """Compare la matrice aux descripteurs et fichiers réellement versionnés.

        Args:
            root: Racine du dépôt ``gba_translator``.

        Returns:
            Liste vide lorsque la parité est complète, sinon erreurs actionnables.
        """
        failures: list[str] = []
        fr_config = _load_yaml(root / "languages/fr/lang.yaml")
        de_config = _load_yaml(root / "languages/de/lang.yaml")

        expected_fields = set(fr_config) - {"patches"}
        failures.extend(
            _compare_inventory(
                expected_fields,
                {entry.source for entry in self.descriptor_fields},
                "champ FR absent de la matrice",
                "champ inconnu dans la matrice",
            )
        )
        expected_steps = set(fr_config.get("patches") or ())
        failures.extend(
            _compare_inventory(
                expected_steps,
                {entry.source for entry in self.build_steps},
                "étape FR absente de la matrice",
                "étape FR inconnue dans la matrice",
            )
        )
        fr_patches = {
            path.relative_to(root).as_posix()
            for path in (root / "languages/fr/patches").glob("*.py")
        }
        failures.extend(
            _compare_inventory(
                fr_patches,
                {entry.source for entry in self.patches},
                "patch FR absent de la matrice",
                "patch FR inconnu dans la matrice",
            )
        )
        fr_assets = {
            path.relative_to(root).as_posix()
            for path in (root / "languages/fr/sprites").iterdir()
            if path.is_file()
        }
        failures.extend(
            _compare_inventory(
                fr_assets,
                {entry.source for entry in self.assets},
                "asset FR absent de la matrice",
                "asset FR inconnu dans la matrice",
            )
        )

        expected_fr_tests = _discover_language_tests(root, "fr")
        failures.extend(
            _compare_inventory(
                expected_fr_tests,
                {entry.source for entry in self.rom_tests},
                "test FR absent de la matrice",
                "test FR inconnu dans la matrice",
            )
        )

        expected_de_tests = _discover_language_tests(root, "de")
        covered_de_tests = {
            entry.target for entry in self.rom_tests if entry.status != "excluded"
        }
        failures.extend(
            _compare_inventory(
                expected_de_tests - covered_de_tests,
                {entry.source for entry in self.de_only_rom_tests},
                "test propre à DE absent de la matrice",
                "test propre à DE inconnu dans la matrice",
            )
        )

        file_sections = (
            self.patches,
            self.assets,
            self.rom_tests,
            self.de_only_rom_tests,
        )
        for section in (
            self.descriptor_fields,
            self.build_steps,
            self.de_only_build_steps,
            self.patches,
            self.assets,
            self.rom_tests,
            self.de_only_rom_tests,
        ):
            failures.extend(_validate_entries(section))
        for section in file_sections:
            for entry in section:
                if "/" in entry.source and not (root / entry.source).is_file():
                    failures.append(f"source introuvable: {entry.source}")
                if (
                    entry.status != "excluded"
                    and "/" in entry.target
                    and not (root / entry.target).is_file()
                ):
                    failures.append(f"équivalent introuvable: {entry.target}")

        for entry in self.descriptor_fields:
            if entry.status != "excluded" and entry.target not in de_config:
                failures.append(f"champ DE déclaré absent de lang.yaml: {entry.target}")

        de_steps = set(de_config.get("patches") or ())
        for entry in self.build_steps:
            if entry.status != "excluded" and entry.target not in de_steps:
                failures.append(
                    f"étape DE déclarée absente de languages/de/lang.yaml: {entry.target}"
                )
        covered_de_steps = {
            entry.target for entry in self.build_steps if entry.status != "excluded"
        }
        failures.extend(
            _compare_inventory(
                de_steps - covered_de_steps,
                {entry.source for entry in self.de_only_build_steps},
                "étape propre à DE absente de la matrice",
                "étape propre à DE inconnue dans la matrice",
            )
        )
        return failures


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise TypeError(f"{path}: mapping YAML attendu")
    return data


def _compare_inventory(
    expected: set[str], actual: set[str], missing_label: str, extra_label: str
) -> list[str]:
    failures = [f"{missing_label}: {item}" for item in sorted(expected - actual)]
    failures.extend(f"{extra_label}: {item}" for item in sorted(actual - expected))
    return failures


def _discover_language_tests(root: Path, language: str) -> set[str]:
    """Découvre les tests explicitement rattachés à une langue par chemin ou nom."""
    tests_root = root / "tests"
    aliases = LANGUAGE_TEST_TOKENS[language]
    token = re.compile(
        rf"(?:^|[_-])(?:{'|'.join(map(re.escape, aliases))})(?:[_-]|$)"
    )
    discovered: set[str] = set()
    for path in tests_root.rglob("*"):
        is_test_file = (
            path.is_file()
            and path.suffix in TEST_SUFFIXES
            and (
                path.name.startswith("test_")
                or ".test." in path.name
                or ".spec." in path.name
            )
        )
        if not is_test_file:
            continue
        relative_to_tests = path.relative_to(tests_root)
        language_directory = any(
            part.lower() in aliases for part in relative_to_tests.parts[:-1]
        )
        if language_directory or token.search(path.stem.lower()):
            discovered.add(path.relative_to(root).as_posix())
    return discovered


def _validate_entries(entries: Sequence[ParityEntry]) -> list[str]:
    failures: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if entry.source in seen:
            failures.append(f"entrée dupliquée: {entry.source}")
        seen.add(entry.source)
        if entry.classification not in ALLOWED_CLASSIFICATIONS:
            failures.append(
                f"classification invalide pour {entry.source}: {entry.classification}"
            )
        if entry.status not in ALLOWED_STATUSES:
            failures.append(f"statut invalide pour {entry.source}: {entry.status}")
        if entry.status == "excluded" and not entry.reason.strip():
            failures.append(f"exclusion sans justification: {entry.source}")
        if entry.status != "excluded" and not entry.target.strip():
            failures.append(f"équivalent DE manquant: {entry.source}")
    return failures


def parse_name_status(output: str) -> list[ChangedPath]:
    """Parse un diff name-status et conserve la destination des renommages.

    Args:
        output: Sortie texte de ``git diff --name-status``.

    Returns:
        Changements normalisés dans l'ordre du diff.
    """
    changes: list[ChangedPath] = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        if status.startswith("R") and len(parts) >= 3:
            changes.append(ChangedPath(status="D", path=parts[-2]))
            changes.append(ChangedPath(status="A", path=parts[-1]))
        else:
            changes.append(ChangedPath(status=status, path=parts[-1]))
    return changes


def staged_changes(root: Path) -> list[ChangedPath]:
    """Retourne les chemins actuellement stagés dans le dépôt.

    Args:
        root: Racine du dépôt Git.

    Returns:
        Changements présents dans l'index.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-status"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_name_status(result.stdout)


def changed_since(root: Path, base_ref: str) -> list[ChangedPath]:
    """Retourne les chemins modifiés entre ``base_ref`` et HEAD.

    Args:
        root: Racine du dépôt Git.
        base_ref: Référence Git servant de base de comparaison.

    Returns:
        Changements de la branche courante depuis la base.
    """
    result = subprocess.run(
        ["git", "diff", "--name-status", f"{base_ref}...HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_name_status(result.stdout)


def current_branch(root: Path) -> str:
    """Lit le nom de branche courant sans modifier le dépôt.

    Args:
        root: Racine du dépôt Git.

    Returns:
        Nom de branche, ou chaîne vide en HEAD détachée.
    """
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def validate_de_scope(
    changes: Iterable[ChangedPath], branch_name: str, policy: ScopePolicy
) -> list[str]:
    """Valide qu'un diff de ticket DE reste isolé des langues FR et IT.

    Args:
        changes: Chemins modifiés et statuts Git.
        branch_name: Branche permettant d'identifier un ticket DE.
        policy: Préfixes et motifs versionnés dans le manifeste.

    Returns:
        Liste vide si le périmètre est respecté, sinon violations détaillées.
    """
    if not DE_BRANCH_PATTERN.search(branch_name):
        return []

    changes = tuple(changes)
    failures: list[str] = []
    for change in changes:
        if any(change.path.startswith(prefix) for prefix in policy.forbidden_prefixes):
            failures.append(f"chemin FR/IT interdit dans un ticket DE: {change.path}")
        elif any(fnmatch.fnmatch(change.path, pattern) for pattern in policy.forbidden_rom_globs):
            failures.append(f"ROM FR/IT livrée interdite dans un ticket DE: {change.path}")

    shared_changed = any(
        any(change.path.startswith(prefix) for prefix in policy.shared_prefixes)
        for change in changes
    )
    regression_test = any(
        change.status != "D"
        and (
            change.path.startswith("tests/")
            or change.path.startswith("emulator-web/tests/")
        )
        and "/de/" not in change.path
        and not change.path.endswith("_de.py")
        for change in changes
    )
    if shared_changed and not regression_test:
        failures.append("code partagé modifié sans test de non-régression multilingue")
    return failures
