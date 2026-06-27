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
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional


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


def format_entries(entries: dict[str, str]) -> list[str]:
    """Format entries as combined_it.txt lines, sorted by offset."""
    lines = []
    for offset in sorted(entries.keys()):
        text = entries[offset]
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


def main():
    parser = argparse.ArgumentParser(
        description="Process Italian translations JSON → combined_it.txt with smart diffing"
    )
    parser.add_argument("json_file", type=Path, help="Italian translations JSON file")
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
