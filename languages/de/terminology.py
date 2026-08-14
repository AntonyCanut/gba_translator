"""Accès unique au glossaire allemand figé utilisé par les patchs ROM."""

from __future__ import annotations

from pathlib import Path

import yaml

GLOSSARY_PATH = Path(__file__).resolve().parent / "data/official_terminology.yaml"
OFFICIAL_TERMINOLOGY: dict = yaml.safe_load(GLOSSARY_PATH.read_text(encoding="utf-8"))


def section(name: str) -> dict:
    """Retourne une section dictionnaire du glossaire ou échoue au build."""
    value = OFFICIAL_TERMINOLOGY.get(name)
    if not isinstance(value, dict):
        raise TypeError(f"invalid or missing German terminology section: {name}")
    return value
