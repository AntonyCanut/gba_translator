#!/usr/bin/env python3
"""
Validate text ranges between an output ROM and a reference ROM.

Uses an offset map to compare text ranges byte-for-byte and reports mismatches
with decoded text for diagnosis.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core.text_codec import TextDecoder


def _parse_offset(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return None
    return None


def _raw_bytes_length(raw_bytes: Any) -> Optional[int]:
    if raw_bytes is None:
        return None
    if isinstance(raw_bytes, (bytes, bytearray)):
        return len(raw_bytes)
    if isinstance(raw_bytes, list):
        return len(raw_bytes)
    if isinstance(raw_bytes, str):
        try:
            return len(bytes.fromhex(raw_bytes))
        except ValueError:
            return None
    return None


def _decode_bytes(data: bytes, encoding: str) -> str:
    try:
        return TextDecoder.decode(data, encoding, preserve_unknown=True)
    except ValueError:
        return TextDecoder.decode(data, 'pokemon', preserve_unknown=True)


def _load_reference_texts(path: Path) -> Dict[int, Dict]:
    with path.open('r', encoding='utf-8') as handle:
        data = json.load(handle)

    texts: Dict[int, Dict] = {}
    for item in data.get('texts', []):
        offset = _parse_offset(item.get('offset'))
        if offset is None:
            continue
        texts[offset] = item
    return texts


def _load_offset_map(path: Path) -> List[Dict]:
    with path.open('r', encoding='utf-8') as handle:
        data = json.load(handle)

    if isinstance(data, dict) and 'offset_map' in data:
        return data.get('offset_map', [])
    if isinstance(data, list):
        return data
    return []


def validate_text_ranges(
    output_rom: bytes,
    reference_rom: bytes,
    offset_map: List[Dict],
    reference_texts: Dict[int, Dict],
    sample_rate: float = 1.0,
    max_mismatches: int = 200,
    include_spanish_only: bool = False,
) -> Dict:
    stats = {
        'total_map_entries': len(offset_map),
        'total_candidates': 0,
        'total_compared': 0,
        'total_matched': 0,
        'total_mismatched': 0,
        'total_spanish_only_compared': 0,
        'skipped_only_in_spanish': 0,
        'skipped_only_in_english': 0,
        'missing_reference_text': 0,
        'invalid_length': 0,
        'out_of_bounds': 0,
        'bytes_compared': 0,
        'match_rate': 0.0,
    }
    mismatches: List[Dict] = []
    errors: List[Dict] = []

    if sample_rate <= 0 or sample_rate > 1:
        raise ValueError("sample_rate must be in (0, 1].")

    step = int(1.0 / sample_rate) if sample_rate < 1.0 else 1
    candidate_index = 0

    for entry in offset_map:
        english_offset = _parse_offset(entry.get('english_offset'))
        spanish_offset = _parse_offset(entry.get('spanish_offset'))
        status = entry.get('status') or 'unknown'

        if english_offset is None:
            if not include_spanish_only:
                stats['skipped_only_in_spanish'] += 1
                continue
            english_offset = spanish_offset
            status = 'spanish_only'
            spanish_only = True
        else:
            spanish_only = False
        if spanish_offset is None:
            stats['skipped_only_in_english'] += 1
            continue

        stats['total_candidates'] += 1
        candidate_index += 1

        if step > 1 and (candidate_index - 1) % step != 0:
            continue

        ref_entry = reference_texts.get(spanish_offset)
        if not ref_entry:
            stats['missing_reference_text'] += 1
            errors.append({
                'english_offset': f"0x{english_offset:08X}",
                'spanish_offset': f"0x{spanish_offset:08X}",
                'status': status,
                'error': 'missing_reference_text',
            })
            continue

        length = (
            ref_entry.get('byte_length')
            or ref_entry.get('length')
            or _raw_bytes_length(ref_entry.get('raw_bytes'))
        )
        try:
            length = int(length)
        except (TypeError, ValueError):
            length = None

        if not length or length <= 0:
            stats['invalid_length'] += 1
            errors.append({
                'english_offset': f"0x{english_offset:08X}",
                'spanish_offset': f"0x{spanish_offset:08X}",
                'status': status,
                'error': 'invalid_length',
            })
            continue

        if english_offset + length > len(output_rom) or spanish_offset + length > len(reference_rom):
            stats['out_of_bounds'] += 1
            errors.append({
                'english_offset': f"0x{english_offset:08X}",
                'spanish_offset': f"0x{spanish_offset:08X}",
                'status': status,
                'error': 'range_out_of_bounds',
            })
            continue

        expected = reference_rom[spanish_offset:spanish_offset + length]
        actual = output_rom[english_offset:english_offset + length]

        stats['total_compared'] += 1
        if spanish_only:
            stats['total_spanish_only_compared'] += 1
        stats['bytes_compared'] += length

        if expected == actual:
            stats['total_matched'] += 1
            continue

        stats['total_mismatched'] += 1

        if len(mismatches) < max_mismatches:
            encoding = ref_entry.get('encoding') or 'pokemon'
            expected_text = _decode_bytes(expected, encoding)
            actual_text = _decode_bytes(actual, encoding)
            ref_text = ref_entry.get('decoded_text') or ref_entry.get('text')

            first_diff = None
            for idx, (exp_byte, act_byte) in enumerate(zip(expected, actual)):
                if exp_byte != act_byte:
                    first_diff = idx
                    break

            mismatches.append({
                'english_offset': f"0x{english_offset:08X}",
                'spanish_offset': f"0x{spanish_offset:08X}",
                'status': status,
                'length': length,
                'encoding': encoding,
                'expected_bytes': expected.hex(),
                'actual_bytes': actual.hex(),
                'expected_text': expected_text,
                'actual_text': actual_text,
                'reference_text': ref_text,
                'first_diff_index': first_diff,
            })

    if stats['total_compared'] > 0:
        stats['match_rate'] = 100 * stats['total_matched'] / stats['total_compared']

    return {
        'statistics': stats,
        'mismatches': mismatches,
        'errors': errors,
        'max_mismatches': max_mismatches,
        'sample_rate': sample_rate,
    }


class TextRangeValidator:
    def __init__(
        self,
        output_rom: Path,
        reference_rom: Path,
        offset_map: Path,
        reference_texts: Path,
        report_path: Optional[Path] = None,
        sample_rate: float = 1.0,
        max_mismatches: int = 200,
        include_spanish_only: bool = False,
    ) -> None:
        self.output_rom = output_rom
        self.reference_rom = reference_rom
        self.offset_map = offset_map
        self.reference_texts = reference_texts
        self.sample_rate = sample_rate
        self.max_mismatches = max_mismatches
        self.include_spanish_only = include_spanish_only
        self.report_path = report_path or self._default_report_path()

    def _default_report_path(self) -> Path:
        report_dir = Path('output/reports')
        report_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime('%Y-%m-%d')
        return report_dir / f"{date_str}_text_range_validation.json"

    def run(self) -> bool:
        print("=" * 70)
        print("🔍 TEXT RANGE VALIDATION")
        print("=" * 70)

        try:
            output_rom_data = self.output_rom.read_bytes()
            reference_rom_data = self.reference_rom.read_bytes()
            reference_texts = _load_reference_texts(self.reference_texts)
            offset_map = _load_offset_map(self.offset_map)
        except Exception as exc:
            print(f"❌ Erreur chargement: {exc}")
            return False

        report = validate_text_ranges(
            output_rom=output_rom_data,
            reference_rom=reference_rom_data,
            offset_map=offset_map,
            reference_texts=reference_texts,
            sample_rate=self.sample_rate,
            max_mismatches=self.max_mismatches,
            include_spanish_only=self.include_spanish_only,
        )

        report_data = {
            'timestamp': datetime.now().isoformat(),
            'output_rom': str(self.output_rom),
            'reference_rom': str(self.reference_rom),
            'offset_map': str(self.offset_map),
            'reference_texts': str(self.reference_texts),
            'results': report,
        }

        try:
            with self.report_path.open('w', encoding='utf-8') as handle:
                json.dump(report_data, handle, indent=2, ensure_ascii=False)
            print(f"✅ Rapport sauvegardé: {self.report_path.name}")
        except Exception as exc:
            print(f"❌ Erreur rapport: {exc}")
            return False

        stats = report['statistics']
        print("\n📊 Résumé:")
        print(f"   - Comparés: {stats['total_compared']}")
        print(f"   - Correspondances: {stats['total_matched']}")
        print(f"   - Mismatches: {stats['total_mismatched']}")
        print(f"   - Taux de match: {stats['match_rate']:.2f}%")
        print(f"   - Skips ES-only: {stats['skipped_only_in_spanish']}")
        print(f"   - Skips EN-only: {stats['skipped_only_in_english']}")
        print(f"\n📁 Rapport: {self.report_path}")

        return True


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate text ranges using offset map')
    parser.add_argument('--output-rom', type=Path, required=True, help='Output ROM to validate')
    parser.add_argument('--reference-rom', type=Path, default=Path('input/roms/spanishrom.gba'),
                        help='Reference ROM (default: input/roms/spanishrom.gba)')
    parser.add_argument('--offset-map', type=Path, default=Path('output/differences/pointer_offset_map.json'),
                        help='Offset map JSON (default: output/differences/pointer_offset_map.json)')
    parser.add_argument('--reference-texts', type=Path, default=Path('output/extracted/extracted_texts/spanishrom_texts.json'),
                        help='Reference extraction JSON (default: output/extracted/extracted_texts/spanishrom_texts.json)')
    parser.add_argument('--report', type=Path, help='Output report path')
    parser.add_argument('--sample-rate', type=float, default=1.0, help='Sample rate (0-1]')
    parser.add_argument('--max-mismatches', type=int, default=200, help='Max mismatches to keep in report')
    parser.add_argument('--include-spanish-only', action='store_true',
                        help='Validate Spanish-only offsets using reference offsets')

    args = parser.parse_args()

    validator = TextRangeValidator(
        output_rom=args.output_rom,
        reference_rom=args.reference_rom,
        offset_map=args.offset_map,
        reference_texts=args.reference_texts,
        report_path=args.report,
        sample_rate=args.sample_rate,
        max_mismatches=args.max_mismatches,
        include_spanish_only=args.include_spanish_only,
    )

    return 0 if validator.run() else 1


if __name__ == '__main__':
    raise SystemExit(main())
