# Tâches Techniques Détaillées - Développement ROM Traduction

## 🔧 Vue d'ensemble technique

Ce document détaille toutes les tâches de développement nécessaires pour améliorer le système de traduction et permettre la relocalisation complète des textes.

---

## Sprint 1 : Outils de productivité traducteurs (Priorité HAUTE)

### Task 1.1 : Créer convertisseur JSON ↔ CSV
**Temps estimé** : 4-6 heures
**Difficulté** : Facile
**Prérequis** : Python 3.6+

**Objectif** : Permettre aux traducteurs d'utiliser Excel/Google Sheets au lieu d'éditer JSON manuellement

**Fichiers à créer** :
- `tools/json_to_csv.py`
- `tools/csv_to_json.py`

#### Spécifications `json_to_csv.py`

```python
#!/usr/bin/env python3
"""
Convertit extracted_texts JSON en CSV pour traduction facile.

Usage:
    python json_to_csv.py input.json output.csv

CSV Format:
    Offset,English,French,Length,Encoding,Category,Notes
"""

import csv
import json
from pathlib import Path

def detect_category(text, offset):
    """
    Détecter automatiquement la catégorie du texte.

    Catégories:
    - dialogue: Dialogues PNJ
    - item: Descriptions objets
    - move: Noms/descriptions attaques
    - pokemon: Descriptions Pokémon
    - location: Noms de lieux
    - menu: Textes menus
    - system: Messages système
    - other: Autres
    """
    # À implémenter selon patterns
    pass

def json_to_csv(input_json, output_csv, add_categories=True):
    """Convertir JSON → CSV"""
    with open(input_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    with open(output_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)

        # Header
        header = ['Offset', 'English', 'French', 'Length', 'Encoding', 'Category', 'Notes']
        writer.writerow(header)

        # Data
        for entry in data['texts']:
            category = detect_category(entry['text'], entry['offset']) if add_categories else ''
            row = [
                f"0x{entry['offset']:08X}",
                entry['text'],
                '',  # French (vide, à remplir)
                entry['length'],
                entry['encoding'],
                category,
                ''   # Notes
            ]
            writer.writerow(row)
```

**Tâches de développement** :
- [ ] Implémenter `json_to_csv()`
- [ ] Implémenter `detect_category()` avec règles intelligentes
- [ ] Gérer encodage UTF-8 + BOM pour Excel
- [ ] Ajouter validation des données
- [ ] Tests avec fichier réel
- [ ] Documentation d'utilisation

---

#### Spécifications `csv_to_json.py`

```python
#!/usr/bin/env python3
"""
Convertit CSV traduit en JSON pour réinsertion ROM.

Usage:
    python csv_to_json.py translated.csv output.json

Validations:
- Vérifier offsets valides
- Vérifier longueurs
- Détecter caractères non supportés
- Alerter textes trop longs
"""

import csv
import json
from pathlib import Path

def validate_translation(row):
    """
    Valider une ligne de traduction.

    Retourne: (valid, errors, warnings)
    """
    errors = []
    warnings = []

    # Vérifier longueur
    french = row['French']
    max_length = int(row['Length'])

    if len(french) > max_length:
        errors.append(f"Text too long: {len(french)} > {max_length}")

    # Vérifier caractères
    if row['Encoding'] == 'pokemon':
        unsupported = check_pokemon_chars(french)
        if unsupported:
            warnings.append(f"Unsupported chars: {unsupported}")

    return (len(errors) == 0, errors, warnings)

def csv_to_json(input_csv, output_json, validate=True):
    """Convertir CSV → JSON"""
    with open(input_csv, 'r', encoding='utf-8-sig') as f:  # -sig pour BOM
        reader = csv.DictReader(f)

        texts = []
        errors = []
        warnings = []

        for i, row in enumerate(reader, start=2):  # Start at 2 (header = 1)
            # Validation
            if validate:
                valid, errs, warns = validate_translation(row)
                if not valid:
                    errors.extend([f"Row {i}: {e}" for e in errs])
                warnings.extend([f"Row {i}: {w}" for w in warns])

            # Convertir offset
            offset = int(row['Offset'], 16)  # 0x12345 → int

            # Créer entry
            entry = {
                'offset': offset,
                'text': row['French'],
                'length': int(row['Length']),
                'encoding': row['Encoding']
            }
            texts.append(entry)

        # Afficher résumé
        print(f"Translated: {len(texts)} texts")
        if warnings:
            print(f"Warnings: {len(warnings)}")
            for w in warnings[:10]:
                print(f"  ⚠ {w}")
        if errors:
            print(f"ERRORS: {len(errors)}")
            for e in errors:
                print(f"  ❌ {e}")
            return False

        # Sauver JSON
        output_data = {
            'rom_name': 'englishrom.gba',
            'text_count': len(texts),
            'texts': texts
        }

        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        return True
```

**Tâches de développement** :
- [ ] Implémenter `csv_to_json()`
- [ ] Implémenter validations complètes
- [ ] Gérer BOM Excel (UTF-8-sig)
- [ ] Rapport d'erreurs détaillé
- [ ] Tests avec cas limites
- [ ] Documentation

---

### Task 1.2 : Interface web simple de traduction (OPTIONNEL)
**Temps estimé** : 3-5 jours
**Difficulté** : Moyenne
**Stack** : Python Flask + HTML/JS

**Objectif** : Interface utilisateur pour traduction collaborative

**Architecture** :
```
translation-web/
├── app.py                  # Flask app
├── database.py             # SQLite operations
├── templates/
│   ├── index.html         # Liste des textes
│   ├── translate.html     # Interface traduction
│   └── stats.html         # Statistiques
├── static/
│   ├── style.css
│   └── app.js
└── data/
    ├── texts.db           # SQLite database
    └── exports/           # JSON exports
```

**Fonctionnalités** :
- [ ] Import JSON initial dans SQLite
- [ ] Liste paginée des textes (50/page)
- [ ] Filtres (catégorie, status, traducteur)
- [ ] Interface de traduction :
  - Texte anglais affiché
  - Champ traduction française
  - Compteur caractères restants
  - Bouton "Valider" (ctrl+Enter)
  - Navigation texte suivant/précédent
- [ ] Système de statut (à faire/en cours/fait/revu)
- [ ] Export JSON pour réinsertion
- [ ] Statistiques temps réel
- [ ] Multi-utilisateurs (optionnel)

**Priorité** : Basse (Nice to have mais pas essentiel)

---

## Sprint 2 : Amélioration système de relocalisation (Priorité MOYENNE)

### Task 2.1 : Analyser structure des tables de textes Pokemon
**Temps estimé** : 3-5 jours
**Difficulté** : Difficile
**Prérequis** : Connaissance ROM hacking Pokemon

**Objectif** : Comprendre exactement comment Pokemon FireRed organise les textes pour pouvoir les relocaliser

**Recherches nécessaires** :

#### A. Étudier les tables de pointeurs existantes
```python
# analyze_text_tables.py

def analyze_pointer_table(rom_data, table_offset, num_pointers):
    """
    Analyser une table de pointeurs et ses cibles.

    Pour chaque pointeur:
    - Où pointe-t-il?
    - Quel texte y a-t-il?
    - Combien d'espace?
    - Y a-t-il un pattern?
    """
    pass

# Exemple: Table à 0x0003FDD4 avec 85 pointeurs
results = analyze_pointer_table(rom, 0x0003FDD4, 85)
```

**Tâches** :
- [ ] Lister les 20 plus grandes tables de pointeurs
- [ ] Analyser leur structure (offset, taille, pattern)
- [ ] Identifier les textes qu'elles référencent
- [ ] Comparer avec version espagnole
- [ ] Documenter findings dans `docs/table_structures.md`

---

#### B. Reverse engineer structures de données
**Documentation à créer** : `docs/pokemon_text_structures.md`

**Questions à répondre** :
1. Comment le jeu accède aux textes?
   - Par index dans une table?
   - Par pointeur direct?
   - Par offset calculé?

2. Quelles sont les structures?
   ```c
   // Exemple hypothétique
   struct TextEntry {
       uint8_t* text_pointer;  // Pointeur vers texte
       uint16_t max_length;    // Longueur max?
       uint8_t flags;          // Flags spéciaux?
   }
   ```

3. Y a-t-il des métadonnées?
   - Longueur stockée quelque part?
   - Checksums?
   - Références croisées?

**Méthode** :
- [ ] Hex dump de zones suspectes
- [ ] Comparaison English vs Spanish ROM
- [ ] Lecture documentation PokéCommunity
- [ ] Tests avec ROM modifiée (essai-erreur)
- [ ] Utilisation d'émulateur avec debugger

**Outils** :
- HxD (hex editor)
- Hex Fiend (Mac)
- mGBA avec debugger
- IDA Pro / Ghidra (désassemblage ARM)

---

### Task 2.2 : Implémenter détection de tables de textes
**Temps estimé** : 2-3 jours
**Difficulté** : Moyenne-Difficile
**Dépend de** : Task 2.1

**Objectif** : Script qui identifie automatiquement qu'un texte fait partie d'une table

**Fichier** : `analyze_text_tables.py` (amélioration)

```python
class TextTable:
    """Représente une table de textes."""
    def __init__(self, pointer_table_offset, num_entries):
        self.pointer_table_offset = pointer_table_offset
        self.num_entries = num_entries
        self.text_offsets = []
        self.texts = []
        self.total_size = 0

def find_text_table_for_offset(rom_data, target_offset):
    """
    Trouver la table de pointeurs qui contient un texte à target_offset.

    Algorithme:
    1. Chercher toutes les tables de pointeurs
    2. Pour chaque table:
       a. Lire tous les pointeurs
       b. Convertir en offsets ROM
       c. Vérifier si target_offset est dans la liste
    3. Retourner la table correspondante

    Retourne: TextTable ou None
    """
    # Scanner toutes les tables connues
    known_tables = detect_all_pointer_tables(rom_data)

    for table in known_tables:
        if target_offset in table.text_offsets:
            return table

    return None

def detect_all_pointer_tables(rom_data):
    """
    Détecter toutes les tables de pointeurs dans la ROM.

    Critères:
    - Au moins 5 pointeurs consécutifs valides
    - Tous pointent dans la ROM
    - Pattern régulier (espacés de 4 bytes)
    """
    tables = []

    # Scanner ROM par blocs de 4 bytes
    for offset in range(0, len(rom_data) - 20, 4):
        # Tenter de lire 10 pointeurs
        pointers = []
        valid_count = 0

        for i in range(10):
            ptr_offset = offset + (i * 4)
            ptr_value = struct.unpack('<I', rom_data[ptr_offset:ptr_offset+4])[0]

            # Vérifier si pointeur valide
            if is_valid_rom_pointer(ptr_value):
                pointers.append(ptr_value)
                valid_count += 1
            else:
                break

        # Si au moins 5 pointeurs valides → probable table
        if valid_count >= 5:
            # Continuer à lire jusqu'à pointeur invalide
            full_table = read_full_pointer_table(rom_data, offset)
            tables.append(full_table)

    return tables
```

**Tâches** :
- [ ] Implémenter `find_text_table_for_offset()`
- [ ] Implémenter `detect_all_pointer_tables()`
- [ ] Cache des tables détectées (pour performance)
- [ ] Tests avec offsets connus
- [ ] Validation avec version espagnole
- [ ] Documentation

---

### Task 2.3 : Implémenter relocalisation de tables complètes
**Temps estimé** : 4-5 jours
**Difficulté** : Difficile
**Dépend de** : Task 2.1, 2.2

**Objectif** : Pouvoir déplacer une table entière de textes dans l'espace libre

**Fichier** : `relocate_text_table.py`

```python
class TableRelocator:
    """Relocate une table complète de textes."""

    def __init__(self, rom_data):
        self.rom_data = bytearray(rom_data)
        self.free_space_offset = find_large_free_space(self.rom_data, min_size=100000)
        self.relocations = []

    def relocate_table(self, table: TextTable, new_texts: dict):
        """
        Relocate une table entière avec nouveaux textes.

        Args:
            table: TextTable détectée
            new_texts: {offset: new_text_string}

        Algorithme:
        1. Calculer espace total nécessaire
        2. Allouer bloc dans free space
        3. Écrire tous les nouveaux textes dans le bloc
        4. Construire nouvelle table de pointeurs
        5. Écrire nouvelle table de pointeurs
        6. Mettre à jour pointeur vers la table
        7. Effacer anciennes données
        8. Logger toutes les modifications
        """

        # Étape 1: Calculer espace nécessaire
        total_size = 0
        encoded_texts = {}

        for offset, new_text in new_texts.items():
            encoded = encode_text(new_text, 'pokemon')
            encoded_texts[offset] = encoded
            total_size += len(encoded)

        # Étape 2: Allouer espace
        new_text_block_offset = self.free_space_offset
        self.free_space_offset += total_size + 100  # +100 pour padding

        # Étape 3: Écrire textes
        current_offset = new_text_block_offset
        new_text_offsets = {}

        for original_offset in sorted(encoded_texts.keys()):
            encoded = encoded_texts[original_offset]
            self.rom_data[current_offset:current_offset+len(encoded)] = encoded
            new_text_offsets[original_offset] = current_offset
            current_offset += len(encoded)

        # Étape 4-5: Reconstruire table de pointeurs
        new_pointer_table_offset = self.free_space_offset
        self.free_space_offset += table.num_entries * 4

        for i, original_offset in enumerate(table.text_offsets):
            new_offset = new_text_offsets.get(original_offset, original_offset)
            new_pointer = GBA_ROM_BASE + new_offset

            ptr_location = new_pointer_table_offset + (i * 4)
            self.rom_data[ptr_location:ptr_location+4] = struct.pack('<I', new_pointer)

        # Étape 6: Mettre à jour pointeur vers la table
        # CRUCIAL: Trouver où est stocké le pointeur vers la table
        # Ceci dépend de la structure spécifique du jeu
        table_pointer_location = find_table_pointer_location(table.pointer_table_offset)
        new_table_pointer = GBA_ROM_BASE + new_pointer_table_offset
        self.rom_data[table_pointer_location:table_pointer_location+4] = struct.pack('<I', new_table_pointer)

        # Étape 7: Effacer anciennes données
        self.clear_old_data(table)

        # Étape 8: Logger
        self.relocations.append({
            'table_offset': table.pointer_table_offset,
            'new_table_offset': new_pointer_table_offset,
            'num_texts': len(new_texts),
            'space_used': total_size
        })

        return True
```

**Défis majeurs** :
1. **Trouver le pointeur vers la table** : Le plus difficile
   - Où est stocké le pointeur qui pointe vers la table de pointeurs?
   - Peut être dans le code ARM du jeu
   - Nécessite désassemblage

2. **Gestion des dépendances**
   - Si une table référence une autre table?
   - Textes partagés entre plusieurs tables?

3. **Tests et validation**
   - Comment tester sans casser la ROM?
   - Besoin de tests incrémentaux

**Tâches** :
- [ ] Implémenter `TableRelocator` class
- [ ] Implémenter `find_table_pointer_location()` (HARD)
- [ ] Système de rollback en cas d'erreur
- [ ] Tests unitaires sur petites tables
- [ ] Tests d'intégration sur ROM réelle
- [ ] Documentation architecture

---

### Task 2.4 : Créer script de validation ROM avancé
**Temps estimé** : 2 jours
**Difficulté** : Moyenne

**Objectif** : Vérifier qu'une ROM modifiée est valide avant distribution

**Fichier** : `validate_rom_advanced.py`

```python
#!/usr/bin/env python3
"""
Validation avancée de ROM modifiée.

Vérifications:
1. Intégrité structurelle
2. Checksum header
3. Textes affichables
4. Boot émulateur
5. Comparaison avec ROM originale
"""

import hashlib
import subprocess
from pathlib import Path

class ROMValidator:
    def __init__(self, rom_path, original_rom_path=None):
        self.rom_path = Path(rom_path)
        self.original_rom_path = Path(original_rom_path) if original_rom_path else None
        self.rom_data = None
        self.errors = []
        self.warnings = []

    def validate_all(self):
        """Exécuter toutes les validations."""
        self.load_rom()
        self.check_header()
        self.check_size()
        self.check_checksum()
        self.check_free_space_integrity()
        self.check_text_validity()

        if self.original_rom_path:
            self.compare_with_original()

        self.generate_report()

    def check_header(self):
        """Vérifier header GBA valide."""
        # Offset 0xA0-0xAB: Game title
        title = self.rom_data[0xA0:0xAC]
        if b'POKEMON' not in title:
            self.errors.append("Invalid game title in header")

        # Offset 0xAC-0xAF: Game code (BPRE pour FireRed)
        game_code = self.rom_data[0xAC:0xB0]
        if game_code != b'BPRE':
            self.warnings.append(f"Unexpected game code: {game_code}")

    def check_free_space_integrity(self):
        """Vérifier que l'espace libre utilisé est marqué correctement."""
        # Vérifier qu'on n'a pas écrasé de code important
        pass

    def check_text_validity(self):
        """Vérifier que tous les textes sont affichables."""
        # Extraire quelques textes et vérifier qu'ils sont décodables
        pass

    def test_emulator_boot(self, emulator_path='mgba'):
        """Tester démarrage dans émulateur."""
        try:
            # Lancer émulateur en mode headless
            result = subprocess.run(
                [emulator_path, '-x', str(self.rom_path)],
                timeout=10,
                capture_output=True
            )
            if result.returncode != 0:
                self.errors.append("ROM failed to boot in emulator")
        except subprocess.TimeoutExpired:
            # OK, le jeu tourne
            pass
        except FileNotFoundError:
            self.warnings.append("Emulator not found, skipping boot test")

    def generate_report(self):
        """Générer rapport de validation."""
        print("="*80)
        print("ROM VALIDATION REPORT")
        print("="*80)
        print(f"ROM: {self.rom_path.name}")
        print(f"Size: {len(self.rom_data)} bytes")
        print()

        if not self.errors and not self.warnings:
            print("✅ ALL CHECKS PASSED")
        else:
            if self.errors:
                print(f"❌ ERRORS ({len(self.errors)}):")
                for err in self.errors:
                    print(f"  • {err}")
            if self.warnings:
                print(f"⚠️  WARNINGS ({len(self.warnings)}):")
                for warn in self.warnings:
                    print(f"  • {warn}")

        print("="*80)
```

**Tâches** :
- [ ] Implémenter toutes les méthodes de validation
- [ ] Ajouter test émulateur automatique
- [ ] Générer rapport HTML (optionnel)
- [ ] Integration dans CI/CD (optionnel)
- [ ] Documentation

---

## Sprint 3 : Tests automatisés (Priorité BASSE)

### Task 3.1 : Framework de tests automatisés
**Temps estimé** : 5-7 jours
**Difficulté** : Difficile
**Stack** : Python + mGBA API

**Objectif** : Tests automatiques pour éviter régressions

**Architecture** :
```python
# test_framework.py

class ROMTest:
    """Test automatisé sur émulateur."""

    def setup(self):
        """Démarrer émulateur, charger ROM."""
        pass

    def run(self):
        """Exécuter test."""
        pass

    def assert_text_displayed(self, expected_text):
        """Vérifier texte à l'écran."""
        pass

    def press_button(self, button):
        """Simuler input."""
        pass

# Exemples de tests
class TestIntroSequence(ROMTest):
    def test_intro_text(self):
        self.wait(5)  # Attendre intro
        self.assert_text_displayed("Bienvenue")
        self.press_button('A')
        self.assert_text_displayed("dans le monde")

class TestFirstDialog(ROMTest):
    def test_oak_dialog(self):
        # Navigation jusqu'au Prof Oak
        self.navigate_to_oak()
        self.interact()
        self.assert_text_displayed("Bonjour!")
```

**Fonctionnalités** :
- [ ] Integration avec émulateur (libmgba)
- [ ] Capture d'écran + OCR pour vérifier textes
- [ ] Savestates pour tests rapides
- [ ] Suite de tests couvrant:
  - Intro
  - 10 premiers dialogues
  - Menus principaux
  - Combat
  - Capture Pokémon

**Priorité** : Basse (Nice to have, pas critique)

---

## Sprint 4 : Documentation et outils support

### Task 4.1 : Documentation complète du système
**Temps estimé** : 2-3 jours

**Documents à créer/compléter** :
- [ ] `docs/ARCHITECTURE.md` - Architecture technique
- [ ] `docs/TEXT_ENCODING.md` - Encodage Pokemon détaillé
- [ ] `docs/POINTER_SYSTEM.md` - Système de pointeurs
- [ ] `docs/TABLE_STRUCTURES.md` - Structures tables de textes
- [ ] `docs/TRANSLATION_GUIDE.md` - Guide du traducteur
- [ ] `docs/API.md` - API des scripts Python

---

### Task 4.2 : Script de création de patch IPS
**Temps estimé** : 1 jour
**Difficulté** : Facile

**Fichier** : `create_patch.py`

```python
#!/usr/bin/env python3
"""
Créer patch IPS entre ROM originale et ROM traduite.

IPS Format:
- Header: PATCH
- Records: Offset (3 bytes) | Size (2 bytes) | Data (size bytes)
- Footer: EOF
"""

def create_ips_patch(original_rom, modified_rom, output_ips):
    """
    Générer patch IPS.

    Algorithme:
    1. Comparer byte par byte
    2. Identifier zones modifiées
    3. Grouper modifications proches
    4. Écrire format IPS
    """
    with open(original_rom, 'rb') as f:
        original = f.read()
    with open(modified_rom, 'rb') as f:
        modified = f.read()

    # Trouver différences
    changes = []
    i = 0
    while i < len(original):
        if original[i] != modified[i]:
            # Début d'un bloc de changements
            start = i
            while i < len(original) and original[i] != modified[i]:
                i += 1
            end = i
            changes.append((start, modified[start:end]))
        else:
            i += 1

    # Écrire IPS
    with open(output_ips, 'wb') as f:
        f.write(b'PATCH')

        for offset, data in changes:
            f.write(offset.to_bytes(3, 'big'))
            f.write(len(data).to_bytes(2, 'big'))
            f.write(data)

        f.write(b'EOF')
```

**Tâches** :
- [ ] Implémenter algorithme IPS
- [ ] Optimiser taille patch (grouper modifications proches)
- [ ] Tests avec ROMs réelles
- [ ] Script d'application de patch (optionnel)

---

## Récapitulatif priorités

### 🔴 PRIORITÉ HAUTE (Sprint 1)
**Temps total** : 1-2 semaines

1. ✅ `json_to_csv.py` - Essential pour traducteurs
2. ✅ `csv_to_json.py` - Essential pour traducteurs
3. Tests et validation des outils

**Impact** : Débloque le travail de traduction

---

### 🟡 PRIORITÉ MOYENNE (Sprint 2)
**Temps total** : 3-4 semaines

1. Analyse structure tables Pokemon
2. Détection automatique tables
3. Relocalisation tables complètes
4. Validation ROM avancée

**Impact** : Permet textes plus longs (si nécessaire)

---

### 🟢 PRIORITÉ BASSE (Sprint 3-4)
**Temps total** : 2-3 semaines

1. Interface web traduction
2. Tests automatisés émulateur
3. Documentation exhaustive
4. Patch IPS

**Impact** : Améliore confort mais pas essentiel

---

## Décision technique recommandée

### Pour démarrer RAPIDEMENT (recommandé) ⭐

**Approche** : Conservative
**Focus** : Sprint 1 uniquement
**Temps** : 1-2 semaines dev

**Avantages** :
- ✅ Démarrage traduction sous 2 semaines
- ✅ Outils simples et fiables
- ✅ Peu de risques techniques
- ✅ Workflow éprouvé (CSV = Excel)

**Limitations** :
- ❌ Textes français ≤ textes anglais
- ❌ Pas de relocalisation avancée

**Résultat attendu** :
- ROM traduite fonctionnelle en 2-3 mois
- Qualité = version espagnole officielle

---

### Pour système COMPLET (long terme)

**Approche** : Avancée
**Focus** : Tous les sprints
**Temps** : 2-3 mois dev

**Avantages** :
- ✅ Textes sans limite de longueur
- ✅ Système professionnel complet
- ✅ Réutilisable pour autres ROMs

**Inconvénients** :
- ⚠️ Temps de développement important
- ⚠️ Risques techniques élevés
- ⚠️ Tests approfondis requis

**Résultat attendu** :
- Système de traduction universel
- ROM traduite en 4-6 mois (incluant dev)

---

## Prochaines actions immédiates

### Cette semaine
- [ ] **DÉCISION** : Approche conservative ou avancée?
- [ ] Créer `json_to_csv.py`
- [ ] Créer `csv_to_json.py`
- [ ] Tests avec 100 premiers textes
- [ ] Valider workflow CSV → JSON → ROM

### Prochaines 2 semaines
- [ ] Formation traducteurs sur outils
- [ ] Traduction test 500 textes
- [ ] Génération ROM alpha
- [ ] Tests alpha sur émulateur

---

**Dernière mise à jour** : 2026-01-13
**Status** : Planification technique complète
**Recommandation** : Démarrer avec Sprint 1 (conservative)
