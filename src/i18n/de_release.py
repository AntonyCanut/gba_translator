"""Chargement du contrat de certification de la ROM allemande."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

REQUIRED_SURFACES = {
    "boot",
    "new_game",
    "party",
    "summary",
    "battle",
    "pokedex",
    "dexnav",
    "pc",
    "shop",
    "world_map",
    "trainer_card",
    "missions",
}


@dataclass(frozen=True)
class ResidueRule:
    """Plage revue de chaînes anglaises encore vivantes."""

    name: str
    start: int
    end: int
    reason: str

    def contains(self, offset: int) -> bool:
        return self.start <= offset <= self.end


@dataclass(frozen=True)
class DeReleaseManifest:
    """Attendus immuables utilisés par la porte finale DE."""

    coverage: dict[str, int]
    live_english_count: int
    live_english_sha256: str
    live_english_rules: tuple[ResidueRule, ...]
    graphics_count: int
    graphics_sha256: str
    captures_count: int
    captures_sha256: str
    rom_sha256: str
    surfaces: dict[str, tuple[str, ...]]

    @classmethod
    def load(cls, path: Path) -> "DeReleaseManifest":
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if payload.get("schema_version") != 1:
            raise ValueError(f"{path}: schema_version doit valoir 1")
        live = payload.get("live_english") or {}
        graphics = payload.get("graphics") or {}
        captures = payload.get("captures") or {}
        rules = tuple(
            ResidueRule(
                name=name,
                start=int(rule["start"], 0),
                end=int(rule["end"], 0),
                reason=str(rule.get("reason", "")),
            )
            for name, rule in (live.get("classifications") or {}).items()
        )
        return cls(
            coverage={
                str(key): int(value)
                for key, value in (payload.get("coverage") or {}).items()
            },
            live_english_count=int(live.get("count", 0)),
            live_english_sha256=str(live.get("sha256", "")),
            live_english_rules=rules,
            graphics_count=int(graphics.get("count", 0)),
            graphics_sha256=str(graphics.get("sha256", "")),
            captures_count=int(captures.get("count", 0)),
            captures_sha256=str(captures.get("sha256", "")),
            rom_sha256=str(payload.get("rom_sha256", "")),
            surfaces={
                str(name): tuple(str(item) for item in evidence)
                for name, evidence in (payload.get("surfaces") or {}).items()
            },
        )

    def classify_live_english(self, offset: int) -> str | None:
        for rule in self.live_english_rules:
            if rule.contains(offset):
                return rule.name
        return None

    def missing_evidence(self, root: Path) -> list[str]:
        return sorted(
            evidence
            for items in self.surfaces.values()
            for evidence in items
            if not (root / evidence).is_file()
        )
