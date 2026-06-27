#!/usr/bin/env python3
"""
06 - Detect Padding

Analyse available padding for all texts to translate.
Generates an enriched JSON with padding information.

Usage:
    python src/translators/06_detect_padding.py

Input:
    - input/roms/englishrom.gba
    - output/differences/*_diff_only.json

Output:
    - output/analysis/YYYY-MM-DD_padding_analysis.json
    - output/differences/YYYY-MM-DD_diff_with_padding.json
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.rom_reader import ROMReader, ROMError
from src.core.padding_detector import PaddingDetector


def find_latest_diff_file() -> Path:
    """
    Find the most recent diff_only.json file.

    Returns:
        Path: Path to the diff_only file
    """
    diff_dir = Path('output/differences')
    if not diff_dir.exists():
        raise FileNotFoundError("output/differences/ not found")

    # Find diff_only files
    diff_files = list(diff_dir.glob('*_diff_only.json'))

    if not diff_files:
        raise FileNotFoundError("No *_diff_only.json found in output/differences/")

    # Return the most recent
    return max(diff_files, key=lambda p: p.stat().st_mtime)


def main():
    print("="*80)
    print("06 - DETECT PADDING")
    print("="*80)
    print()

    # 1. Load ROM
    rom_path = Path('input/roms/englishrom.gba')
    print(f"📖 Loading ROM: {rom_path}")

    try:
        rom = ROMReader(str(rom_path))
        rom.load()
        info = rom.get_rom_info()
        print(f"   ROM: {info['title']} ({info['game_code']})")
        print(f"   Size: {info['size_mb']} MB")
    except (FileNotFoundError, ROMError) as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    print()

    # 2. Load differences
    try:
        diff_file = find_latest_diff_file()
        print(f"📄 Loading differences: {diff_file.name}")

        with open(diff_file, 'r', encoding='utf-8') as f:
            diff_data = json.load(f)

        texts = diff_data['texts']
        print(f"   Texts to analyse: {len(texts)}")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    print()

    # 3. Analyse padding
    print("🔍 Analysing available padding (extended search)...")
    detector = PaddingDetector(rom)

    # Use extended_search=True to find more padding
    enriched_texts = detector.analyze_all_texts(texts, extended_search=True)

    print(f"✅ {len(enriched_texts)} texts analysed")
    print()

    # 4. Display statistics
    print("="*80)
    print("PADDING STATISTICS")
    print("="*80)

    report = detector.generate_report()
    stats = report['statistics']

    print(f"Total analysé:     {stats['total_analyzed']}")
    print(f"Avec padding:      {stats['with_padding']}")
    print(f"Sans padding:      {stats['without_padding']}")
    print(f"Padding moyen:     {stats['average_padding']}")
    print(f"Padding max:       {stats['max_padding']}")
    print(f"Padding min:       {stats['min_padding']}")
    print()

    print("Distribution par range:")
    print("-"*80)
    for label, data in report['distribution_by_range'].items():
        print(f"  {label:20s}: {data['count']:5d} ({data['percentage']})")
    print()

    print("Recommandations:")
    print("-"*80)
    for rec in report['recommendations']:
        print(f"  {rec}")
    print()

    # 5. Save results
    date_str = datetime.now().strftime('%Y-%m-%d')

    # Analysis report
    analysis_dir = Path('output/analysis')
    analysis_dir.mkdir(parents=True, exist_ok=True)

    analysis_path = analysis_dir / f"{date_str}_padding_analysis.json"
    print(f"💾 Saving analysis: {analysis_path}")

    with open(analysis_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Enriched texts
    diff_with_padding = {
        'rom_name': diff_data['rom_name'],
        'rom_size': diff_data['rom_size'],
        'text_count': len(enriched_texts),
        'analysis_date': date_str,
        'texts': enriched_texts
    }

    enriched_path = Path('output/differences') / f"{date_str}_diff_with_padding.json"
    print(f"💾 Saving enriched texts: {enriched_path}")

    with open(enriched_path, 'w', encoding='utf-8') as f:
        json.dump(diff_with_padding, f, indent=2, ensure_ascii=False)

    print()
    print("="*80)
    print("✅ ANALYSIS COMPLETE")
    print("="*80)
    print()
    print(f"Generated files:")
    print(f"  - {analysis_path}")
    print(f"  - {enriched_path}")
    print()
    print("Next step:")
    print("  python src/translators/08_json_to_csv.py")
    print()


if __name__ == "__main__":
    main()
