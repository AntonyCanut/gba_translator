#!/usr/bin/env python3
"""
Build ROM - Génération de ROMs traduites

Script générique pour construire une ROM traduite à partir:
- D'une ROM source (généralement anglaise)
- D'une ROM de référence (pour copier les textes), OU
- D'un fichier JSON de traductions

Usage:
    # Copier depuis ROM espagnole
    python src/commands/build_rom.py \\
        --source input/roms/englishrom.gba \\
        --reference input/roms/spanishrom.gba \\
        --output output/roms/spanish_rebuilt.gba

    # Utiliser traductions JSON
    python src/commands/build_rom.py \\
        --source input/roms/englishrom.gba \\
        --translations output/translation/french.json \\
        --output output/roms/french.gba
"""

import sys
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.rom_reader import ROMReader
from src.core.text_reinserter import TextEncoder


class ROMBuilder:
    """Constructeur générique de ROMs traduites."""

    def __init__(self, source_rom: Path, output_rom: Path):
        """
        Initialise le constructeur de ROM.

        Args:
            source_rom: ROM source (base anglaise)
            output_rom: ROM de sortie
        """
        self.source_rom = source_rom
        self.output_rom = output_rom
        self.rom_data = None
        self.stats = {
            'total_texts': 0,
            'copied_texts': 0,
            'skipped_texts': 0,
            'errors': []
        }

    def build_from_reference(self, reference_rom: Path) -> bool:
        """
        Construit la ROM en copiant depuis une ROM de référence.

        Stratégie: Copie directe byte-par-byte des textes depuis la ROM
        de référence vers la ROM de sortie aux mêmes offsets.

        Args:
            reference_rom: ROM de référence (ex: espagnole)

        Returns:
            bool: True si succès
        """
        print(f"\n📖 Chargement des ROMs...")

        # Charger ROM source
        source = ROMReader(str(self.source_rom))
        source.load()
        print(f"✅ ROM source: {self.source_rom.name} ({len(source.rom_data) / 1024 / 1024:.2f} MB)")

        # Charger ROM référence
        reference = ROMReader(str(reference_rom))
        reference.load()
        print(f"✅ ROM référence: {reference_rom.name} ({len(reference.rom_data) / 1024 / 1024:.2f} MB)")

        # Copier ROM source comme base
        self.rom_data = bytearray(source.rom_data)

        # Stratégie simple: copier tous les bytes texte-par-texte
        # Pour l'instant, on fait une copie complète des zones texte
        print(f"\n🔄 Copie des données texte...")

        # Zones texte connues dans Pokemon FireRed
        text_regions = [
            (0x00000000, 0x01000000),  # Toute la ROM pour simplifier
        ]

        for start, end in text_regions:
            size = min(end, len(reference.rom_data)) - start
            if size > 0:
                self.rom_data[start:start+size] = reference.rom_data[start:start+size]
                self.stats['copied_texts'] += 1

        print(f"✅ Copie complétée")

        # Sauvegarder
        return self._save_rom()

    def build_from_translations(self, translations_json: Path) -> bool:
        """
        Construit la ROM en utilisant un fichier de traductions JSON.

        Args:
            translations_json: Fichier JSON avec les traductions

        Returns:
            bool: True si succès
        """
        print(f"\n📖 Chargement de la ROM source...")

        # Charger ROM source
        source = ROMReader(str(self.source_rom))
        source.load()
        print(f"✅ ROM source: {self.source_rom.name}")

        # Copier comme base
        self.rom_data = bytearray(source.rom_data)

        # Charger traductions
        print(f"\n📝 Chargement des traductions...")
        with open(translations_json, 'r', encoding='utf-8') as f:
            data = json.load(f)

        translations = data.get('texts', [])
        print(f"✅ {len(translations)} traductions chargées")

        # Appliquer chaque traduction
        print(f"\n🔄 Application des traductions...")
        for i, trans in enumerate(translations):
            if i % 1000 == 0:
                print(f"   Traité: {i}/{len(translations)}")

            try:
                offset = trans['offset']
                if isinstance(offset, str):
                    offset = int(offset, 16)

                text = trans.get('translation', trans.get('text', ''))
                encoding = trans.get('encoding', 'pokemon')

                # Encoder le texte
                encoded = TextEncoder.encode(text, encoding)

                # Écrire dans la ROM
                self.rom_data[offset:offset+len(encoded)] = encoded
                self.stats['copied_texts'] += 1

            except Exception as e:
                self.stats['errors'].append({
                    'offset': trans.get('offset'),
                    'error': str(e)
                })
                self.stats['skipped_texts'] += 1

        print(f"✅ {self.stats['copied_texts']} traductions appliquées")
        if self.stats['skipped_texts'] > 0:
            print(f"⚠️  {self.stats['skipped_texts']} traductions ignorées (erreurs)")

        # Sauvegarder
        return self._save_rom()

    def _save_rom(self) -> bool:
        """
        Sauvegarde la ROM construite.

        Returns:
            bool: True si succès
        """
        print(f"\n💾 Sauvegarde de la ROM...")

        # Créer le répertoire de sortie
        self.output_rom.parent.mkdir(parents=True, exist_ok=True)

        # Écrire la ROM
        with open(self.output_rom, 'wb') as f:
            f.write(self.rom_data)

        size_mb = len(self.rom_data) / 1024 / 1024
        print(f"✅ ROM sauvegardée: {self.output_rom.name} ({size_mb:.2f} MB)")

        return True

    def print_stats(self):
        """Affiche les statistiques de construction."""
        print(f"\n📊 STATISTIQUES")
        print(f"{'='*80}")
        print(f"Textes copiés:  {self.stats['copied_texts']}")
        print(f"Textes ignorés: {self.stats['skipped_texts']}")
        print(f"Erreurs:        {len(self.stats['errors'])}")

        if self.stats['errors']:
            print(f"\n⚠️  Erreurs rencontrées:")
            for err in self.stats['errors'][:10]:  # Montrer max 10 erreurs
                print(f"   - Offset {err['offset']}: {err['error']}")


def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description='Construit une ROM traduite',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--source',
        type=Path,
        required=True,
        help='ROM source (généralement anglaise)'
    )

    parser.add_argument(
        '--reference',
        type=Path,
        help='ROM de référence (pour copier les textes)'
    )

    parser.add_argument(
        '--translations',
        type=Path,
        help='Fichier JSON de traductions'
    )

    parser.add_argument(
        '--output',
        type=Path,
        required=True,
        help='ROM de sortie'
    )

    args = parser.parse_args()

    # Validation
    if not args.reference and not args.translations:
        parser.error("Au moins --reference ou --translations est requis")

    if args.reference and args.translations:
        parser.error("Utiliser --reference OU --translations, pas les deux")

    if not args.source.exists():
        print(f"❌ ROM source introuvable: {args.source}")
        return 1

    # Construction
    print(f"\n{'='*80}")
    print(f"🚀 ROM BUILDER")
    print(f"{'='*80}")

    builder = ROMBuilder(args.source, args.output)

    try:
        if args.reference:
            if not args.reference.exists():
                print(f"❌ ROM de référence introuvable: {args.reference}")
                return 1
            success = builder.build_from_reference(args.reference)
        else:
            if not args.translations.exists():
                print(f"❌ Fichier de traductions introuvable: {args.translations}")
                return 1
            success = builder.build_from_translations(args.translations)

        builder.print_stats()

        if success:
            print(f"\n✅ ROM construite avec succès: {args.output}")
            return 0
        else:
            print(f"\n❌ Échec de la construction")
            return 1

    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
