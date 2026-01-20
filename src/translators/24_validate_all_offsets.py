#!/usr/bin/env python3
"""
24 - Complete Offset Validation

Teste TOUS les offsets dans la ROM espagnole pour valider
que chaque byte a été copié correctement.

Usage:
    python src/translators/24_validate_all_offsets.py
    
    Or with sampling (faster):
    python src/translators/24_validate_all_offsets.py --sample 0.1
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass
import argparse

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@dataclass
class OffsetValidationResult:
    """Résultat de validation pour un offset."""
    offset: int
    length: int
    match: bool
    english_bytes: bytes
    spanish_bytes: bytes
    output_bytes: bytes
    error: str = ""


class CompleteOffsetValidator:
    """Valide tous les offsets de la ROM espagnole."""
    
    def __init__(self, sample_rate: float = 1.0):
        self.english_texts = {}
        self.english_rom_data = None
        self.spanish_rom_data = None
        self.output_rom_data = None
        self.sample_rate = sample_rate
        self.results: List[OffsetValidationResult] = []
        self.statistics = {
            'total_tested': 0,
            'total_match': 0,
            'total_mismatch': 0,
            'total_skipped': 0,
            'match_rate': 0.0,
            'bytes_compared': 0,
            'errors': []
        }
    
    def run(self) -> bool:
        """Exécuter validation complète."""
        print("="*70)
        print("🔬 COMPLETE OFFSET VALIDATION")
        print("="*70)
        
        if not self._load_data():
            return False
        
        print(f"\n📊 Validation Mode: {'SAMPLING ' + str(int(self.sample_rate*100)) + '%' if self.sample_rate < 1.0 else 'COMPLETE'}")
        print(f"   Testing {int(len(self.english_texts) * self.sample_rate):,} of {len(self.english_texts):,} offsets")
        
        self._validate_all_offsets()
        self._print_results()
        self._save_report()
        
        return True
    
    def _load_data(self) -> bool:
        """Charger les données."""
        print("\n📥 Loading data...")
        
        try:
            # Charger les textes anglais
            english_path = Path('output/extracted/extracted_texts/englishrom_texts.json')
            with open(english_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data.get('texts', []):
                    offset = item['offset']
                    self.english_texts[offset] = item
            
            print(f"✅ English texts: {len(self.english_texts):,}")
            
            # Charger les ROMs
            with open(Path('input/roms/englishrom.gba'), 'rb') as f:
                self.english_rom_data = f.read()
            print(f"✅ English ROM: {len(self.english_rom_data):,} bytes")
            
            with open(Path('input/roms/spanishrom.gba'), 'rb') as f:
                self.spanish_rom_data = f.read()
            print(f"✅ Spanish ROM: {len(self.spanish_rom_data):,} bytes")
            
            with open(Path('output/roms/2026-01-14_sprom_final.gba'), 'rb') as f:
                self.output_rom_data = f.read()
            print(f"✅ Output ROM: {len(self.output_rom_data):,} bytes")
            
            return True
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def _validate_all_offsets(self):
        """Valider tous les offsets."""
        print("\n🔍 Validating offsets...")
        
        offsets = sorted(self.english_texts.keys())
        total_offsets = len(offsets)
        
        # Déterminer quels offsets tester
        if self.sample_rate < 1.0:
            # Sampling
            step = int(1.0 / self.sample_rate)
            test_offsets = offsets[::step]
        else:
            # Tous
            test_offsets = offsets
        
        print(f"   Total to test: {len(test_offsets):,}")
        
        for i, offset in enumerate(test_offsets):
            try:
                item = self.english_texts[offset]
                length = item.get('length', 0)
                
                # Skip invalid lengths
                if length <= 0 or length > 1000:
                    self.statistics['total_skipped'] += 1
                    continue
                
                # Obtenir les bytes
                if offset + length > len(self.spanish_rom_data):
                    self.statistics['total_skipped'] += 1
                    continue
                
                spanish_bytes = self.spanish_rom_data[offset:offset + length]
                output_bytes = self.output_rom_data[offset:offset + length]
                english_bytes = self.english_rom_data[offset:offset + length]
                
                # Comparer
                match = spanish_bytes == output_bytes
                
                result = OffsetValidationResult(
                    offset=offset,
                    length=length,
                    match=match,
                    english_bytes=english_bytes,
                    spanish_bytes=spanish_bytes,
                    output_bytes=output_bytes
                )
                
                if match:
                    self.statistics['total_match'] += 1
                else:
                    self.statistics['total_mismatch'] += 1
                    self.results.append(result)
                
                self.statistics['bytes_compared'] += length
                self.statistics['total_tested'] += 1
            
            except Exception as e:
                self.statistics['errors'].append({
                    'offset': offset,
                    'error': str(e)
                })
                self.statistics['total_skipped'] += 1
            
            # Afficher progression
            if (i + 1) % 10000 == 0:
                match_rate = 100 * self.statistics['total_match'] / max(1, self.statistics['total_tested'])
                print(f"   Progress: {i+1}/{len(test_offsets)} ({match_rate:.2f}% match)")
        
        # Calculer le taux de match
        if self.statistics['total_tested'] > 0:
            self.statistics['match_rate'] = 100 * self.statistics['total_match'] / self.statistics['total_tested']
    
    def _print_results(self):
        """Afficher les résultats."""
        print("\n" + "="*70)
        print("📊 VALIDATION RESULTS")
        print("="*70)
        
        print(f"\n✅ STATISTICS:")
        print(f"   Tested: {self.statistics['total_tested']:,}")
        print(f"   Matched: {self.statistics['total_match']:,} ✅")
        print(f"   Mismatched: {self.statistics['total_mismatch']:,} ❌")
        print(f"   Skipped (invalid): {self.statistics['total_skipped']:,}")
        print(f"   Match rate: {self.statistics['match_rate']:.2f}%")
        print(f"   Bytes compared: {self.statistics['bytes_compared']:,}")
        
        if self.statistics['total_mismatch'] == 0:
            print(f"\n🎉 PERFECT! All {self.statistics['total_tested']:,} tested offsets match perfectly!")
        else:
            print(f"\n⚠️  {self.statistics['total_mismatch']} mismatches found:")
            print(f"\n   Top 10 mismatches:")
            for i, result in enumerate(sorted(self.results, key=lambda x: x.offset)[:10], 1):
                print(f"\n   {i}. Offset 0x{result.offset:08X} (length={result.length})")
                print(f"      Spanish: {result.spanish_bytes[:20].hex()}...")
                print(f"      Output:  {result.output_bytes[:20].hex()}...")
                
                # Trouver le premier byte différent
                for j, (s, o) in enumerate(zip(result.spanish_bytes, result.output_bytes)):
                    if s != o:
                        print(f"      First diff at byte {j}: Spanish={s:02X} vs Output={o:02X}")
                        break
        
        if self.statistics['errors']:
            print(f"\n⚠️  Errors: {len(self.statistics['errors'])}")
            for err in self.statistics['errors'][:5]:
                print(f"   Offset 0x{err['offset']:08X}: {err['error']}")
    
    def _save_report(self):
        """Sauvegarder le rapport."""
        print(f"\n💾 Saving report...")
        
        report = {
            'validation_type': 'COMPLETE' if self.sample_rate == 1.0 else f'SAMPLING_{int(self.sample_rate*100)}%',
            'statistics': self.statistics,
            'sample_rate': self.sample_rate,
            'mismatches': [
                {
                    'offset': r.offset,
                    'length': r.length,
                    'spanish_bytes': r.spanish_bytes.hex(),
                    'output_bytes': r.output_bytes.hex()
                }
                for r in sorted(self.results, key=lambda x: x.offset)[:100]
            ]
        }
        
        try:
            output_path = Path('output/reports/2026-01-14_offset_validation_complete.json')
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"✅ Report saved: {output_path}")
        except Exception as e:
            print(f"❌ Error saving report: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Validate all offsets in Spanish ROM',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test all offsets (complete validation)
  python 24_validate_all_offsets.py

  # Test 10% of offsets (faster)
  python 24_validate_all_offsets.py --sample 0.1

  # Test 50% of offsets
  python 24_validate_all_offsets.py --sample 0.5
        """
    )
    
    parser.add_argument('--sample', type=float, default=1.0,
                       help='Sample rate (0.0-1.0, default=1.0 for complete)')
    
    args = parser.parse_args()
    
    if not 0.0 < args.sample <= 1.0:
        print("Error: sample rate must be between 0 and 1.0")
        return 1
    
    validator = CompleteOffsetValidator(args.sample)
    success = validator.run()
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
