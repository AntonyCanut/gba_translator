#!/usr/bin/env python3
"""
25 - Advanced Offset Analysis

Analyse détaillée:
- Distribution des longueurs
- Patterns de stockage
- Vérification des frontières
- Analyse des bytes consécutifs

Usage:
    python src/translators/25_advanced_offset_analysis.py
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple
from collections import Counter, defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class AdvancedOffsetAnalysis:
    """Analyse avancée des offsets."""
    
    def __init__(self):
        self.english_texts = {}
        self.english_rom_data = None
        self.spanish_rom_data = None
        self.output_rom_data = None
        self.analysis = {
            'length_distribution': {},
            'consecutive_texts': 0,
            'gap_analysis': {},
            'boundary_integrity': True,
            'error_patterns': []
        }
    
    def run(self) -> bool:
        """Exécuter analyse complète."""
        print("="*70)
        print("🔬 ADVANCED OFFSET ANALYSIS")
        print("="*70)
        
        if not self._load_data():
            return False
        
        self._analyze_length_distribution()
        self._analyze_consecutive_texts()
        self._analyze_gaps()
        self._analyze_boundaries()
        self._generate_detailed_report()
        
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
    
    def _analyze_length_distribution(self):
        """Analyser distribution des longueurs."""
        print("\n📊 Analyzing length distribution...")
        
        offsets = sorted(self.english_texts.keys())
        lengths = []
        
        for offset in offsets:
            item = self.english_texts[offset]
            length = item.get('length', 0)
            
            if 0 < length <= 1000:
                lengths.append(length)
        
        self.analysis['length_distribution'] = {
            'total': len(lengths),
            'min': min(lengths),
            'max': max(lengths),
            'avg': sum(lengths) / len(lengths) if lengths else 0,
            'median': sorted(lengths)[len(lengths)//2] if lengths else 0,
            'total_bytes': sum(lengths)
        }
        
        # Distribution par ranges
        ranges = {
            '1-10': 0,
            '11-50': 0,
            '51-100': 0,
            '101-200': 0,
            '201-500': 0,
            '501-1000': 0
        }
        
        for length in lengths:
            if length <= 10:
                ranges['1-10'] += 1
            elif length <= 50:
                ranges['11-50'] += 1
            elif length <= 100:
                ranges['51-100'] += 1
            elif length <= 200:
                ranges['101-200'] += 1
            elif length <= 500:
                ranges['201-500'] += 1
            else:
                ranges['501-1000'] += 1
        
        self.analysis['length_distribution']['by_range'] = ranges
        
        print(f"   Total texts: {len(lengths):,}")
        print(f"   Bytes: {sum(lengths):,}")
        print(f"   Length: min={min(lengths)}, max={max(lengths)}, avg={sum(lengths)/len(lengths):.0f}")
        print(f"\n   Distribution by range:")
        for range_name, count in ranges.items():
            pct = 100 * count / len(lengths)
            print(f"      {range_name:12} bytes: {count:8,} texts ({pct:5.2f}%)")
    
    def _analyze_consecutive_texts(self):
        """Analyser les textes consécutifs."""
        print("\n🔗 Analyzing consecutive texts...")
        
        offsets = sorted(self.english_texts.keys())
        consecutive_count = 0
        consecutive_groups = []
        current_group = []
        
        for i, offset in enumerate(offsets[:-1]):
            item = self.english_texts[offset]
            length = item.get('length', 0)
            
            if length <= 0 or length > 1000:
                continue
            
            next_offset = offsets[i+1]
            
            # Si le prochain offset suit directement
            if offset + length == next_offset:
                consecutive_count += 1
                current_group.append((offset, length))
            else:
                if current_group:
                    consecutive_groups.append(current_group)
                    current_group = []
        
        self.analysis['consecutive_texts'] = {
            'count': consecutive_count,
            'groups': len(consecutive_groups),
            'largest_group': max(len(g) for g in consecutive_groups) if consecutive_groups else 0
        }
        
        print(f"   Consecutive text pairs: {consecutive_count:,}")
        print(f"   Consecutive groups: {len(consecutive_groups):,}")
        if consecutive_groups:
            print(f"   Largest group: {max(len(g) for g in consecutive_groups)} texts")
    
    def _analyze_gaps(self):
        """Analyser les gaps entre offsets."""
        print("\n🔲 Analyzing gaps between offsets...")
        
        offsets = sorted(self.english_texts.keys())
        gaps = []
        gap_sizes = defaultdict(int)
        
        for i in range(len(offsets) - 1):
            offset = offsets[i]
            next_offset = offsets[i + 1]
            
            item = self.english_texts[offset]
            length = item.get('length', 0)
            
            if length > 0 and length <= 1000:
                gap = next_offset - (offset + length)
                if gap > 0:
                    gaps.append(gap)
                    
                    if gap < 100:
                        gap_sizes['<100'] += 1
                    elif gap < 1000:
                        gap_sizes['100-1000'] += 1
                    elif gap < 10000:
                        gap_sizes['1K-10K'] += 1
                    else:
                        gap_sizes['>10K'] += 1
        
        self.analysis['gap_analysis'] = {
            'total_gaps': len(gaps),
            'avg_gap': sum(gaps) / len(gaps) if gaps else 0,
            'max_gap': max(gaps) if gaps else 0,
            'zero_gap': sum(1 for g in gaps if g == 0),
            'distribution': dict(gap_sizes)
        }
        
        print(f"   Total gaps: {len(gaps):,}")
        if gaps:
            print(f"   Average gap: {sum(gaps)/len(gaps):.0f} bytes")
            print(f"   Max gap: {max(gaps):,} bytes")
            print(f"   Zero gaps: {sum(1 for g in gaps if g == 0):,}")
            print(f"\n   Gap distribution:")
            for size, count in sorted(gap_sizes.items()):
                pct = 100 * count / len(gaps)
                print(f"      {size:12}: {count:8,} gaps ({pct:5.2f}%)")
    
    def _analyze_boundaries(self):
        """Analyser l'intégrité des limites."""
        print("\n🔒 Analyzing boundary integrity...")
        
        offsets = sorted(self.english_texts.keys())
        boundary_errors = []
        
        for offset in offsets:
            item = self.english_texts[offset]
            length = item.get('length', 0)
            
            if length <= 0 or length > 1000:
                continue
            
            # Vérifier que l'offset + length ne dépasse pas ROM
            if offset + length > len(self.spanish_rom_data):
                boundary_errors.append({
                    'offset': offset,
                    'length': length,
                    'end': offset + length,
                    'rom_size': len(self.spanish_rom_data)
                })
            
            # Vérifier que Spanish et Output ont le même contenu
            try:
                spanish_bytes = self.spanish_rom_data[offset:offset + length]
                output_bytes = self.output_rom_data[offset:offset + length]
                
                if spanish_bytes != output_bytes:
                    boundary_errors.append({
                        'offset': offset,
                        'type': 'content_mismatch'
                    })
            except:
                pass
        
        self.analysis['boundary_integrity'] = len(boundary_errors) == 0
        self.analysis['boundary_errors'] = len(boundary_errors)
        
        if boundary_errors:
            print(f"   ❌ Boundary errors found: {len(boundary_errors)}")
            for err in boundary_errors[:5]:
                print(f"      {err}")
        else:
            print(f"   ✅ All boundaries are intact!")
    
    def _generate_detailed_report(self):
        """Générer rapport détaillé."""
        print("\n" + "="*70)
        print("📋 DETAILED ANALYSIS REPORT")
        print("="*70)
        
        print(f"\n📏 LENGTH ANALYSIS:")
        dist = self.analysis['length_distribution']
        print(f"   Total texts: {dist['total']:,}")
        print(f"   Total bytes: {dist['total_bytes']:,}")
        print(f"   Range: {dist['min']} - {dist['max']} bytes")
        print(f"   Average: {dist['avg']:.1f} bytes")
        print(f"   Median: {dist['median']} bytes")
        
        print(f"\n🔗 CONSECUTIVE TEXTS:")
        cons = self.analysis['consecutive_texts']
        print(f"   Consecutive pairs: {cons['count']:,}")
        print(f"   Groups: {cons['groups']:,}")
        print(f"   Largest: {cons['largest_group']} texts in sequence")
        
        print(f"\n🔲 GAP ANALYSIS:")
        gap = self.analysis['gap_analysis']
        print(f"   Total gaps: {gap['total_gaps']:,}")
        print(f"   Average: {gap['avg_gap']:.0f} bytes")
        print(f"   Max: {gap['max_gap']:,} bytes")
        print(f"   Zero-gap (consecutive): {gap['zero_gap']:,}")
        
        print(f"\n🔒 BOUNDARY INTEGRITY:")
        if self.analysis['boundary_integrity']:
            print(f"   ✅ All boundaries intact")
        else:
            print(f"   ⚠️  {self.analysis['boundary_errors']} boundary errors")
        
        # Sauvegarder rapport
        self._save_report()
    
    def _save_report(self):
        """Sauvegarder le rapport JSON."""
        print(f"\n💾 Saving detailed analysis...")
        
        try:
            output_path = Path('output/reports/2026-01-14_advanced_offset_analysis.json')
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(self.analysis, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Report saved: {output_path}")
        except Exception as e:
            print(f"❌ Error: {e}")


def main():
    analysis = AdvancedOffsetAnalysis()
    success = analysis.run()
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
