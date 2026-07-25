"""Détection des chaînes anglaises encore atteignables dans une ROM traduite."""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from typing import Iterable, Literal, Mapping, Sequence

from .collision_check import ROM_BASE, live_target, plausible_sites

ExceptionCategory = Literal["delivered", "intentional", "base-unused"]

_CONTROL_TOKEN = re.compile(r"<0x[0-9A-Fa-f]{2}>")
_ASCII_WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
_ENGLISH_CUES = frozenset(
    """
    a an the this that these those i me my we our us you your he his him she
    her they their them it its is are was were be been being have has had do
    does did can could would should will not no yes and or but if then than to
    of in on at from for with without into out up down here there where when
    what who why how all any some more most less very just still only also
    again today tomorrow yesterday please thank thanks sorry hello good great
    bad want need like know find found give gave get got take took make made
    come came go went going look see saw tell told time day night pokemon
    trainer battle move moves tm tms box mission quest route city house shop
    save game return select press active none effectiveness completed handed
    ran disappeared ready right total ever everyone everything nothing
    something
    """.split()
)
_ENGLISH_SINGLE_WORDS = frozenset(
    {"active", "none", "show", "champion", "standard", "effectiveness",
     "why", "tms", "tm", "on", "is", "was"}
)


@dataclass(frozen=True)
class LiveEnglishFinding:
    """Chaîne anglaise identique à la source, suivie depuis un pointeur vivant."""

    source_offset: int
    target_offset: int
    pointer_sites: tuple[int, ...]
    english_text: str
    spanish_translated: bool


@dataclass(frozen=True)
class EnglishException:
    """Exception revue manuellement et liée à un texte source exact."""

    source_offset: int
    category: ExceptionCategory
    english_text: str
    reason: str


@dataclass(frozen=True)
class AuditClassification:
    """Résultat trié entre contenu livré, exceptions et cas à examiner."""

    delivered: tuple[LiveEnglishFinding, ...]
    unclassified: tuple[LiveEnglishFinding, ...]
    intentional: tuple[LiveEnglishFinding, ...]
    base_unused: tuple[LiveEnglishFinding, ...]
    stale_exceptions: tuple[EnglishException, ...]


def _parse_offsets(values: object) -> list[int]:
    if not values:
        return []
    raw_values = values if isinstance(values, (list, tuple)) else [values]
    parsed: list[int] = []
    for value in raw_values:
        try:
            parsed.append(int(value, 0) if isinstance(value, str) else int(value))
        except (TypeError, ValueError):
            continue
    return parsed


def _terminated_bytes(rom: bytes, offset: int, *, limit: int = 0x1000) -> bytes | None:
    if not 0 <= offset < len(rom):
        return None
    end = rom.find(b"\xFF", offset, min(len(rom), offset + limit))
    if end == -1:
        return None
    return rom[offset : end + 1]


def _entry_bytes(entry: Mapping[str, object]) -> bytes | None:
    raw = entry.get("raw_bytes")
    if not isinstance(raw, str):
        return None
    try:
        encoded = bytes.fromhex(raw)
    except ValueError:
        return None
    return encoded if encoded.endswith(b"\xFF") else None


def _is_real_string_start(rom: bytes, offset: int) -> bool:
    return offset == 0 or (0 < offset < len(rom) and rom[offset - 1] == 0xFF)


def _spanish_changed(
    spanish_rom: bytes,
    pointer_site: int,
    source_bytes: bytes,
) -> bool:
    target = live_target(spanish_rom, pointer_site)
    if target is None:
        return False
    return _terminated_bytes(spanish_rom, target) != source_bytes


def find_live_english(
    english_rom: bytes,
    french_rom: bytes,
    spanish_rom: bytes,
    entries: Iterable[Mapping[str, object]],
) -> list[LiveEnglishFinding]:
    """Suit les pointeurs EN dans la ROM FR et retourne les textes restés anglais.

    Seuls les vrais débuts de chaînes terminées et les sites de pointeurs jugés
    plausibles par le builder sont retenus. Les octets anglais orphelins laissés
    par une relocalisation ne sont donc jamais signalés.

    Args:
        english_rom: ROM anglaise qui fournit les cellules et sites de référence.
        french_rom: ROM française construite à auditer.
        spanish_rom: ROM espagnole utilisée comme preuve qu'un contenu est livré.
        entries: Entrées de l'extraction anglaise avec ``pointer_offsets``.

    Returns:
        Détections dédupliquées et triées par offset source puis cible.
    """
    grouped: dict[tuple[int, int, str], dict[str, object]] = {}
    for entry in entries:
        try:
            source_offset = int(entry["offset"])
        except (KeyError, TypeError, ValueError):
            continue
        english_text = entry.get("decoded_text") or entry.get("text")
        source_bytes = _entry_bytes(entry)
        if (
            not isinstance(english_text, str)
            or not english_text.strip()
            or source_bytes is None
            or not _is_real_string_start(english_rom, source_offset)
            or _terminated_bytes(english_rom, source_offset) != source_bytes
        ):
            continue

        raw_sites = _parse_offsets(entry.get("pointer_offsets"))
        expected = struct.pack("<I", ROM_BASE + source_offset)
        exact_sites = [
            site
            for site in raw_sites
            if 0 <= site <= len(english_rom) - 4
            and english_rom[site : site + 4] == expected
        ]
        for site in plausible_sites(english_rom, source_offset, exact_sites):
            target_offset = live_target(french_rom, site)
            if target_offset is None:
                continue
            if _terminated_bytes(french_rom, target_offset) != source_bytes:
                continue
            key = (source_offset, target_offset, english_text)
            bucket = grouped.setdefault(
                key,
                {"sites": set(), "spanish_translated": False},
            )
            sites = bucket["sites"]
            assert isinstance(sites, set)
            sites.add(site)
            bucket["spanish_translated"] = bool(bucket["spanish_translated"]) or (
                _spanish_changed(spanish_rom, site, source_bytes)
            )

    findings = [
        LiveEnglishFinding(
            source_offset=source,
            target_offset=target,
            pointer_sites=tuple(sorted(bucket["sites"])),
            english_text=text,
            spanish_translated=bool(bucket["spanish_translated"]),
        )
        for (source, target, text), bucket in grouped.items()
    ]
    return sorted(
        findings,
        key=lambda finding: (
            finding.source_offset,
            finding.target_offset,
            finding.pointer_sites,
        ),
    )


def _looks_entirely_english(finding: LiveEnglishFinding) -> bool:
    """Écarte les noms propres et le bruit binaire sans masquer les titres courts.

    La preuve espagnole permet de retenir un titre sans mot-outil anglais
    (``bright orange cheeks``). Sans cette preuve, au moins un marqueur lexical
    anglais est exigé. Le ratio de lettres ASCII rejette les faux textes issus
    de données graphiques ou de code décodées avec la charmap.
    """
    cleaned = _CONTROL_TOKEN.sub(" ", finding.english_text)
    words = _ASCII_WORD.findall(cleaned.lower())
    ascii_letters = sum(len(word.replace("'", "")) for word in words)
    all_letters = sum(character.isalpha() for character in cleaned)
    if not words or ascii_letters / max(1, all_letters) < 0.68:
        return False
    if len(words) == 1:
        return words[0] in _ENGLISH_SINGLE_WORDS
    return finding.spanish_translated or any(
        word in _ENGLISH_CUES for word in words
    )


def filter_english_findings(
    findings: Sequence[LiveEnglishFinding],
    *,
    source_region: tuple[int, int],
) -> list[LiveEnglishFinding]:
    """Ne garde que les textes anglais linguistiques du bloc CFRU demandé."""
    start, end = source_region
    return [
        finding
        for finding in findings
        if start <= finding.source_offset < end
        and _looks_entirely_english(finding)
    ]


def classify_findings(
    findings: Sequence[LiveEnglishFinding],
    exceptions: Sequence[EnglishException],
) -> AuditClassification:
    """Classe les détections avec des exceptions liées à l'offset et au texte."""
    exception_by_key = {
        (exception.source_offset, exception.english_text): exception
        for exception in exceptions
    }
    matched: set[EnglishException] = set()
    delivered: list[LiveEnglishFinding] = []
    unclassified: list[LiveEnglishFinding] = []
    intentional: list[LiveEnglishFinding] = []
    base_unused: list[LiveEnglishFinding] = []

    for finding in findings:
        exception = exception_by_key.get(
            (finding.source_offset, finding.english_text)
        )
        if exception is None:
            unclassified.append(finding)
            continue
        matched.add(exception)
        if exception.category == "delivered":
            delivered.append(finding)
        elif exception.category == "intentional":
            intentional.append(finding)
        elif exception.category == "base-unused":
            base_unused.append(finding)
        else:
            raise ValueError(f"catégorie d'exception inconnue: {exception.category!r}")

    return AuditClassification(
        delivered=tuple(delivered),
        unclassified=tuple(unclassified),
        intentional=tuple(intentional),
        base_unused=tuple(base_unused),
        stale_exceptions=tuple(
            exception for exception in exceptions if exception not in matched
        ),
    )
