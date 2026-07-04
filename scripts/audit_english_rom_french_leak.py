#!/usr/bin/env python3
"""Audit ``input/roms/englishrom.gba`` for baked-in **French** text.

Motivation (follow-up to the P-171 move-name investigation)
-----------------------------------------------------------
The "English" source ROM everyone builds from is *not* a pristine English
CFRU/Unbound compile: it ships official French text baked into several
content tables. The move-name table at ``0x1B2980`` was the first confirmed
case (see ``languages/fr/patches/move_names.py`` / the ``FIXED_TABLE_RANGES``
docstring in ``src/core/fixed_tables.py``). Because the leak lives in the
*shared base ROM*, every language that lacks a dedicated patch for a given
table silently ships French instead of English fallback or its own text —
e.g. the Italian and German builds display French move names and French move
descriptions today.

This script extends the methodology of
``scripts/audit_it_table_offset_coverage.py`` (bucket ROM offsets by region,
diff against a reference) to the whole ROM: it scans for CFRU-encoded runs
that decode to recognisable French prose, clusters the hits by proximity,
classifies each cluster against the known content-table regions, and — when a
comparison ROM is supplied — decodes the same offset there to show that the
French is anomalous.

Why a comparison ROM settles the question
-----------------------------------------
A genuinely-fresh English compile is not checked into this repo, so
"diff englishrom.gba against a fresh compile" cannot be run directly. The
next-best independent reference is ``spanishrom.gba``: it is a *separately*
produced community translation of the same game, so wherever the English ROM
holds French but the Spanish ROM holds Spanish (or the built IT/DE ROMs hold
their own language), the French in ``englishrom.gba`` is proven to be base
contamination rather than something a pipeline wrote. Pass ``--compare`` (and
optionally repeat it) to fold that check into the report.

Usage::

    # self-contained audit of the English source ROM
    python3 scripts/audit_english_rom_french_leak.py

    # confirm each cluster against an independent translation
    python3 scripts/audit_english_rom_french_leak.py \\
        --compare input/roms/spanishrom.gba \\
        --compare output/roms/GenedRom-it.gba \\
        --json /tmp/en_french_leak.json

Caveats mirroring the sibling audit script: the French detector is a
heuristic. High-density clusters that land in a known content-table region
(move names/descriptions, item names/descriptions, Pokédex flavour, species
names) are confident; low-density clusters and ``unclassified`` regions can
include residual false positives from graphics data whose bytes happen to
decode to accent glyphs. Density + region classification is the verdict, a
single hit is not. See ``docs/english-rom-french-leak-audit.md`` for the
worked findings this script's output was cross-checked against.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.core.text_codec import TextDecoder  # noqa: E402
from src.text.charmap_data import BYTE_TO_CHAR  # noqa: E402

# --------------------------------------------------------------------------
# Known content-table regions (start, end exclusive, label). Boundaries come
# from src/core/fixed_tables.py plus offsets sampled while characterising the
# clusters this script produces (see docs/english-rom-french-leak-audit.md).
# A cluster landing in one of these is confident baked-in contamination; the
# generic Pokédex/move-description free-space relocation pool is the large
# 0x0B2*-0x0C2* / 0x044*/0x095* span the P-171 parent ticket flagged.
# --------------------------------------------------------------------------
CONTENT_REGIONS = [
    (0x01B2980, 0x01B56E6, "move names (13B fixed table)"),
    (0x03D0000, 0x03E0000, "item descriptions (general: Poke Ball/Berry/Spray)"),
    (0x0480000, 0x0490000, "move descriptions (legacy/duplicate table)"),
    (0x0440000, 0x0450000, "Pokedex flavour text (free-space pool)"),
    (0x0876074, 0x0878000, "item names (gItems, 44B stride)"),
    (0x0950000, 0x0970000, "Pokedex flavour text (free-space pool)"),
    (0x0A37000, 0x0A44000, "move descriptions / Spinda flavour (free-space pool)"),
    (0x0B20000, 0x0C24000, "move descriptions (free-space relocation pool)"),
    (0x0EB0000, 0x0EB3000, "item descriptions (drinks/vitamins)"),
    (0x1650000, 0x1668000, "Pokedex flavour text"),
    (0x166A981, 0x166E126, "species names (11B fixed table)"),
    (0x1A35800, 0x1A3ABB0, "species info / Pokedex category (fixed table)"),
]

# Accents that mark French specifically (drop the ä/ö/ü umlauts, which are
# German and also appear as noise in graphics data).
FRENCH_ACCENTS = set("àâçèéêëîïôùûœ")
_ALL_ACCENTS = "àâäçèéêëîïôöùûüœ"

_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿœŒ]+")
# "clean" word: optional leading capital then only lowercase/accented letters
# (no interior capitals) — filters out mixed-case graphics gibberish.
_CLEAN_RE = re.compile(r"^[A-ZÀ-ÖØ-Þ]?[a-z" + _ALL_ACCENTS + r"]+$")
_ASCII_VOWELS = set("aeiou")

# Accent folding used only for the English-safe-word membership test, so
# loanwords/proper nouns like "café"/"Véga" are recognised as English.
_FOLD = str.maketrans({
    "à": "a", "â": "a", "ä": "a", "ç": "c", "è": "e", "é": "e", "ê": "e",
    "ë": "e", "î": "i", "ï": "i", "ô": "o", "ö": "o", "ù": "u", "û": "u",
    "ü": "u", "œ": "oe",
})

# High-frequency French function words that do not double as common English
# words. Requiring TWO distinct ones (or an accent / strong elision) keeps
# English prose that merely contains "son"/"par"/"plus" from matching.
FRENCH_STOPWORDS = frozenset({
    "une", "des", "les", "vous", "pour", "avec", "dans", "avez", "votre",
    "nos", "est", "plus", "cette", "cet", "être", "fait", "peut", "sont",
    "ses", "leur", "qui", "que", "mais", "fois", "aux", "son", "par",
    "tous", "tout", "comme", "quand", "aussi", "très", "ces", "cela",
    "donc", "alors", "chez", "sans", "sous", "entre",
})

# Unambiguously-French elisions/particles. Bare "l'"/"d'"/"s'" are deliberately
# excluded: they collide with English ("Farfetch'd", "ol' Mel", "Borrius'").
FRENCH_ELISIONS = ("qu'", "c'est", "n'est", "-vous", "-nous", "-moi")

# Words carrying an accent that are legitimately English (é/è loanwords and
# proper nouns) — never a French signal on their own.
ENGLISH_SAFE_WORDS = frozenset({
    "poke", "vega", "cafe", "melee", "cliche", "naive", "fiance", "resume",
})


def _text_byte_class() -> bytes:
    """Byte values that decode to letters/space/accents/common punctuation."""
    keep = set(" '-.,!?°") | FRENCH_ACCENTS | set(_ALL_ACCENTS)
    vals = sorted(
        b for b, ch in BYTE_TO_CHAR.items()
        if ch.isalnum() or ch in keep
    )
    return bytes(vals)


_RUN_RE = re.compile(b"[" + re.escape(_text_byte_class()) + b"]{8,}")


def french_signal(text: str):
    """Return ``(kind, evidence)`` if ``text`` reads as French, else ``None``.

    The gate is structural (real word-like tokens dominate the string) plus a
    strong French marker: an accent inside a genuine word, an unambiguous
    elision, or two distinct French function words.
    """
    words = _WORD_RE.findall(text)
    if len(words) < 2:
        return None
    clean = [w for w in words if _CLEAN_RE.match(w) and len(w) >= 3]
    if len(clean) < 2:
        return None
    clean_letters = sum(len(w) for w in clean)
    all_letters = sum(len(w) for w in words)
    if all_letters == 0 or clean_letters / all_letters < 0.6:
        return None

    # Normalise "Poké"/"Pokédex"/"Pokémon" -> ascii so their é never fires,
    # then drop English-safe accented loanwords/proper nouns.
    lowered = [re.sub(r"pok[eé]", "poke", w.lower()) for w in clean]
    lowered = [w for w in lowered if w.translate(_FOLD) not in ENGLISH_SAFE_WORDS]

    for w in lowered:
        if any(c in FRENCH_ACCENTS for c in w) and any(v in w for v in _ASCII_VOWELS):
            return ("accent", w)

    low_text = text.lower()
    for particle in FRENCH_ELISIONS:
        if particle in low_text:
            return ("elision", particle)

    stops = {w for w in lowered if w in FRENCH_STOPWORDS}
    if len(stops) >= 2:
        return ("stopwords", ",".join(sorted(stops)[:3]))
    return None


def find_french_runs(rom: bytes):
    """Yield ``(offset, kind, evidence, decoded_text)`` for French-looking runs."""
    for match in _RUN_RE.finditer(rom):
        decoded = TextDecoder.decode_pokemon(rom[match.start():match.end()])
        sig = french_signal(decoded)
        if sig is not None:
            yield (match.start(), sig[0], sig[1], decoded)


def classify_region(offset: int) -> str:
    """Human label for the content table an offset falls in ('unclassified')."""
    for lo, hi, label in CONTENT_REGIONS:
        if lo <= offset < hi:
            return label
    return "unclassified (free-space pool or graphics noise)"


def cluster_hits(hits, gap: int = 0x1000, min_hits: int = 5):
    """Merge hits closer than ``gap`` into clusters; keep those >= ``min_hits``."""
    if not hits:
        return []
    hits = sorted(hits, key=lambda h: h[0])
    clusters = []
    current = [hits[0]]
    for hit in hits[1:]:
        if hit[0] - current[-1][0] <= gap:
            current.append(hit)
        else:
            clusters.append(current)
            current = [hit]
    clusters.append(current)
    return [c for c in clusters if len(c) >= min_hits]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=Path,
                        default=REPO_ROOT / "input/roms/englishrom.gba",
                        help="ROM to audit (default: the English source ROM)")
    parser.add_argument("--compare", type=Path, action="append", default=[],
                        help="reference ROM to decode the same offset in "
                             "(repeatable; e.g. spanishrom.gba, GenedRom-it.gba)")
    parser.add_argument("--gap", type=lambda s: int(s, 0), default=0x1000,
                        help="max byte gap between hits in one cluster")
    parser.add_argument("--min-hits", type=int, default=5,
                        help="minimum hits for a cluster to be reported")
    parser.add_argument("--json", type=Path, help="also write the report as JSON")
    args = parser.parse_args()

    if not args.rom.exists():
        print(f"error: ROM not found: {args.rom}", file=sys.stderr)
        return 2

    rom = args.rom.read_bytes()
    compares = []
    for path in args.compare:
        if path.exists():
            compares.append((path.name, path.read_bytes()))
        else:
            print(f"warning: --compare ROM not found, skipping: {path}",
                  file=sys.stderr)

    hits = list(find_french_runs(rom))
    clusters = cluster_hits(hits, gap=args.gap, min_hits=args.min_hits)

    report = {
        "rom": str(args.rom),
        "total_french_hits": len(hits),
        "reported_clusters": len(clusters),
        "clusters": [],
    }

    print(f"Audited: {args.rom}")
    print(f"French-looking runs: {len(hits)}   "
          f"clusters (>= {args.min_hits} hits): {len(clusters)}")
    if compares:
        print(f"Comparison ROMs: {', '.join(name for name, _ in compares)}")
    print()

    for cluster in sorted(clusters, key=lambda c: c[0][0]):
        start = cluster[0][0]
        end = cluster[-1][0]
        label = classify_region(start)
        report_cluster = {
            "start": f"0x{start:07X}",
            "end": f"0x{end:07X}",
            "hits": len(cluster),
            "region": label,
            "sample_en": cluster[0][3][:70],
            "comparisons": {},
        }
        print(f"0x{start:07X}-0x{end:07X}  hits={len(cluster):<4} span={end - start:#x}")
        print(f"    region: {label}")
        for off, kind, evidence, text in cluster[:3]:
            print(f"    0x{off:07X} [{kind}:{evidence}] {text[:64]!r}")
        for name, data in compares:
            other = TextDecoder.decode_pokemon(data[start:start + 40])
            same = "== EN" if data[start:start + 40] == rom[start:start + 40] else "DIFFERS"
            report_cluster["comparisons"][name] = {"same": same == "== EN", "text": other[:40]}
            print(f"    cmp {name:<22} [{same}] {other[:40]!r}")
        print()
        report["clusters"].append(report_cluster)

    # Coverage summary by region label.
    by_region: dict[str, int] = {}
    for cluster in clusters:
        by_region[classify_region(cluster[0][0])] = by_region.get(
            classify_region(cluster[0][0]), 0) + len(cluster)
    print("Hits per content region:")
    for label, count in sorted(by_region.items(), key=lambda kv: -kv[1]):
        print(f"  {count:>5}  {label}")

    if args.json:
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\nJSON written to {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
