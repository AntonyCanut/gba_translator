"""Load and validate the per-language build descriptors under ``languages/``.

A descriptor is a small YAML file (``languages/<code>/lang.yaml``) declaring how
a target language is built.  Three descriptor classes exist:

- ``build: dedicated`` — French, hand-tuned byte-perfect recipe (``make build-fr``).
- ``build: generic``   — Italian / German, driven by ``scripts/build_language.py``.
- ``build: none``      — English / Spanish, reference-only extractions (no build step).
  These carry ``status: source`` or ``status: reference`` and have no output ROM.

This module has no side effects and never touches a ROM, so it is fully
unit-testable without the 32 MB game files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

# Repository root = two levels up from this file (src/i18n/registry.py).
REPO_ROOT = Path(__file__).resolve().parents[2]
LANGUAGES_DIR = REPO_ROOT / "languages"

REQUIRED_KEYS = (
    "code",
    "name",
    "status",
    "build",
    "combined",
)

# Keys required only for buildable languages (build ≠ none)
BUILDABLE_REQUIRED_KEYS = ("builder_language", "output_rom")

VALID_STATUS = {"complete", "in_progress", "source", "reference"}
VALID_BUILD = {"dedicated", "generic", "none"}


class RegistryError(RuntimeError):
    """Raised when a language descriptor is missing or malformed."""


@dataclass(frozen=True)
class LanguageConfig:
    """A single validated language descriptor."""

    code: str
    name: str
    status: str
    build: str
    combined: str
    output_rom: str = ""          # empty for build: none languages
    builder_language: str = ""    # empty for build: none languages
    native_name: str = ""
    critical: Optional[str] = None
    version_label: str = ""
    font_glyphs: str = ""
    status_abbrev: Dict[str, str] = field(default_factory=dict)
    patches: List[str] = field(default_factory=list)
    descriptor_path: Optional[Path] = None

    # -- convenience accessors -------------------------------------------------
    @property
    def is_reference(self) -> bool:
        """True for source/reference languages (build: none) — no build step."""
        return self.build == "none"

    @property
    def is_complete(self) -> bool:
        return self.status == "complete"

    @property
    def is_dedicated(self) -> bool:
        return self.build == "dedicated"

    def combined_path(self, root: Path = REPO_ROOT) -> Path:
        """Absolute path to this language's combined translation file."""
        return (root / self.combined).resolve()

    def critical_path(self, root: Path = REPO_ROOT) -> Optional[Path]:
        if not self.critical:
            return None
        return (root / self.critical).resolve()

    def output_rom_path(self, root: Path = REPO_ROOT) -> Optional[Path]:
        """None for reference languages (build: none)."""
        if not self.output_rom:
            return None
        return (root / "output" / "roms" / self.output_rom).resolve()

    def translation_json_path(self, root: Path = REPO_ROOT) -> Path:
        """Where the generic driver writes this language's translation JSON."""
        return (root / "output" / "translation" / f"{self.code}_translation_ready.json").resolve()


@dataclass(frozen=True)
class LanguageRegistry:
    """All discovered language descriptors, keyed by language code."""

    languages: Dict[str, LanguageConfig]

    def __iter__(self):
        return iter(self.languages.values())

    def __contains__(self, code: str) -> bool:
        return code in self.languages

    def __len__(self) -> int:
        return len(self.languages)

    def codes(self) -> List[str]:
        return sorted(self.languages.keys())

    def get(self, code: str) -> LanguageConfig:
        try:
            return self.languages[code]
        except KeyError:
            available = ", ".join(self.codes()) or "(none)"
            raise RegistryError(
                f"Unknown language code {code!r}. Available: {available}"
            ) from None

    def buildable(self) -> List[LanguageConfig]:
        """Buildable languages only (build ≠ none), French first."""
        return sorted(
            (c for c in self.languages.values() if not c.is_reference),
            key=lambda c: (c.code != "fr", c.code),
        )

    def references(self) -> List[LanguageConfig]:
        """Reference-only languages (build: none), sorted by code."""
        return sorted(
            (c for c in self.languages.values() if c.is_reference),
            key=lambda c: c.code,
        )


def _validate(data: dict, source: Path) -> LanguageConfig:
    missing = [key for key in REQUIRED_KEYS if not data.get(key)]
    if missing:
        raise RegistryError(
            f"{source}: missing required key(s): {', '.join(missing)}"
        )

    status = data["status"]
    if status not in VALID_STATUS:
        raise RegistryError(
            f"{source}: invalid status {status!r} (expected one of {sorted(VALID_STATUS)})"
        )

    build = data["build"]
    if build not in VALID_BUILD:
        raise RegistryError(
            f"{source}: invalid build {build!r} (expected one of {sorted(VALID_BUILD)})"
        )

    # builder_language and output_rom are required only for buildable languages.
    if build != "none":
        missing_build = [k for k in BUILDABLE_REQUIRED_KEYS if not data.get(k)]
        if missing_build:
            raise RegistryError(
                f"{source}: missing required key(s) for build={build!r}: "
                f"{', '.join(missing_build)}"
            )

    code = data["code"]
    if source.parent.name != code:
        raise RegistryError(
            f"{source}: descriptor code {code!r} does not match its folder "
            f"name {source.parent.name!r}"
        )

    # output_rom may be "~" (YAML null) for reference languages.
    raw_output_rom = data.get("output_rom") or ""
    if raw_output_rom == "~":
        raw_output_rom = ""

    return LanguageConfig(
        code=code,
        name=data["name"],
        builder_language=data.get("builder_language", ""),
        status=status,
        build=build,
        combined=data["combined"],
        output_rom=raw_output_rom,
        native_name=data.get("native_name", ""),
        critical=data.get("critical"),
        version_label=data.get("version_label", ""),
        font_glyphs=data.get("font_glyphs", ""),
        status_abbrev=dict(data.get("status_abbrev") or {}),
        patches=list(data.get("patches") or []),
        descriptor_path=source,
    )


def load_registry(languages_dir: Path = LANGUAGES_DIR) -> LanguageRegistry:
    """Discover and validate every ``languages/<code>/lang.yaml`` descriptor."""
    languages_dir = Path(languages_dir)
    if not languages_dir.is_dir():
        raise RegistryError(f"languages directory not found: {languages_dir}")

    descriptors = sorted(languages_dir.glob("*/lang.yaml"))
    if not descriptors:
        raise RegistryError(f"no language descriptors found under {languages_dir}")

    languages: Dict[str, LanguageConfig] = {}
    for descriptor in descriptors:
        with descriptor.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            raise RegistryError(f"{descriptor}: descriptor is not a mapping")
        config = _validate(data, descriptor)
        if config.code in languages:
            raise RegistryError(f"duplicate language code: {config.code}")
        languages[config.code] = config

    return LanguageRegistry(languages=languages)
