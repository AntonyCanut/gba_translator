#!/usr/bin/env python3
"""
09 - CSV to JSON Converter

Convertit le CSV traduit vers un JSON pour réinsertion dans la ROM.

Usage:
    python src/translators/09_csv_to_json.py [csv_file]

Input:
    - output/translation/*_translation_template.csv (ou fichier spécifié)

Output:
    - output/translation/YYYY-MM-DD_translation_ready.json
"""

import sys
import csv
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict


def find_latest_csv_file() -> Path:
    """
    Trouve le fichier CSV le plus récent.

    Returns:
        Path: Chemin vers le fichier
    """
    translation_dir = Path('output/translation')
    if not translation_dir.exists():
        raise FileNotFoundError("output/translation/ not found")

    # Chercher fichiers CSV
    csv_files = list(translation_dir.glob('*_translation_*.csv'))

    if not csv_files:
        raise FileNotFoundError("No CSV files found in output/translation/")

    # Retourner le plus récent
    return max(csv_files, key=lambda p: p.stat().st_mtime)


def validate_translation(row: dict) -> tuple[bool, str]:
    """
    Valide une ligne de traduction.

    Args:
        row: Ligne du CSV

    Returns:
        tuple: (is_valid, error_message)
    """
    translation = row.get('translation', '').strip()

    # Vérifier si traduction existe
    if not translation:
        return False, "Traduction manquante"

    # Vérifier longueur
    try:
        real_max = int(row['real_max_length'])
        trans_len = len(translation)

        if trans_len > real_max:
            return False, f"Trop long: {trans_len} > {real_max} (débordement: {trans_len - real_max})"

    except (ValueError, KeyError) as e:
        return False, f"Erreur de validation: {e}"

    return True, ""


def csv_to_json(csv_path: Path, json_path: Path) -> dict:
    """
    Convertit CSV vers JSON et valide les traductions.

    Args:
        csv_path: Chemin vers le CSV traduit
        json_path: Chemin de sortie du JSON

    Returns:
        dict: Statistiques de conversion et validation
    """
    translations = []
    errors = []
    warnings = []

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)

        for row_num, row in enumerate(reader, start=2):  # Start at 2 (header = 1)
            translation = row.get('translation', '').strip()

            # Ignorer lignes vides
            if not translation:
                warnings.append({
                    'row': row_num,
                    'offset': row.get('offset', 'unknown'),
                    'message': 'Traduction manquante'
                })
                continue

            # Valider
            is_valid, error_msg = validate_translation(row)

            if not is_valid:
                errors.append({
                    'row': row_num,
                    'offset': row.get('offset', 'unknown'),
                    'original': row.get('original_text', ''),
                    'translation': translation,
                    'error': error_msg
                })
                continue

            # Convertir offset (0x12345678 → 305441400)
            offset_str = row['offset'].replace('0x', '')
            offset = int(offset_str, 16)

            # Ajouter traduction
            translations.append({
                'offset': offset,
                'original_text': row['original_text'],
                'translation': translation,
                'length': len(translation),
                'original_length': int(row['original_length']),
                'padding_used': len(translation) - int(row['original_length']),
                'encoding': row['encoding'],
                'category': row.get('category', 'unknown'),
                'notes': row.get('notes', '')
            })

    # Sauvegarder JSON
    output = {
        'conversion_date': datetime.now().isoformat(),
        'source_csv': csv_path.name,
        'total_translations': len(translations),
        'total_errors': len(errors),
        'total_warnings': len(warnings),
        'translations': translations
    }

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Stats
    stats = {
        'total_rows': len(translations) + len(errors) + len(warnings),
        'successful': len(translations),
        'errors': errors,
        'warnings': warnings
    }

    return stats


def main():
    print("="*80)
    print("09 - CSV TO JSON CONVERTER")
    print("="*80)
    print()

    # 1. Trouver fichier CSV
    if len(sys.argv) > 1:
        csv_path = Path(sys.argv[1])
        if not csv_path.exists():
            print(f"❌ Erreur: Fichier non trouvé: {csv_path}")
            sys.exit(1)
    else:
        try:
            csv_path = find_latest_csv_file()
            print(f"📄 Fichier trouvé: {csv_path.name}")
        except FileNotFoundError as e:
            print(f"❌ Erreur: {e}")
            sys.exit(1)

    print()

    # 2. Créer chemin de sortie
    output_dir = Path('output/translation')
    output_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime('%Y-%m-%d')
    json_path = output_dir / f"{date_str}_translation_ready.json"

    # 3. Convertir et valider
    print("🔄 Conversion CSV → JSON...")
    print("🔍 Validation des traductions...")
    print()

    stats = csv_to_json(csv_path, json_path)

    # 4. Afficher résultats
    print("="*80)
    print("RÉSULTATS DE LA CONVERSION")
    print("="*80)
    print(f"Total lignes:           {stats['total_rows']}")
    print(f"Traductions réussies:   {stats['successful']}")
    print(f"Erreurs:                {len(stats['errors'])}")
    print(f"Avertissements:         {len(stats['warnings'])}")
    print()

    # 5. Afficher erreurs
    if stats['errors']:
        print("="*80)
        print("❌ ERREURS DÉTECTÉES")
        print("="*80)
        for error in stats['errors'][:10]:  # Limiter à 10
            print(f"\nLigne {error['row']} - Offset {error['offset']}")
            print(f"  Original:    {error['original']}")
            print(f"  Traduction:  {error['translation']}")
            print(f"  Erreur:      {error['error']}")

        if len(stats['errors']) > 10:
            print(f"\n... et {len(stats['errors']) - 10} autres erreurs")

        print()
        print("⚠️ Veuillez corriger ces erreurs avant de continuer.")
        sys.exit(1)

    # 6. Afficher avertissements
    if stats['warnings']:
        print("="*80)
        print("⚠️ AVERTISSEMENTS")
        print("="*80)
        for warning in stats['warnings'][:5]:
            print(f"Ligne {warning['row']} - {warning['offset']}: {warning['message']}")

        if len(stats['warnings']) > 5:
            print(f"... et {len(stats['warnings']) - 5} autres avertissements")
        print()

    # 7. Succès
    print("="*80)
    print("✅ CONVERSION RÉUSSIE")
    print("="*80)
    print()
    print(f"Fichier généré: {json_path}")
    print()
    print("Prochaine étape:")
    print("  python src/translators/10_reinsert_smart.py")
    print()


if __name__ == "__main__":
    main()
