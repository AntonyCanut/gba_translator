# Architecture du Code

**Date** : 2026-01-13
**Version** : 1.0

---

## Vue d'Ensemble

Architecture modulaire orientée objet avec séparation claire des responsabilités.

### Principes
- **DRY** : Don't Repeat Yourself
- **SOLID** : Single Responsibility, Open/Closed, etc.
- **Modularité** : Code réutilisable dans `src/core/`
- **Testabilité** : Classes découplées, facilement testables

---

## Structure des Modules

### src/core/ - Fonctionnalités Communes

#### 1. rom_reader.py
**Rôle** : Lecture et manipulation ROM GBA

```python
class ROMReader:
    """Lecteur ROM GBA avec gestion mémoire."""

    GBA_ROM_BASE = 0x08000000

    def __init__(self, rom_path: str)
    def load(self) -> None
    def read_bytes(self, offset: int, length: int) -> bytes
    def read_pointer(self, offset: int) -> Optional[int]
    def is_valid_pointer(self, ptr_value: int) -> bool
    def write_bytes(self, offset: int, data: bytes) -> None
    def save(self, output_path: str) -> None
```

#### 2. text_encoder.py
**Rôle** : Encodage/décodage textes (Pokemon + ASCII)

```python
class PokemonEncoder:
    """Encodeur pour textes Pokemon GBA."""

    CHAR_TABLE = {...}  # Table de caractères 0xBB-0xEE

    def encode(self, text: str) -> bytes
    def decode(self, data: bytes) -> str
    def get_encoded_length(self, text: str) -> int
    def is_valid_char(self, char: str) -> bool

class ASCIIEncoder:
    """Encodeur ASCII standard."""

    def encode(self, text: str) -> bytes
    def decode(self, data: bytes) -> str
```

#### 3. padding_detector.py
**Rôle** : Détection padding disponible (stratégie espagnole)

```python
class PaddingDetector:
    """Détecte padding (0x00/0xFF) après les textes."""

    PADDING_BYTES = [0x00, 0xFF]

    def __init__(self, rom_reader: ROMReader)
    def detect_padding(self, offset: int, length: int) -> int
    def analyze_text(self, text_entry: dict) -> dict
    def analyze_all_texts(self, texts: list) -> list
    def generate_report(self) -> dict
```

#### 4. pointer_utils.py
**Rôle** : Gestion pointeurs ROM

```python
class PointerManager:
    """Gestion des pointeurs 32-bit GBA."""

    def __init__(self, rom_reader: ROMReader)
    def find_pointers_to(self, target_offset: int) -> List[int]
    def update_pointer(self, ptr_location: int, new_target: int) -> None
    def validate_pointer(self, ptr_value: int) -> bool
    def scan_pointer_tables(self, min_entries: int = 5) -> List[PointerTable]
```

---

### src/extractors/ - Scripts d'Extraction

#### 01_extract_text.py
**Rôle** : Extraire tous les textes d'une ROM

```python
class TextExtractor:
    def __init__(self, rom_path: str)
    def extract_pokemon_texts(self) -> List[dict]
    def extract_ascii_texts(self) -> List[dict]
    def extract_all(self) -> dict
    def save_results(self, output_path: str) -> None
```

#### 02_compare_texts.py
**Rôle** : Comparer textes entre 2 ROMs

```python
class TextComparer:
    def __init__(self, rom1_texts: dict, rom2_texts: dict)
    def compare(self) -> List[dict]
    def filter_by_type(self, diff_type: str) -> List[dict]
    def calculate_similarity(self, text1: str, text2: str) -> float
    def save_results(self, output_path: str) -> None
```

---

### src/analyzers/ - Scripts d'Analyse

#### 03_analyze_structure.py
**Rôle** : Analyser structure ROM

```python
class ROMAnalyzer:
    def __init__(self, rom_path: str)
    def find_free_space(self) -> List[dict]
    def analyze_region(self, offset: int, length: int) -> dict
    def generate_report(self) -> dict
```

#### 04_detect_tables.py
**Rôle** : Détecter tables de pointeurs

```python
class PointerTableDetector:
    def __init__(self, rom_path: str)
    def detect_pointer_tables(self, min_entries: int = 5) -> List[PointerTable]
    def classify_tables(self) -> List[PointerTable]
    def find_text_tables(self) -> List[PointerTable]
```

#### 05_detect_arrays.py
**Rôle** : Détecter arrays séquentiels

```python
class TextArrayDetector:
    def __init__(self, rom_path: str, differences_json: str)
    def detect_text_arrays(self, max_gap: int = 100) -> List[TextArray]
    def match_tables_to_arrays(self) -> dict
    def find_relocation_chains(self) -> List[dict]
```

---

### src/translators/ - Scripts de Traduction

#### 06_detect_padding.py ⭐
**Rôle** : Analyser padding disponible (NOUVEAU)

```python
class PaddingAnalyzer:
    def __init__(self, rom_path: str, texts_json: str)
    def analyze_all_texts(self) -> List[dict]
    def generate_statistics(self) -> dict
    def save_results(self, output_path: str) -> None
```

#### 07_reinsert_smart.py ⭐
**Rôle** : Réinsertion padding-aware (NOUVEAU)

```python
class SmartTextReinserter:
    def __init__(self, rom_path: str, translation_json: str)
    def process_text(self, text_entry: dict) -> dict
    def reinsert_with_padding(self, offset: int, text: str, original_len: int) -> dict
    def create_backup(self) -> None
    def generate_report(self) -> dict
    def save_rom(self, output_path: str) -> None
```

#### 08_json_to_csv.py
**Rôle** : Export JSON → CSV

```python
class JSONToCSVConverter:
    def __init__(self, json_path: str)
    def detect_context(self, text_entry: dict) -> str
    def convert(self) -> pd.DataFrame
    def save_csv(self, output_path: str) -> None
```

#### 09_csv_to_json.py
**Rôle** : Import CSV → JSON

```python
class CSVToJSONConverter:
    def __init__(self, csv_path: str)
    def validate(self) -> bool
    def convert(self) -> dict
    def save_json(self, output_path: str) -> None
```

---

### src/utils/ - Utilitaires

#### validation.py
```python
def validate_translation_json(data: dict) -> Tuple[bool, List[str]]
def validate_text_length(text: str, max_length: int) -> bool
def validate_encoding(text: str, encoding: str) -> bool
```

#### reporting.py
```python
class ReportGenerator:
    def __init__(self)
    def add_section(self, title: str, content: dict)
    def generate_html(self) -> str
    def generate_json(self) -> dict
    def save(self, output_path: str)
```

---

## Flux de Données

### Phase 1 : Extraction
```
input/roms/englishrom.gba
    ↓
[01_extract_text.py] → ROMReader + PokemonEncoder
    ↓
output/extracted/2026-01-13_englishrom_texts.json
    ↓
[02_compare_texts.py] → TextComparer
    ↓
output/differences/2026-01-13_differences.json
```

### Phase 2 : Analyse
```
output/differences/*.json
    ↓
[04_detect_tables.py] → PointerTableDetector
    ↓
output/analysis/2026-01-13_tables.json
    ↓
[05_detect_arrays.py] → TextArrayDetector
    ↓
output/analysis/2026-01-13_arrays.json
```

### Phase 3 : Traduction (Padding-Aware) ⭐
```
output/differences/2026-01-13_diff_only.json
    ↓
[06_detect_padding.py] → PaddingDetector
    ↓
output/analysis/2026-01-13_padding.json
    ↓
[08_json_to_csv.py] → JSONToCSVConverter
    ↓
translation_workfile.csv
    ↓
[TRADUCTION MANUELLE]
    ↓
translation_completed.csv
    ↓
[09_csv_to_json.py] → CSVToJSONConverter
    ↓
translation.json
    ↓
[07_reinsert_smart.py] → SmartTextReinserter + PaddingDetector
    ↓
output/roms/frenchrom.gba
output/reports/2026-01-13_translation_report.json
```

---

## Classes Core - Spécifications Détaillées

### ROMReader

```python
class ROMReader:
    """
    Gère la lecture et l'écriture de ROMs GBA.

    Attributes:
        GBA_ROM_BASE (int): Adresse de base ROM (0x08000000)
        rom_path (Path): Chemin vers la ROM
        rom_data (bytearray): Données ROM en mémoire
        rom_size (int): Taille de la ROM
    """

    GBA_ROM_BASE = 0x08000000

    def __init__(self, rom_path: str):
        """
        Initialise le lecteur ROM.

        Args:
            rom_path: Chemin vers le fichier ROM
        """
        self.rom_path = Path(rom_path)
        self.rom_data = None
        self.rom_size = 0
        self._modified = False

    def load(self) -> None:
        """Charge la ROM en mémoire."""
        with open(self.rom_path, 'rb') as f:
            self.rom_data = bytearray(f.read())
        self.rom_size = len(self.rom_data)

    def read_bytes(self, offset: int, length: int) -> bytes:
        """
        Lit des bytes à un offset donné.

        Args:
            offset: Offset dans la ROM
            length: Nombre de bytes à lire

        Returns:
            bytes: Données lues

        Raises:
            ValueError: Si offset invalide
        """
        if offset + length > self.rom_size:
            raise ValueError(f"Read beyond ROM size: {offset}+{length} > {self.rom_size}")
        return bytes(self.rom_data[offset:offset+length])

    def read_pointer(self, offset: int) -> Optional[int]:
        """
        Lit un pointeur 32-bit little-endian.

        Args:
            offset: Offset du pointeur

        Returns:
            int ou None: Offset ROM si valide, None sinon
        """
        if offset + 4 > self.rom_size:
            return None

        ptr_value = struct.unpack('<I', self.rom_data[offset:offset+4])[0]

        if self.is_valid_pointer(ptr_value):
            return ptr_value - self.GBA_ROM_BASE
        return None

    def is_valid_pointer(self, ptr_value: int) -> bool:
        """
        Vérifie si une valeur est un pointeur ROM valide.

        Args:
            ptr_value: Valeur à vérifier

        Returns:
            bool: True si pointeur valide
        """
        if (ptr_value & 0xFF000000) != 0x08000000:
            return False

        rom_offset = ptr_value - self.GBA_ROM_BASE
        return 0 <= rom_offset < self.rom_size

    def write_bytes(self, offset: int, data: bytes) -> None:
        """
        Écrit des bytes à un offset donné.

        Args:
            offset: Offset d'écriture
            data: Données à écrire

        Raises:
            ValueError: Si écriture hors limites
        """
        if offset + len(data) > self.rom_size:
            raise ValueError(f"Write beyond ROM size")

        self.rom_data[offset:offset+len(data)] = data
        self._modified = True

    def save(self, output_path: str, create_backup: bool = True) -> None:
        """
        Sauvegarde la ROM.

        Args:
            output_path: Chemin de sortie
            create_backup: Créer un backup si fichier existe
        """
        output_path = Path(output_path)

        if output_path.exists() and create_backup:
            backup_path = Path(str(output_path) + '.bak')
            shutil.copy2(output_path, backup_path)

        with open(output_path, 'wb') as f:
            f.write(self.rom_data)

        self._modified = False
```

### PaddingDetector

```python
class PaddingDetector:
    """
    Détecte le padding disponible après les textes.
    Stratégie inspirée de la ROM espagnole.
    """

    PADDING_BYTES = [0x00, 0xFF]

    def __init__(self, rom_reader: ROMReader):
        """
        Initialise le détecteur.

        Args:
            rom_reader: Instance de ROMReader
        """
        self.rom = rom_reader
        self.stats = {
            'total_analyzed': 0,
            'with_padding': 0,
            'without_padding': 0,
            'avg_padding': 0.0,
            'max_padding': 0
        }

    def detect_padding(self, offset: int, length: int) -> int:
        """
        Détecte padding après un texte.

        Args:
            offset: Offset du texte
            length: Longueur du texte

        Returns:
            int: Nombre de bytes de padding disponibles
        """
        end = offset + length
        padding = 0

        while end + padding < self.rom.rom_size:
            byte = self.rom.rom_data[end + padding]
            if byte in self.PADDING_BYTES:
                padding += 1
            else:
                break

        return padding

    def analyze_text(self, text_entry: dict) -> dict:
        """
        Analyse un texte et détecte son padding.

        Args:
            text_entry: Dictionnaire avec 'offset' et 'length'

        Returns:
            dict: Entry enrichi avec padding info
        """
        offset = text_entry['offset']
        length = text_entry['length']

        padding = self.detect_padding(offset, length)

        enriched = text_entry.copy()
        enriched['padding_available'] = padding
        enriched['real_max_length'] = length + padding

        self.stats['total_analyzed'] += 1
        if padding > 0:
            self.stats['with_padding'] += 1
        else:
            self.stats['without_padding'] += 1

        self.stats['max_padding'] = max(self.stats['max_padding'], padding)

        return enriched

    def analyze_all_texts(self, texts: List[dict]) -> List[dict]:
        """
        Analyse une liste de textes.

        Args:
            texts: Liste de text entries

        Returns:
            List[dict]: Textes enrichis avec padding
        """
        enriched_texts = []

        for text in texts:
            enriched = self.analyze_text(text)
            enriched_texts.append(enriched)

        # Calculer moyenne
        if self.stats['total_analyzed'] > 0:
            total_padding = sum(t['padding_available'] for t in enriched_texts)
            self.stats['avg_padding'] = total_padding / self.stats['total_analyzed']

        return enriched_texts

    def generate_report(self) -> dict:
        """Génère un rapport statistique."""
        return {
            'statistics': self.stats,
            'padding_distribution': self._calculate_distribution(),
            'recommendations': self._generate_recommendations()
        }

    def _calculate_distribution(self) -> dict:
        """Calcule distribution des padding."""
        # À implémenter
        pass

    def _generate_recommendations(self) -> List[str]:
        """Génère des recommandations."""
        recommendations = []

        if self.stats['avg_padding'] >= 3:
            recommendations.append(
                f"Padding moyen élevé ({self.stats['avg_padding']:.1f} bytes). "
                "Débordements de 1-3 bytes seront gérés automatiquement."
            )

        return recommendations
```

---

## Conventions de Code

### Imports
```python
# Standard library
import sys
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Third-party
import pandas as pd

# Local
from src.core.rom_reader import ROMReader
from src.core.text_encoder import PokemonEncoder
from src.core.padding_detector import PaddingDetector
```

### Error Handling
```python
class ROMError(Exception):
    """Erreur liée à la manipulation ROM."""
    pass

class EncodingError(Exception):
    """Erreur d'encodage/décodage."""
    pass

# Usage
try:
    rom = ROMReader('input/roms/englishrom.gba')
    rom.load()
except FileNotFoundError:
    print("❌ ROM introuvable")
    sys.exit(1)
except ROMError as e:
    print(f"❌ Erreur ROM: {e}")
    sys.exit(1)
```

### Logging
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

logger.info("Chargement ROM...")
logger.warning("Padding insuffisant")
logger.error("Échec d'écriture")
```

---

## Tests

### Structure
```python
# tests/test_core/test_rom_reader.py
import pytest
from src.core.rom_reader import ROMReader

class TestROMReader:
    @pytest.fixture
    def rom_reader(self):
        return ROMReader('tests/fixtures/sample_rom.gba')

    def test_load(self, rom_reader):
        rom_reader.load()
        assert rom_reader.rom_size > 0

    def test_read_pointer(self, rom_reader):
        rom_reader.load()
        ptr = rom_reader.read_pointer(0x100)
        assert ptr is not None or ptr is None  # Test structure

    def test_invalid_offset(self, rom_reader):
        rom_reader.load()
        with pytest.raises(ValueError):
            rom_reader.read_bytes(999999999, 100)
```

---

## Prochaines Étapes

1. ✅ Créer structure `src/core/`
2. ⏳ Implémenter `ROMReader`
3. ⏳ Implémenter `PaddingDetector` ⭐
4. ⏳ Créer `06_detect_padding.py` ⭐
5. ⏳ Créer `07_reinsert_smart.py` ⭐
6. ⏳ Tests unitaires

Voir `docs/05_TASKS_TECHNICAL.md` pour détails.
