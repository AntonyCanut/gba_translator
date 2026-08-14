"""English-toponym policy for the German Pokemon Unbound build.

The English ROM is authoritative.  Aliases are replaced only when the paired
English source entry contains the matching canonical name, which prevents
common German words such as ``Wald`` or ``Krater`` from being rewritten.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = ROOT / "languages/de/data/english_toponyms.yaml"

_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")
_CONTROL_RE = re.compile(r"\\[nlp]|<0x(?:79|7A|7B|7C|FA|FB|FE)>", re.IGNORECASE)
_CONTROL_NAMES = {
    r"\n": "NL", r"\l": "LINE", r"\p": "PAGE",
    "<0XFE>": "NL", "<0XFA>": "LINE", "<0XFB>": "PAGE",
    "<0X79>": "UP", "<0X7A>": "DOWN", "<0X7B>": "LEFT", "<0X7C>": "RIGHT",
}


@dataclass(frozen=True)
class Toponym:
    canonical: str
    anchors: tuple[int, ...]
    aliases: tuple[str, ...]


def load_catalog(path: Path = DEFAULT_CATALOG) -> tuple[Toponym, ...]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return tuple(
        Toponym(
            canonical=item["canonical"],
            anchors=tuple(item.get("anchors", [])),
            aliases=tuple(item.get("aliases", [])),
        )
        for item in raw["toponyms"]
    )


def load_combined(path: Path) -> dict[int, str]:
    """Return the live last-wins value for every combined-file offset."""
    mapping: dict[int, str] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for raw in handle:
            match = _LINE_RE.match(raw.rstrip("\r\n"))
            if match:
                mapping[int(match.group(1), 16)] = match.group(2)
    return mapping


def _replace_alias(text: str, alias: str, canonical: str) -> str:
    # ``combined_*.txt`` stores line controls as the two literal characters
    # ``\\n``/``\\l``/``\\p``.  Their final letter is a word character, so a
    # plain ``(?<!\\w)`` boundary would miss a name beginning on the next line.
    pattern = re.compile(
        rf"(?:(?<=\\n)|(?<=\\l)|(?<=\\p)|(?<!\w))"
        rf"{re.escape(alias)}(?!\w)",
        re.IGNORECASE,
    )
    return pattern.sub(canonical, text)


def _source_spelling(english_text: str, canonical: str) -> str | None:
    """Return the spelling/case used by this exact EN surface."""
    direct = re.search(re.escape(canonical), english_text, re.IGNORECASE)
    if direct:
        return direct.group(0)
    parts = canonical.split(" ")
    separator = r"(?:\s|\\[nlp]|<0x(?:FA|FB|FE)>)+"
    flexible = re.search(separator.join(map(re.escape, parts)), english_text, re.IGNORECASE)
    if flexible:
        return canonical.upper() if flexible.group(0).isupper() else canonical
    return None


def restore_toponyms(
    english_text: str,
    translated_text: str,
    records: tuple[Toponym, ...],
) -> str:
    """Restore only proper names that are explicitly present in EN source."""
    restored = translated_text
    placeholders: dict[str, str] = {}
    for index, record in enumerate(
        sorted(records, key=lambda item: len(item.canonical), reverse=True)
    ):
        source_spelling = _source_spelling(english_text, record.canonical)
        if source_spelling is None:
            continue
        # Shield every restored occurrence until all shorter aliases have been
        # processed.  This prevents ``Magnolia`` from turning the already
        # restored ``Magnolia Fields`` into ``Magnolia Town Fields``.
        placeholder = f"<TOPONYM_{index}>"
        placeholders[placeholder] = source_spelling
        candidates = sorted(
            (record.canonical, *record.aliases), key=len, reverse=True
        )
        for candidate in candidates:
            restored = _replace_alias(restored, candidate, placeholder)
    for placeholder, source_spelling in placeholders.items():
        restored = restored.replace(placeholder, source_spelling)
    return restored


def control_signature(text: str) -> tuple[str, ...]:
    """Normalise source spellings of line/page controls and direction arrows."""
    signature = []
    for match in _CONTROL_RE.finditer(text):
        token = match.group(0)
        key = token if token.startswith("\\") else token.upper()
        signature.append(_CONTROL_NAMES[key])
    return tuple(signature)


def audit_combined(
    english_path: Path,
    translated_path: Path,
    records: tuple[Toponym, ...],
) -> list[str]:
    """Report DE entries whose EN-anchored proper name is not canonical."""
    english = load_combined(english_path)
    translated = load_combined(translated_path)
    violations: list[str] = []
    for offset, de_text in translated.items():
        en_text = english.get(offset)
        if not en_text:
            continue
        expected = restore_toponyms(en_text, de_text, records)
        if expected != de_text:
            violations.append(f"0x{offset:08X}: {de_text!r} -> {expected!r}")
    return violations
