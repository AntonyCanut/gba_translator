#!/usr/bin/env python3
"""
08 - JSON to CSV Converter

Convertit le fichier JSON enrichi avec padding vers un CSV pour traduction.

Usage:
    python src/translators/08_json_to_csv.py

Input:
    - output/differences/*_diff_with_padding.json

Output:
    - output/translation/YYYY-MM-DD_translation_template.csv
"""

import sys
import csv
import json
from pathlib import Path
from datetime import datetime

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def find_latest_padding_file() -> Path:
    """
    Trouve le fichier diff_with_padding.json le plus récent.

    Returns:
        Path: Chemin vers le fichier
    """
    diff_dir = Path('output/differences')
    if not diff_dir.exists():
        raise FileNotFoundError("output/differences/ not found")

    # Chercher fichiers diff_with_padding
    padding_files = list(diff_dir.glob('*_diff_with_padding.json'))

    if not padding_files:
        raise FileNotFoundError("No *_diff_with_padding.json found in output/differences/")

    # Retourner le plus récent
    return max(padding_files, key=lambda p: p.stat().st_mtime)


def categorize_text(text: str, offset: int) -> str:
    """
    Catégorise un texte basé sur son contenu.

    Args:
        text: Le texte à catégoriser
        offset: L'offset du texte

    Returns:
        str: Catégorie du texte
    """
    text_lower = text.lower()

    # Dialogues
    if any(marker in text_lower for marker in ['!', '?', '...', 'you', 'your', 'my', 'i ']):
        return "dialogue"

    # Noms de lieux
    if text[0].isupper() and ' ' in text and len(text.split()) <= 3:
        return "location"

    # Messages système
    if any(word in text_lower for word in ['saved', 'loaded', 'menu', 'cancel', 'select']):
        return "system"

    # Descriptions
    if len(text) > 30:
        return "description"

    # Autre
    return "other"


def json_to_csv(json_path: Path, csv_path: Path) -> dict:
    """
    Convertit JSON vers CSV pour traduction.

    Args:
        json_path: Chemin vers le JSON enrichi
        csv_path: Chemin de sortie du CSV

    Returns:
        dict: Statistiques de conversion
    """
    # Charger JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    texts = data['texts']

    # Créer CSV
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'offset',
            'original_text',
            'original_length',
            'padding_available',
            'real_max_length',
            'encoding',
            'category',
            'translation',
            'notes'
        ])

        writer.writeheader()

        for text_entry in texts:
            offset = text_entry['offset']
            original_text = text_entry['text']
            original_length = text_entry['length']
            padding = text_entry['padding_available']
            real_max = text_entry['real_max_length']
            encoding = text_entry['encoding']

            category = categorize_text(original_text, offset)

            writer.writerow({
                'offset': f"0x{offset:08X}",
                'original_text': original_text,
                'original_length': original_length,
                'padding_available': padding,
                'real_max_length': real_max,
                'encoding': encoding,
                'category': category,
                'translation': '',  # À remplir
                'notes': ''  # Pour commentaires traducteurs
            })

    # Statistiques
    stats = {
        'total_texts': len(texts),
        'categories': {}
    }

    for text_entry in texts:
        cat = categorize_text(text_entry['text'], text_entry['offset'])
        stats['categories'][cat] = stats['categories'].get(cat, 0) + 1

    return stats


def main():
    print("="*80)
    print("08 - JSON TO CSV CONVERTER")
    print("="*80)
    print()

    # 1. Trouver fichier JSON
    try:
        json_path = find_latest_padding_file()
        print(f"📄 Fichier trouvé: {json_path.name}")
    except FileNotFoundError as e:
        print(f"❌ Erreur: {e}")
        sys.exit(1)

    print()

    # 2. Créer dossier de sortie
    output_dir = Path('output/translation')
    output_dir.mkdir(parents=True, exist_ok=True)

    # 3. Générer CSV
    date_str = datetime.now().strftime('%Y-%m-%d')
    csv_path = output_dir / f"{date_str}_translation_template.csv"

    print("🔄 Conversion JSON → CSV...")
    stats = json_to_csv(json_path, csv_path)

    print(f"✅ {stats['total_texts']} textes exportés")
    print()

    # 4. Afficher statistiques
    print("="*80)
    print("STATISTIQUES PAR CATÉGORIE")
    print("="*80)

    for category, count in sorted(stats['categories'].items(), key=lambda x: -x[1]):
        pct = 100 * count / stats['total_texts']
        print(f"  {category:15s}: {count:5d} ({pct:5.1f}%)")

    print()

    # 5. Instructions
    print("="*80)
    print("✅ CONVERSION TERMINÉE")
    print("="*80)
    print()
    print(f"Fichier généré: {csv_path}")
    print()
    print("Instructions pour les traducteurs:")
    print("-" * 80)
    print("1. Ouvrir le CSV dans Excel, Google Sheets ou LibreOffice")
    print("2. Remplir la colonne 'translation' avec vos traductions")
    print("3. Respecter la colonne 'real_max_length' (longueur max avec padding)")
    print("4. Utiliser la colonne 'notes' pour commentaires si nécessaire")
    print("5. Sauvegarder et exécuter: python src/translators/09_csv_to_json.py")
    print()
    print("Colonnes importantes:")
    print("  - original_text: Texte anglais à traduire")
    print("  - original_length: Longueur du texte anglais")
    print("  - padding_available: Bytes de padding disponibles")
    print("  - real_max_length: Longueur MAXIMALE autorisée (original + padding)")
    print("  - translation: VOTRE TRADUCTION (à remplir)")
    print()


if __name__ == "__main__":
    main()
