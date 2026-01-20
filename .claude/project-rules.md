# Règles d'Architecture du Projet

## 📁 Structure des Dossiers

### Interdictions STRICTES

- ❌ **JAMAIS de fichiers de travail à la racine**
- ❌ **JAMAIS de scripts Python (.py) à la racine**
- ❌ **JAMAIS de scripts temporaires à la racine**
- ❌ **JAMAIS de résultats d'analyse à la racine**
- ❌ **JAMAIS de documentation non-numérotée dans docs/**
- ❌ **JAMAIS de fichiers markdown à la racine sauf README.md**

### Fichiers Autorisés à la Racine

**UNIQUEMENT ces fichiers peuvent être à la racine :**
- ✅ `README.md` (point d'entrée principal)
- ✅ `Makefile` (automatisation)
- ✅ `requirements.txt` (dépendances Python)
- ✅ `.gitignore`
- ✅ Fichiers de configuration (`.editorconfig`, etc.)

### Structure Obligatoire

```
Unbound Begin/
├── .claude/                    # Configuration Claude
│   └── project-rules.md
│
├── input/                      # SOURCES (lecture seule)
│   ├── roms/
│   │   ├── englishrom.gba
│   │   └── spanishrom.gba
│   └── references/
│
├── output/                     # RÉSULTATS (générés)
│   ├── roms/                   # ROMs modifiées
│   ├── extracted/              # Textes extraits
│   ├── analysis/               # Analyses
│   ├── differences/            # Comparaisons
│   └── reports/                # Rapports
│
├── src/                        # CODE SOURCE
│   ├── core/                   # Classes et fonctions communes
│   │   ├── __init__.py
│   │   ├── rom_reader.py       # Lecture ROM
│   │   ├── text_encoder.py     # Encodage/décodage
│   │   ├── pointer_utils.py    # Gestion pointeurs
│   │   └── padding_detector.py # Détection padding
│   │
│   ├── extractors/             # Scripts d'extraction
│   │   ├── __init__.py
│   │   ├── 01_extract_text.py
│   │   └── 02_compare_texts.py
│   │
│   ├── analyzers/              # Scripts d'analyse
│   │   ├── __init__.py
│   │   ├── 03_analyze_structure.py
│   │   ├── 04_detect_tables.py
│   │   └── 05_detect_arrays.py
│   │
│   ├── translators/            # Scripts de traduction
│   │   ├── __init__.py
│   │   ├── 06_detect_padding.py
│   │   ├── 07_reinsert_smart.py
│   │   ├── 08_json_to_csv.py
│   │   └── 09_csv_to_json.py
│   │
│   └── utils/                  # Utilitaires
│       ├── __init__.py
│       ├── validation.py
│       └── reporting.py
│
├── docs/                       # DOCUMENTATION (TOUJOURS numérotée)
│   ├── 00_README.md            # Index général
│   ├── 01_SOLUTION.md          # Stratégie principale
│   ├── 02_TECHNICAL.md         # Documentation technique
│   ├── 03_ARCHITECTURE.md      # Architecture code
│   ├── 04_TASKS.md             # Planning projet
│   ├── 05_TASKS_TECHNICAL.md   # Tâches dev
│   ├── 06_STRATEGY.md          # Stratégies
│   ├── 07_WORKFLOW_READY.md    # Workflows
│   ├── 08_ARCHITECTURE_OOP.md  # Architecture OOP
│   ├── 09_CHANGELOG.md         # Historique
│   ├── 10_PROJECT_STATUS.md    # État projet
│   ├── 11_GUIDE_TRADUCTEURS.md # Guide traducteurs
│   └── recaps/                 # Récapitulatifs de sessions
│       ├── INDEX.md
│       ├── RESUME_EXECUTIF.md
│       └── RECAP_SESSION_*.md
│
├── tests/                      # TESTS
│   ├── test_core/
│   ├── test_extractors/
│   └── fixtures/
│
├── scripts/                    # Scripts auxiliaires
│   └── legacy/                 # Scripts anciens (archivés)
│
├── README.md                   # README principal (SEUL MD à la racine)
├── Makefile                    # Automatisation
├── requirements.txt            # Dépendances Python
└── .gitignore
```

---

## 🏗️ Architecture du Code

### Principe : DRY (Don't Repeat Yourself)

**OBLIGATOIRE** :
1. ✅ Code commun dans `src/core/`
2. ✅ Fonctions réutilisables
3. ✅ Classes pour structures complexes
4. ✅ Imports depuis core dans tous les scripts
5. ✅ Approche orientée objet

**INTERDIT** :
1. ❌ Dupliquer du code entre scripts
2. ❌ Copier-coller de fonctions
3. ❌ Code procédural long
4. ❌ Fonctions monolithiques

### Exemple de Structure

```python
# src/core/rom_reader.py
class ROMReader:
    """Classe pour lire et manipuler une ROM GBA."""

    GBA_ROM_BASE = 0x08000000

    def __init__(self, rom_path):
        self.rom_path = Path(rom_path)
        self.rom_data = None
        self.rom_size = 0

    def load(self):
        """Charge la ROM en mémoire."""
        pass

    def read_pointer(self, offset):
        """Lit un pointeur 32-bit."""
        pass

# src/extractors/01_extract_text.py
from src.core.rom_reader import ROMReader
from src.core.text_encoder import PokemonEncoder

def main():
    rom = ROMReader('input/roms/englishrom.gba')
    rom.load()
    encoder = PokemonEncoder()
    # ...
```

---

## 📝 Conventions de Nommage

### Fichiers

#### Scripts (numérotés par ordre d'exécution)
```
01_extract_text.py      # Premier script
02_compare_texts.py     # Deuxième script
03_analyze_structure.py # Troisième script
...
```

#### Documentation (OBLIGATOIREMENT numérotée par importance)

**RÈGLE STRICTE** : Tout document dans `docs/` DOIT être numéroté au format `NN_NOM.md`

```
00_README.md            # Index (toujours en premier)
01_SOLUTION.md          # Document principal
02_TECHNICAL.md         # Documentation technique
03_ARCHITECTURE.md      # Architecture
04_TASKS.md             # Planning
...
11_GUIDE_TRADUCTEURS.md # Guide utilisateur
```

**Exception** : Les sous-dossiers comme `docs/recaps/` peuvent contenir des fichiers non-numérotés pour les récapitulatifs de sessions.

#### Modules Core (descriptifs)
```
rom_reader.py           # Lecture ROM
text_encoder.py         # Encodage textes
pointer_utils.py        # Utilitaires pointeurs
padding_detector.py     # Détection padding
```

### Classes et Fonctions

```python
# Classes : PascalCase
class ROMReader:
class TextExtractor:
class PaddingDetector:

# Fonctions : snake_case
def read_pointer(offset):
def detect_padding(rom, offset):
def encode_pokemon_text(text):

# Constantes : UPPER_SNAKE_CASE
GBA_ROM_BASE = 0x08000000
POKEMON_CHAR_TABLE = {...}
```

---

## 🔧 Gestion des Entrées/Sorties

### Entrées (input/)

**Règle** : Fichiers sources en lecture seule, JAMAIS modifiés

```
input/
├── roms/
│   ├── englishrom.gba          # ROM source (lecture seule)
│   └── spanishrom.gba          # ROM référence (lecture seule)
└── references/
    └── pokemon_encoding.json   # Tables de référence
```

### Sorties (output/)

**Règle** : Tous les fichiers générés vont dans output/

```
output/
├── roms/                       # ROMs modifiées
│   ├── frenchrom.gba
│   └── frenchrom.gba.bak
│
├── extracted/                  # Textes extraits
│   ├── 2026-01-13_englishrom_texts.json
│   ├── 2026-01-13_spanishrom_texts.json
│   └── 2026-01-13_englishrom_texts.txt
│
├── analysis/                   # Analyses
│   ├── 2026-01-13_text_arrays.json
│   ├── 2026-01-13_text_tables.json
│   └── 2026-01-13_padding_analysis.json
│
├── differences/                # Comparaisons
│   ├── 2026-01-13_differences.json
│   └── 2026-01-13_englishrom_diff_only.json
│
└── reports/                    # Rapports
    ├── 2026-01-13_validation_report.json
    └── 2026-01-13_translation_report.json
```

**Nommage** : `YYYY-MM-DD_description.extension`

---

## 🎯 Flux de Travail

### Phase 1 : Extraction
```bash
python src/extractors/01_extract_text.py input/roms/englishrom.gba
# → output/extracted/2026-01-13_englishrom_texts.json

python src/extractors/02_compare_texts.py
# → output/differences/2026-01-13_differences.json
```

### Phase 2 : Analyse
```bash
python src/analyzers/03_analyze_structure.py
# → output/analysis/2026-01-13_structure.json

python src/analyzers/04_detect_tables.py
# → output/analysis/2026-01-13_tables.json
```

### Phase 3 : Traduction
```bash
python src/translators/06_detect_padding.py
# → output/analysis/2026-01-13_padding.json

python src/translators/07_reinsert_smart.py translation.json
# → output/roms/frenchrom.gba
# → output/reports/2026-01-13_translation_report.json
```

---

## 📦 Classes Core Obligatoires

### 1. ROMReader (src/core/rom_reader.py)
```python
class ROMReader:
    """Lecture et manipulation ROM GBA."""
    def __init__(self, rom_path)
    def load(self)
    def read_pointer(self, offset)
    def is_valid_pointer(self, ptr_value)
    def read_bytes(self, offset, length)
```

### 2. TextEncoder (src/core/text_encoder.py)
```python
class PokemonEncoder:
    """Encodage/décodage textes Pokemon."""
    def encode(self, text)
    def decode(self, bytes_data)
    def get_encoded_length(self, text)

class ASCIIEncoder:
    """Encodage/décodage ASCII."""
    def encode(self, text)
    def decode(self, bytes_data)
```

### 3. PaddingDetector (src/core/padding_detector.py)
```python
class PaddingDetector:
    """Détection padding disponible."""
    def __init__(self, rom_reader)
    def detect_padding(self, offset, length)
    def count_padding_bytes(self, offset)
    def analyze_all_texts(self, texts)
```

### 4. PointerUtils (src/core/pointer_utils.py)
```python
class PointerManager:
    """Gestion des pointeurs."""
    def __init__(self, rom_reader)
    def find_pointers_to(self, target_offset)
    def update_pointer(self, ptr_location, new_target)
    def validate_pointer(self, ptr_value)
```

---

## 🧪 Tests

### Structure
```
tests/
├── test_core/
│   ├── test_rom_reader.py
│   ├── test_text_encoder.py
│   └── test_padding_detector.py
│
├── test_extractors/
│   └── test_extract_text.py
│
└── fixtures/
    ├── sample_rom.gba (petit échantillon)
    └── expected_results.json
```

### Commandes
```bash
# Tester tout
pytest tests/

# Tester un module
pytest tests/test_core/test_rom_reader.py

# Couverture
pytest --cov=src tests/
```

---

## 📋 Makefile Structuré

```makefile
# Variables
INPUT_DIR = input/roms
OUTPUT_DIR = output
SRC_DIR = src

# Extraction
extract:
	python $(SRC_DIR)/extractors/01_extract_text.py $(INPUT_DIR)/englishrom.gba
	python $(SRC_DIR)/extractors/01_extract_text.py $(INPUT_DIR)/spanishrom.gba

# Comparaison
compare:
	python $(SRC_DIR)/extractors/02_compare_texts.py

# Analyse
analyze:
	python $(SRC_DIR)/analyzers/03_analyze_structure.py
	python $(SRC_DIR)/analyzers/04_detect_tables.py
	python $(SRC_DIR)/analyzers/05_detect_arrays.py

# Traduction
translate:
	python $(SRC_DIR)/translators/07_reinsert_smart.py translation.json

# Nettoyage
clean:
	rm -rf $(OUTPUT_DIR)/*
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Tests
test:
	pytest tests/

.PHONY: extract compare analyze translate clean test
```

---

## 🚨 Règles de Commit

### Structure des Commits
```
type(scope): description courte

Description détaillée si nécessaire.

- Point 1
- Point 2
```

### Types
- `feat`: Nouvelle fonctionnalité
- `fix`: Correction bug
- `refactor`: Refactorisation
- `docs`: Documentation
- `test`: Tests
- `chore`: Maintenance

### Exemples
```
feat(core): add PaddingDetector class

Implements padding detection using 0x00/0xFF byte analysis.
- Detects padding after text offsets
- Calculates real max length
- Returns padding statistics

refactor(extractors): move common code to core.rom_reader

Extracted ROMReader class to avoid code duplication
across 01_extract_text.py and 02_compare_texts.py
```

---

## 📚 Documentation Code

### Docstrings (obligatoires pour toutes les fonctions publiques)

```python
def detect_padding(rom, offset, length):
    """
    Détecte le padding disponible après un texte.

    Args:
        rom (ROMReader): Instance de lecteur ROM
        offset (int): Offset du texte dans la ROM
        length (int): Longueur du texte original

    Returns:
        int: Nombre de bytes de padding disponibles (0x00/0xFF)

    Example:
        >>> rom = ROMReader('input/roms/englishrom.gba')
        >>> rom.load()
        >>> padding = detect_padding(rom, 0x0023E5DA, 5)
        >>> print(padding)  # 7
    """
    pass
```

### Commentaires

```python
# Bon : Explique POURQUOI
# Use padding detection to allow overflows up to available space
padding = detect_padding(rom, offset, length)

# Mauvais : Explique QUOI (évident)
# Detect padding
padding = detect_padding(rom, offset, length)
```

---

## ⚡ Performance

### Règles
1. ✅ Charger ROM une seule fois
2. ✅ Réutiliser instances (ROMReader, Encoder)
3. ✅ Cache pour calculs répétitifs
4. ✅ Progress bars pour opérations longues

### Anti-patterns
1. ❌ Recharger ROM à chaque opération
2. ❌ Recréer encodeurs à chaque appel
3. ❌ Scans complets multiples
4. ❌ Pas de feedback utilisateur

---

## 🔒 Sécurité

### Règles
1. ✅ Toujours créer backup avant modification (.gba.bak)
2. ✅ Valider offsets avant écriture
3. ✅ Vérifier taille ROM
4. ✅ Confirmer écrasement fichiers existants

### Interdictions
1. ❌ Modifier ROM source directement
2. ❌ Écriture sans validation
3. ❌ Pas de backup
4. ❌ Ignorer erreurs de validation

---

## 🎯 Validation et Tests

### RÈGLE CRITIQUE : 100% Success Rate OBLIGATOIRE

**PRINCIPE FONDAMENTAL** : Un taux de succès en dessous de 100% est un ÉCHEC.

#### Obligations STRICTES

1. ✅ **100% de succès requis** : Tous les tests doivent passer sans exception
2. ✅ **Investigation obligatoire** : Chaque échec demande une véritable investigation
3. ✅ **Fix propre et générique** : Les corrections doivent être propres et génériques, pas de contournements
4. ✅ **Pas de skip** : Il ne faut skip AUCUN test pour masquer un échec

#### Processus en Cas d'Échec

Lorsqu'un test échoue :

1. **Investigation approfondie** :
   - Analyser la cause racine du problème
   - Examiner les bytes réels dans la ROM
   - Vérifier les patterns et structures de données
   - Comparer avec la ROM de référence (espagnole)

2. **Solution générique** :
   - Implémenter un fix qui résout la catégorie entière de problèmes
   - Ne PAS créer de cas spéciaux ou de contournements
   - Documenter la solution et le problème résolu

3. **Validation complète** :
   - Re-tester 100% du corpus après le fix
   - Vérifier qu'aucun nouveau problème n'a été introduit
   - Confirmer que le taux de succès est exactement 100.0%

#### Catégories de Solutions Acceptables

1. **Amélioration de la détection** : Filtrer les faux positifs (données corrompues, binaires, test data)
2. **Extension des capacités** : Améliorer la détection de padding, implémenter relocation
3. **Correction d'encodage** : Résoudre les problèmes de conversion de caractères
4. **Gestion structurelle** : Implémenter la gestion de tableaux, relocations complexes

#### Solutions INTERDITES

1. ❌ **Skip de tests** : Ne jamais ignorer un test qui échoue
2. ❌ **Hardcoded fixes** : Pas de corrections pour un offset spécifique
3. ❌ **Compromis de qualité** : 99.9% n'est PAS acceptable, même excellent
4. ❌ **Fausses excuses** : "C'est un cas limite", "C'est acceptable" → NON

#### Exemple

```python
# ❌ INTERDIT : Skip d'un test problématique
if offset == 0x00A44125:
    return True, "skip_known_issue"

# ✅ CORRECT : Investigation et fix générique
# Investigation révèle que certains textes utilisent un encodage spécial
# → Implémenter la détection et gestion de cet encodage spécial
# → Résultat : 100% de succès
```

---

## 📖 Résumé des Règles Principales

1. **📁 Structure** : Entrées dans `input/`, sorties dans `output/`, code dans `src/`
2. **🚫 Racine Propre** : AUCUN script Python, AUCUN markdown sauf README.md
3. **🔢 Numérotation** : Scripts et docs OBLIGATOIREMENT numérotés (NN_nom.md, NN_nom.py)
4. **🏗️ Architecture** : Code commun dans `src/core/`, approche orientée objet
5. **♻️ DRY** : Pas de duplication, réutiliser les classes core
6. **📝 Nommage** : Clair, descriptif, snake_case pour fonctions, PascalCase pour classes
7. **🧪 Tests** : Couvrir les fonctions critiques dans `tests/`
8. **📚 Documentation** :
   - Docstrings obligatoires pour toutes les classes/méthodes
   - Docs numérotés dans `docs/` (NN_NOM.md)
   - Type hints partout
9. **🔒 Sécurité** : Backups, validation, jamais modifier sources
10. **🎯 Validation** : 100% de succès OBLIGATOIRE, investigation complète des échecs

---

## 🚨 Checklist Avant Commit

Avant chaque commit, vérifier :

- [ ] ✅ Aucun fichier .py à la racine (sauf scripts à déplacer dans `src/` ou `scripts/legacy/`)
- [ ] ✅ Aucun fichier .md à la racine (sauf README.md)
- [ ] ✅ Tous les docs dans `docs/` sont numérotés (NN_NOM.md)
- [ ] ✅ Tous les scripts dans `src/` sont dans le bon sous-dossier
- [ ] ✅ Pas de code dupliqué (utiliser `src/core/`)
- [ ] ✅ Docstrings + type hints ajoutés
- [ ] ✅ Tests créés si nécessaire

---

**Ces règles DOIVENT être suivies STRICTEMENT pour TOUS les développements futurs.**
