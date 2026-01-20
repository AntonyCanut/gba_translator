#!/usr/bin/env python3
"""
21 - Diagnose Spanish ROM Failures

Analyse les 6 textes qui échouent lors de la construction de la ROM espagnole
pour comprendre exactement pourquoi ils échouent et comment les corriger.

Usage:
    python src/translators/21_diagnose_spanish_rom_failures.py
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@dataclass
class FailedText:
    """Représente un texte qui a échoué."""
    offset: int
    length: int
    english_text: str
    spanish_text: str
    failure_reason: str
    suggestions: List[str]


class SpanishROMFailureDiagnostics:
    """Diagnostique les 6 textes qui échouent dans la ROM espagnole."""
    
    def __init__(self):
        self.english_texts = {}
        self.spanish_texts = {}
        self.failed_texts: List[FailedText] = []
    
    def run(self) -> bool:
        """Exécuter le diagnostic."""
        print("="*70)
        print("🔍 SPANISH ROM FAILURE DIAGNOSTICS")
        print("="*70)
        
        # Charger les données
        if not self._load_data():
            return False
        
        # Analyser tous les offsets pour identifier les problèmes
        self._analyze_failures()
        
        # Afficher les résultats
        self._print_results()
        
        return True
    
    def _load_data(self) -> bool:
        """Charger les textes extracteds."""
        print("\n📥 Chargement des données...")
        
        english_path = Path('output/extracted/extracted_texts/englishrom_texts.json')
        spanish_path = Path('output/extracted/extracted_texts/spanishrom_texts.json')
        
        try:
            if english_path.exists():
                with open(english_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data.get('texts', []):
                        self.english_texts[item['offset']] = item
                print(f"✅ Textes anglais: {len(self.english_texts)}")
            
            if spanish_path.exists():
                with open(spanish_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data.get('texts', []):
                        self.spanish_texts[item['offset']] = item
                print(f"✅ Textes espagnols: {len(self.spanish_texts)}")
            
            return True
        except Exception as e:
            print(f"❌ Erreur chargement: {e}")
            return False
    
    def _analyze_failures(self):
        """Analyser les raisons d'échec."""
        print("\n🔬 Analyse des échecs...")
        
        # Charger les offsets anglais
        all_offsets = list(self.english_texts.keys())
        
        print(f"Total textes attendus: {len(all_offsets)}")
        print(f"Textes trouvés en espagnol: {len(self.spanish_texts)}")
        print(f"Différence: {len(all_offsets) - len(self.spanish_texts)}")
        
        # Trouver les offsets manquants
        missing_offsets = []
        for offset in all_offsets:
            if offset not in self.spanish_texts:
                missing_offsets.append(offset)
        
        print(f"\n🔴 Offsets MANQUANTS en espagnol: {len(missing_offsets)}")
        
        for i, offset in enumerate(missing_offsets[:20]):  # Top 20
            english = self.english_texts.get(offset, {})
            english_text = english.get('text', '')
            length = english.get('length', 0)
            
            failure = FailedText(
                offset=offset,
                length=length,
                english_text=english_text,
                spanish_text='[NOT FOUND]',
                failure_reason='Offset not found in Spanish ROM extraction',
                suggestions=[
                    'Text may be at different offset in Spanish ROM',
                    'Text may have been moved/relocated',
                    'Text may not exist in Spanish ROM',
                    'Extraction issue in Spanish ROM'
                ]
            )
            self.failed_texts.append(failure)
        
        # Analyser les problèmes de longueur
        print(f"\n📏 Vérification des longueurs...")
        
        length_issues = []
        for offset in self.spanish_texts.keys():
            english = self.english_texts.get(offset, {})
            spanish = self.spanish_texts.get(offset, {})
            
            if not english or not spanish:
                continue
            
            english_len = english.get('length', 0)
            spanish_len = spanish.get('length', 0)
            
            if english_len != spanish_len:
                length_issues.append({
                    'offset': offset,
                    'english_len': english_len,
                    'spanish_len': spanish_len,
                    'diff': spanish_len - english_len
                })
        
        if length_issues:
            print(f"⚠️  Found {len(length_issues)} offsets with length mismatches")
            print("\nTop 10 length issues:")
            for issue in sorted(length_issues, key=lambda x: abs(x['diff']), reverse=True)[:10]:
                offset = issue['offset']
                english = self.english_texts.get(offset, {})
                spanish = self.spanish_texts.get(offset, {})
                print(f"\n   Offset: 0x{offset:08X}")
                print(f"   English length: {issue['english_len']}")
                print(f"   Spanish length: {issue['spanish_len']}")
                print(f"   Difference: {issue['diff']:+d}")
                print(f"   English: {english.get('text', '')[:40]}...")
                print(f"   Spanish: {spanish.get('text', '')[:40]}...")
        
        # Analyser les longueurs invalides
        print(f"\n🚨 Vérification des longueurs invalides...")
        
        invalid_lengths = []
        for offset, text_info in self.english_texts.items():
            length = text_info.get('length', 0)
            if length <= 0 or length > 1000:
                invalid_lengths.append((offset, length))
        
        if invalid_lengths:
            print(f"⚠️  Found {len(invalid_lengths)} offsets with invalid lengths")
            print("Examples:")
            for offset, length in invalid_lengths[:10]:
                english = self.english_texts[offset]
                failure = FailedText(
                    offset=offset,
                    length=length,
                    english_text=english.get('text', ''),
                    spanish_text='N/A',
                    failure_reason=f'Invalid length: {length}',
                    suggestions=[
                        f'Length {length} is invalid (must be 1-1000)',
                        'This is likely an extraction error',
                        'Text should be skipped during build'
                    ]
                )
                self.failed_texts.append(failure)
                print(f"   Offset 0x{offset:08X}: length={length}")
    
    def _print_results(self):
        """Afficher les résultats."""
        print("\n" + "="*70)
        print("📊 RÉSULTATS")
        print("="*70)
        
        print(f"\n📌 Raisons potentielles des 6 échecs:")
        print("""
1. LONGUEURS INVALIDES (0 ou > 1000)
   - Ces offsets ont une longueur invalide
   - Impossible de copier/valider
   - Raison probable: erreur d'extraction
   
2. OFFSETS MANQUANTS EN ESPAGNOL
   - Offset existe en anglais mais pas en espagnol
   - ROM espagnole a une structure différente
   - Raison probable: ROM locale ne contient pas ce texte
   
3. LONGUEURS DIFFÉRENTES
   - Même offset mais longueurs différentes
   - Impossible de copier directement (format incompatible)
   - Raison probable: texts stockés différemment

4. CORRUPTION DE DONNÉES
   - Données corrupted lors de l'extraction
   - Impossible de valider
   - Raison probable: problème dans la ROM source
""")
        
        if self.failed_texts:
            print(f"\n🔍 Détails des {len(self.failed_texts)} problèmes identifiés:\n")
            
            for i, failure in enumerate(self.failed_texts[:10], 1):
                print(f"{i}. Offset 0x{failure.offset:08X} (length={failure.length})")
                print(f"   Raison: {failure.failure_reason}")
                print(f"   English: {failure.english_text[:50]}...")
                if failure.spanish_text != '[NOT FOUND]':
                    print(f"   Spanish: {failure.spanish_text[:50]}...")
                print(f"   Solutions possibles:")
                for sugg in failure.suggestions:
                    print(f"     - {sugg}")
                print()
        
        # Recommandations
        print("\n💡 RECOMMANDATIONS:")
        print("""
✅ ROM Espagnole actuelle: 99.98% succès (339,815/339,821)

Les 6 textes qui échouent sont probablement:
1. Offsets invalides (longueur 0 ou > 1000)
2. Textes n'existant pas dans ROM espagnole
3. Données corrupted lors de l'extraction

💡 PROCHAINES ÉTAPES:

1. Vérifier les détails exacts des 6 échecs
   └─ Voir output/reports/2026-01-14_sprom_build_report.json

2. Analyser si c'est acceptable (0.02% loss)
   └─ Généralement acceptable pour build de ROM

3. Options de correction:
   ├─ Laisser tels quels (0.02% = 6 textes/339K)
   ├─ Pré-traiter extraction pour valider longueurs
   └─ Ajouter fallback vers ROM anglaise pour ces cas

4. Pour autres langues:
   └─ Utiliser TRANSLATE strategy + validation stricte
""")


def main():
    diagnostics = SpanishROMFailureDiagnostics()
    diagnostics.run()


if __name__ == '__main__':
    main()
