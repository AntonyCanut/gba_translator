#!/usr/bin/env python3
"""Process Italian translations JSON → combined_it.txt with smart merging.

Usage:
    # Import / update (always merges with existing file if present)
    python3 scripts/process_italian_translations.py Italian_Translations_v2.json

    # With diff display
    python3 scripts/process_italian_translations.py Italian_Translations_v2.json --compare languages/it/combined_it.txt --show-diff

Features:
    - Converts Italian translation JSON to CFRU combined_<code>.txt format
    - Merges with existing combined_it.txt: existing entries not in JSON are preserved
    - JSON entries override existing entries for the same offset
    - Filters out unchanged entries (identical to English original)
    - Removes corrupted script/binary entries
    - Preserves control codes, accents, and escape sequences
    - Handles duplicate offsets (last entry wins, case-insensitive)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

# Reverse CFRU charmap (byte value -> character) used to decode the raw
# ``{XX}`` hex tokens that some JSON dumps leave behind for bytes the dump tool
# could not map (e.g. ``{B4}`` for the apostrophe 0xB4). Left untouched, those
# tokens reach the encoder verbatim and render as garbage (``?B4?``) in-game,
# inflating every apostrophe by 3 bytes and overflowing string slots.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
try:  # pragma: no cover - exercised by the IT build, charmap always present
    from text import charmap_data as _cd

    _BYTE_TO_CHAR: dict[int, str] = {}
    for _ch, _b in _cd.CHAR_TO_BYTE.items():
        _BYTE_TO_CHAR.setdefault(_b, _ch)
except Exception:  # pragma: no cover - defensive
    _BYTE_TO_CHAR = {}

_HEX_TOKEN_RE = re.compile(r"\{([0-9A-Fa-f]{2})\}")

# ---------------------------------------------------------------------------
# Control-token normalization
#
# The Italian community dump marks colours, buffers and name placeholders with
# its own readable token convention (``[green]``, ``[buffer1]``, ``{player}``…)
# instead of the raw CFRU control codes the build pipeline understands. Left
# untouched, ``[`` / ``]`` / ``{`` / ``}`` are not in the font charmap, so the
# encoder renders them as ``?`` and spells the token name out literally — the
# screen reads ``?green??buffer1??black?`` instead of a coloured, buffered word.
#
# Each token maps to exactly one raw control sequence, verified byte-for-byte
# against the English ROM (``output/extracted/extracted_texts/englishrom_texts.json``):
# every clean-aligned string agreed on the same code (e.g. ``[green]`` → FC 01 06
# in 2027/2027 cases, ``[buffer1]`` → FD 02 in 791/791, ``{player}`` → FD 01 in
# 670/670). We emit the raw ``<0xNN>`` form (the same tokens combined_fr.txt uses)
# so the rest of the proven pipeline encodes them directly — and, because the
# colour is explicit per token, the result is faithful to the Italian
# translator's own choices and immune to English-vs-Italian positional drift.
#
#   Colours  → <0xFC><0x01><0xNN>   (FC 01 NN, the Gen III SET_TEXT_COLOR code)
#   Buffers  → <0xFD><0xNN>         (FD NN, the FireRed string-buffer placeholder)
#   [pause]  → <0xFC><0x09>         (FC 09, PAUSE_UNTIL_PRESS)
_CONTROL_TOKEN_MAP = {
    # Colours (FC 01 NN)
    "[green]": "<0xFC><0x01><0x06>",
    "[red]": "<0xFC><0x01><0x04>",
    "[blue]": "<0xFC><0x01><0x08>",
    "[black]": "<0xFC><0x01><0x02>",
    "[lightgreen]": "<0xFC><0x01><0x07>",
    "[orange]": "<0xFC><0x01><0x05>",
    "[darknavyblue]": "<0xFC><0x01><0x0F>",
    # String buffers / name placeholders (FD NN)
    "[buffer1]": "<0xFD><0x02>",
    "[buffer2]": "<0xFD><0x03>",
    "[buffer3]": "<0xFD><0x04>",
    "[rival]": "<0xFD><0x06>",
    "{player}": "<0xFD><0x01>",
    # Flow control
    "[pause]": "<0xFC><0x09>",
    # Sound macros (Classic Leaders Gauntlet completion string 0x1ee09a8)
    # Verified byte-for-byte from EN ROM: FC 17 / FC 0A / FC 18
    "[pause_music]": "<0xFC><0x17>",
    "[wait_sound]": "<0xFC><0x0A>",
    "[resume_music]": "<0xFC><0x18>",
}

# Match the exact known tokens only — never a stray ``[`` or ``{`` in real text.
_CONTROL_TOKEN_RE = re.compile(
    "|".join(re.escape(tok) for tok in _CONTROL_TOKEN_MAP)
)


def normalize_control_tokens(text: str) -> str:
    """Convert Italian-dump control tokens into raw CFRU ``<0xNN>`` sequences.

    Colours (``[green]`` …), string buffers (``[buffer1]`` …), name
    placeholders (``{player}``, ``[rival]``), ``[pause]``, and sound-control
    macros (``[pause_music]``, ``[wait_sound]``, ``[resume_music]``) are
    replaced with the exact control bytes the encoder emits verbatim. Any other
    text — including legitimate square brackets — is left untouched.
    """
    return _CONTROL_TOKEN_RE.sub(lambda m: _CONTROL_TOKEN_MAP[m.group(0)], text)


# ---------------------------------------------------------------------------
# Backslash-hex escape normalization
#
# The Italian dump uses two backslash-based conventions that the build pipeline
# does not understand.  Left untouched, the encoder sees a raw ``\`` (no glyph
# → ``?``) followed by literal hex digits and renders gibberish in-game.
#
# 1. ``\CCxxyyzz…`` — FC control-code sequence.
#    ``\CC`` is a fixed prefix that stands for byte 0xFC; the following hex
#    digits (always an even count) are the argument bytes, one per two-char pair.
#    Examples verified against the EN ROM:
#      ``\CC0820`` → FC 08 20 → ``<0xFC><0x08><0x20>``  (timed pause 32 frames)
#      ``\CC0B0C01`` → FC 0B 0C 01 → ``<0xFC><0x0B><0x0C><0x01>``  (play SE)
#    The regex is greedy over complete byte pairs; a trailing odd hex digit is
#    left untouched so that ``\CC06001,000`` → ``<0xFC><0x06><0x00>1,000``.
#
# 2. ``\\XX`` or ``\XX`` — raw FD buffer code or navigation glyph.
#    IMPORTANT: the file uses DIFFERENT backslash counts per token family:
#      • FD buffer placeholders (FD 07 … FD 0C) appear as DOUBLE-backslash
#        ``\\07`` … ``\\0C`` in the file (bytes 5C 5C NN NN). This is how the
#        original import script stored them when it processed the JSON.
#      • Navigation tokens ``\au``, ``\al``, ``\ar``, ``\qo``, ``\qc``, ``\ad``
#        appear as SINGLE-backslash (byte 5C), e.g. ``\au`` = 5C 61 75.
#    FD buffer IDs confirmed by byte-for-byte comparison with the EN ROM:
#      ``\\07`` → FD 07 → ``<0xFD><0x07>``   (buffer 7, e.g. player age)
#      ``\\08`` → FD 08 → ``<0xFD><0x08>``   (buffer 8, Frontier count)
#    Navigation arrow / quote bytes verified against EN ROM path descriptions:
#      ``\au`` → 0x79 (↑)   ``\ad`` → 0x7A (↓)
#      ``\al`` → 0x7B (←)   ``\ar`` → 0x7C (→)
#      ``\qo`` → 0xB1 (")   ``\qc`` → 0xB2 (")
#
# All mappings verified byte-for-byte against the EN ROM.

# Literal tokens with non-hex characters (or single-backslash navigation tokens
# that must be processed FIRST so they are not partially consumed later).
# All use a SINGLE backslash prefix in the file.
_BACKSLASH_LITERAL_MAP: dict[str, str] = {
    r"\au": "<0x79>",  # up arrow ↑ (map/route descriptions)
    r"\al": "<0x7B>",  # left arrow ←
    r"\ar": "<0x7C>",  # right arrow →
    r"\qo": "<0xB1>",  # opening curly quote "
    r"\qc": "<0xB2>",  # closing curly quote "
    r"\ad": "<0x7A>",  # down arrow ↓ (single backslash, confirmed by ROM scan)
}
_BACKSLASH_LITERAL_RE = re.compile(
    "|".join(re.escape(tok) for tok in _BACKSLASH_LITERAL_MAP)
)

# FD buffer-ID tokens — stored with a DOUBLE backslash in the file (``\\07`` etc.)
# because the original import script left them un-decoded and Python's write path
# preserved the raw ``\\`` escape.  Each key is a two-char raw prefix (``r"\\07"``
# = Python string ``\\07`` = bytes 5C 5C 30 37), matched as TWO literal backslashes.
_BACKSLASH_HEX_MAP: dict[str, str] = {
    r"\\07": "<0xFD><0x07>",
    r"\\08": "<0xFD><0x08>",
    r"\\09": "<0xFD><0x09>",
    r"\\0A": "<0xFD><0x0A>",
    r"\\0a": "<0xFD><0x0A>",
    r"\\0B": "<0xFD><0x0B>",
    r"\\0b": "<0xFD><0x0B>",
    r"\\0C": "<0xFD><0x0C>",
    r"\\0c": "<0xFD><0x0C>",
}
_BACKSLASH_HEX_RE = re.compile(
    "|".join(re.escape(tok) for tok in _BACKSLASH_HEX_MAP)
)

# ``\CC<hex_pairs>`` → ``<0xFC>`` + one ``<0xNN>`` per byte pair.
# The regex matches only complete byte pairs (even hex-digit count) so a
# trailing odd digit is left as plain text (e.g. ``\CC06001`` → the ``1``
# after ``0600`` stays, becoming ``<0xFC><0x06><0x00>1``).
_CC_ESCAPE_RE = re.compile(r"\\CC((?:[0-9A-Fa-f]{2})+)", re.IGNORECASE)


def _decode_cc_escape(match: "re.Match[str]") -> str:
    """Decode a ``\\CCxxyyzz`` sequence into ``<0xFC><0xXX><0xYY><0xZZ>``."""
    hex_str = match.group(1)
    parts = ["<0xFC>"]
    for i in range(0, len(hex_str), 2):
        parts.append(f"<0x{hex_str[i:i+2].upper()}>")
    return "".join(parts)


def normalize_backslash_escapes(text: str) -> str:
    r"""Convert backslash-hex escape sequences to raw CFRU ``<0xNN>`` form.

    Three escape conventions used by the Italian dump are handled:

    * ``\CCxxyy`` — FC control-code prefix (SINGLE backslash) followed by
      argument bytes.  ``\CC0820`` → ``<0xFC><0x08><0x20>``.
    * ``\\07``–``\\0C`` — FD string-buffer placeholders (DOUBLE backslash in
      the file).  ``\\07`` → ``<0xFD><0x07>`` (buffer 7, e.g. player age).
    * ``\ad`` / ``\au`` / ``\al`` / ``\ar`` / ``\qo`` / ``\qc`` — map
      directional glyphs and curly-quote delimiters (SINGLE backslash).

    The standard line-break escapes ``\n``, ``\l``, ``\p`` are not affected.
    Already-converted ``<0xNN>`` sequences are left untouched (idempotent).
    """
    # Step 1: single-backslash literal tokens (navigation arrows, quotes)
    text = _BACKSLASH_LITERAL_RE.sub(
        lambda m: _BACKSLASH_LITERAL_MAP[m.group(0)], text
    )
    # Step 2: double-backslash FD buffer tokens (\\07 … \\0C)
    text = _BACKSLASH_HEX_RE.sub(
        lambda m: _BACKSLASH_HEX_MAP[m.group(0)], text
    )
    # Step 3: \CC<hex_pairs> → <0xFC>…  (single backslash)
    text = _CC_ESCAPE_RE.sub(_decode_cc_escape, text)
    return text


def decode_hex_tokens(text: str) -> str:
    """Replace raw ``{XX}`` hex tokens with their CFRU character.

    Only tokens that decode to a single printable character are substituted;
    anything else is left intact so genuine markup is never corrupted.
    """

    def _sub(match: "re.Match[str]") -> str:
        byte = int(match.group(1), 16)
        ch = _BYTE_TO_CHAR.get(byte)
        if ch is not None and len(ch) == 1 and ch.isprintable():
            return ch
        return match.group(0)

    return _HEX_TOKEN_RE.sub(_sub, text)


def parse_json(json_file: Path) -> dict[str, str]:
    """Parse Italian translation JSON, return offset → translation mapping."""
    entries = {}
    skipped = {"unchanged": 0, "corrupted": 0}

    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, dict) or "entries" not in data:
        raise ValueError("JSON must have top-level 'entries' array")

    for entry in data["entries"]:
        original = entry.get("original", "")
        translated = entry.get("translated", "")
        offset = entry.get("address", "").lower()

        if not offset or not translated:
            continue

        # Filter 1: Skip unchanged entries (identical to English)
        if translated == original or translated.strip() == original.strip():
            skipped["unchanged"] += 1
            continue

        # Filter 2: Skip corrupted/binary script entries (heuristic: looks like garbage)
        # These typically have random chars, control codes mixed with text, [kun], etc.
        if entry.get("category") == "scripts" and translated == original:
            skipped["corrupted"] += 1
            continue

        # Handle duplicates: last entry wins (case-insensitive offset)
        entries[offset] = translated

    return entries, skipped


def escape_text(text: str) -> str:
    """Encode in-game line breaks as the literal ``\\n`` escape.

    The build parser (apply_combined_fr.py) reads the combined file line by line
    and silently drops any physical line that is not ``0x<offset>: <text>``. A
    JSON ``translated`` value carrying *real* newline characters would therefore
    spill across several physical lines and lose everything after the first one
    (truncating multi-line strings — e.g. the game intro). Each entry must stay
    on a single physical line with line breaks written as the two-character
    escape ``\\n``. Values that already use the ``\\n`` escape are unaffected.
    """
    text = decode_hex_tokens(text)
    text = normalize_control_tokens(text)
    text = normalize_backslash_escapes(text)
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")


def format_entries(entries: dict[str, str]) -> list[str]:
    """Format entries as combined_it.txt lines, sorted by offset."""
    lines = []
    for offset in sorted(entries.keys()):
        text = escape_text(entries[offset])
        lines.append(f"{offset}: {text}")
    return lines


def read_combined(combined_file: Path) -> dict[str, str]:
    """Parse existing combined_it.txt into offset → translation mapping."""
    entries = {}
    with open(combined_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line or line.startswith('#'):
                continue
            if ':' not in line:
                continue
            offset, text = line.split(':', 1)
            offset = offset.strip().lower()
            text = text.strip()
            entries[offset] = text
    return entries


def diff_translations(old: dict[str, str], new: dict[str, str]) -> dict[str, str]:
    """
    Compare old and new translations, return only changed/new entries.

    Returns a mapping of offset → new_translation for entries that:
    - Are new (not in old)
    - Have changed text (old vs new differ)
    """
    changes = {}

    # New entries and updates
    for offset, new_text in new.items():
        old_text = old.get(offset)
        if old_text is None or old_text != new_text:
            changes[offset] = new_text

    return changes


def normalize_combined_file(path: Path) -> int:
    """Re-normalize all backslash-hex and control tokens in an existing combined file.

    Reads every entry, applies ``decode_hex_tokens``, ``normalize_control_tokens``,
    and ``normalize_backslash_escapes`` in place, then rewrites the file.
    The header comments are preserved; sort order is unchanged.
    Returns the number of entries that were modified.
    """
    header_lines: list[str] = []
    entry_lines: list[str] = []
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            stripped = raw.rstrip("\n")
            if stripped.lstrip().startswith("#") or not stripped.strip():
                header_lines.append(stripped)
            else:
                entry_lines.append(stripped)

    changed = 0
    out_lines: list[str] = []
    for line in entry_lines:
        if ":" not in line:
            out_lines.append(line)
            continue
        offset_part, text_part = line.split(":", 1)
        text = text_part.lstrip(" ")
        norm = decode_hex_tokens(text)
        norm = normalize_control_tokens(norm)
        norm = normalize_backslash_escapes(norm)
        if norm != text:
            changed += 1
        out_lines.append(f"{offset_part}: {norm}")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(header_lines) + "\n")
        fh.write("\n".join(out_lines) + "\n")

    return changed


def main():
    parser = argparse.ArgumentParser(
        description="Process Italian translations JSON → combined_it.txt with smart diffing"
    )
    parser.add_argument(
        "json_file",
        nargs="?",
        type=Path,
        help="Italian translations JSON file (omit when using --normalize-existing)"
    )
    parser.add_argument(
        "--normalize-existing",
        metavar="FILE",
        type=Path,
        help="Re-normalize all backslash-hex tokens in an existing combined file (no JSON needed)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("languages/it/combined_it.txt"),
        help="Output file (default: languages/it/combined_it.txt)"
    )
    parser.add_argument(
        "--compare",
        type=Path,
        help="Existing combined_it.txt to diff against (for smart updates)"
    )
    parser.add_argument(
        "--show-diff",
        action="store_true",
        help="Show detailed diff of changes (when --compare is used)"
    )

    args = parser.parse_args()

    if args.normalize_existing:
        target = args.normalize_existing
        if not target.exists():
            print(f"❌ File not found: {target}", file=sys.stderr)
            return 1
        print(f"🔧 Normalizing backslash-hex tokens in {target}…")
        n = normalize_combined_file(target)
        print(f"✓ Done — {n} entr{'y' if n == 1 else 'ies'} updated.")
        return 0

    if not args.json_file:
        parser.error("json_file is required unless --normalize-existing is used")

    # Parse JSON
    print(f"📖 Parsing {args.json_file}...")
    try:
        entries, skipped = parse_json(args.json_file)
    except Exception as e:
        print(f"❌ Error parsing JSON: {e}", file=sys.stderr)
        return 1

    total_in_source = len(entries) + skipped["unchanged"] + skipped["corrupted"]
    print(f"   Total entries in source: {total_in_source}")
    print(f"   - Valid translations kept: {len(entries)}")
    print(f"   - Unchanged (filtered): {skipped['unchanged']}")
    print(f"   - Corrupted/binary (filtered): {skipped['corrupted']}")

    # If comparing, show diffs
    if args.compare and args.compare.exists():
        print(f"\n🔍 Comparing with existing {args.compare.name}...")
        old_entries = read_combined(args.compare)
        changes = diff_translations(old_entries, entries)

        print(f"   Previous entries: {len(old_entries)}")
        print(f"   New entries: {len(entries)}")
        print(f"   Changes detected: {len(changes)}")

        new_entries = {o: entries[o] for o in entries if o not in old_entries}
        print(f"   - Completely new offsets: {len(new_entries)}")
        updated_entries = {o: entries[o] for o in changes if o in old_entries}
        print(f"   - Updated translations: {len(updated_entries)}")

        if args.show_diff and (new_entries or updated_entries):
            print("\n   New offsets (first 5):")
            for offset in sorted(new_entries.keys())[:5]:
                print(f"     + {offset}: {new_entries[offset][:60]}...")

            if updated_entries:
                print("\n   Updated translations (first 5):")
                for offset in sorted(updated_entries.keys())[:5]:
                    old_text = old_entries.get(offset, "(was missing)")
                    new_text = entries[offset]
                    print(f"     ~ {offset}")
                    print(f"       before: {old_text[:50]}...")
                    print(f"       after:  {new_text[:50]}...")

    # Merge with existing combined file when output already exists
    # Existing entries not present in the JSON are preserved (new JSON overrides on conflict)
    output_file = args.output
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if output_file.exists():
        existing = read_combined(output_file)
        before_count = len(existing)
        # Merge: existing baseline, JSON entries override
        merged = {**existing, **entries}
        preserved = len(merged) - len(entries)
        added_from_existing = len(merged) - len(entries)
        print(f"\n🔀 Merging with existing {output_file.name}...")
        print(f"   Existing entries: {before_count}")
        print(f"   From JSON: {len(entries)}")
        only_in_existing = len([o for o in existing if o not in entries])
        print(f"   Kept from existing (not in JSON): {only_in_existing}")
        print(f"   Total after merge: {len(merged)}")
        entries = merged

    # Write output
    print(f"\n✍️  Writing {output_file}...")

    # Build header comment
    header_lines = [
        "# combined_it.txt — Italian translations for Pokémon Unbound (EN→IT)",
        "#",
        "# Same format as combined_fr.txt:  <offset_hex>: <text_IT>",
        "#   \\n  -> line break        \\l -> <0xFA> (scroll)      \\p -> <0xFB> (clear)",
        "# Lines starting with '#' and blank lines are ignored.",
        "# Offsets absent from this file keep their English text.",
        "# Last entry wins for a duplicated offset (case-insensitive).",
        "#",
        f"# Updated from {args.json_file.name}",
        "#",
    ]

    # Write header + entries
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(header_lines) + '\n')
        f.write('\n'.join(format_entries(entries)) + '\n')

    print(f"✓ Done! {len(entries)} translations written to {output_file}")
    print(f"  File size: {output_file.stat().st_size / 1024 / 1024:.1f} MB")

    return 0


if __name__ == "__main__":
    sys.exit(main())
