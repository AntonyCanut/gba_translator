# Audit Projet & Suite de Tests E2E

## 1. Vue d'ensemble

Le projet **GBA Translator** est un toolkit Python pour traduire des ROMs GBA Pokemon (CFRU/BPRE01). Il gere l'encodage proprietaire Gen III (Pokemon charmap), la gestion des pointeurs 32-bit, l'allocation d'espace libre, et la reinsertion de textes traduits.

### Stack
- **Langage**: Python 3.11+
- **Tests**: pytest (unittest-style existant + nouveaux E2E pytest)
- **Dependance externe**: aucune (stdlib uniquement)

---

## 2. Architecture

```
src/
  core/           Modules fondamentaux
    rom_reader.py         Lecture/ecriture ROM GBA (bytearray)
    text_codec.py         Encodeur/decodeur Pokemon charmap
    text_reinserter.py    Reinsertion intelligente + allocation espace libre
    text_validator.py     Validation et filtrage des textes
    text_converter.py     Conversion entre formats
    padding_detector.py   Detection du padding dans la ROM
  extractors/     Extraction de textes
    pointer_text_extractor.py   Extraction basee sur les tables de pointeurs
    validate_extraction.py      Validation des extractions
  validators/     Validation
    text_range_validator.py     Validation des plages de texte
  translators/    Scripts de traduction (historique, 27 scripts)
  analyzers/      Outils d'analyse
  commands/       Commandes CLI
  utils/          Utilitaires
scripts/          Scripts applicatifs
tests/            Tests unitaires existants + E2E
input/roms/       ROMs source (EN, ES)
output/
  roms/           ROMs generees (FR)
  translation/    Fichiers de traduction (JSON, CSV)
```

### Modules cles

| Module | Role | API principale |
|--------|------|---------------|
| **ROMReader** | Acces ROM GBA | `load()`, `read_bytes()`, `read_pointer()`, `write_bytes()`, `save()` |
| **TextEncoder** | UTF-8 -> bytes Pokemon | `encode_pokemon(text)`, `encode_ascii(text)` |
| **TextDecoder** | bytes Pokemon -> UTF-8 | `decode_pokemon(data)`, `decode_ascii(data)` |
| **SmartReinserter** | Injection textes + relocation | `reinsert_text(dict)`, `reinsert_all(list)`, `get_report()` |
| **FreeSpaceAllocator** | Gestion espace libre | `allocate(size)` -> offset ou None |
| **ROMTranslationManager** | Pipeline haut niveau | `apply_translations(list)`, `save_rom(path)` |
| **PointerTextExtractor** | Extraction par pointeurs | `detect_tables()`, extraction textes |

---

## 3. Pipeline de Traduction

```
1. EXTRACT          ROM EN -> tables de pointeurs -> textes decodes
                    |-- PointerTextExtractor.detect_tables()
                    |-- Decodage Pokemon charmap
                    `-- Export JSON/CSV

2. TRANSLATE        Template -> fichier traduit (manuel / LLM)
                    Format: {offset, original_text, translation, encoding, ...}

3. REINSERTION      ROM EN + traductions -> ROM FR
                    |-- SmartReinserter pour chaque entree
                    |-- In-place si taille <= original + padding
                    |-- Relocation via FreeSpaceAllocator si trop long
                    |-- Mise a jour pointeurs si relocation
                    `-- Sauvegarde ROM modifiee

4. VALIDATION       Verification post-injection
                    |-- Textes lisibles aux offsets
                    |-- Pointeurs valides
                    |-- Structure ROM preservee
```

---

## 4. Donnees techniques

| Parametre | Valeur |
|-----------|--------|
| ROM size | 32 MB |
| Game code | BPRE (offset 0xAC) |
| Encoding | Pokemon charmap proprietaire |
| Terminateur de chaine | 0xFF (Pokemon), 0x00 (ASCII) |
| Newline | 0xFE |
| Pointeurs | 32-bit little-endian, base 0x08000000 |
| Caracteres francais natifs | a c e a i u (6 chars + 3 majuscules) |
| Caracteres francais aliases | e o u e i o u (normalises vers base) |
| Caracteres espagnols | a e i o u n (6 chars) |
| Total traductions | ~19,000 entrees (fichier 2026-01-16) |
| Entrees traduites | ~18,966 |

---

## 5. Suite de Tests Existante

### Tests unitaires (12 fichiers)

| Fichier | Couverture |
|---------|-----------|
| `test_text_codec.py` | Round-trip Pokemon, newlines, accents FR, aliases |
| `test_reinserter.py` | Raw bytes, max_length, reinsertion basique |
| `test_reinserter_relocation.py` | Relocation + mise a jour pointeurs |
| `test_pointer_text_extractor.py` | Detection tables, extraction textes |
| `test_text_range_validator.py` | Validation plages de texte |
| `test_control_placeholders.py` | Codes de controle (hex tokens) |
| `test_font_patch.py` | Patch de font pour caracteres FR |
| `test_regression_texts.py` | Tests de regression textes specifiques |
| `test_dynamic_translation_insertion.py` | Insertion dynamique |
| `test_inline_text_copy.py` | Copie inline de textes |
| `test_localized_lz77_blocks.py` | Blocs LZ77 localises |
| `test_builder_pointer_copy.py` | Copie de pointeurs par le builder |

---

## 6. Nouveaux Tests E2E Ajoutes

### 6.1 `tests/e2e/conftest.py`
Fixtures partagees:
- `en_rom_path`, `es_rom_path`, `fr_rom_path` (skip si absent)
- `translation_ready_path`, `french_texts_path`
- `en_rom_data` (ROMReader charge)
- `translation_entries` (liste des entrees)
- `injected_rom` (module-scoped: injection 500 entrees, retourne path + report)

### 6.2 `test_encoding_stress.py` (10 classes, 20+ tests)
- Round-trip accents francais (6 caracteres natifs)
- Round-trip accents espagnols (6 caracteres)
- Aliases (oe, e, o, u -> formes simplifiees)
- Codes de controle (newline 0xFE, hex tokens)
- Cas limites (vide, 1 char, 200 chars, terminateur au milieu, bytes inconnus)
- Bulk encoding (toutes les entrees de traduction)
- Round-trip bulk (1000 premieres entrees)

### 6.3 `test_rom_integrity.py` (5 classes, 10+ tests)
- Header GBA valide (taille, game code, entry point, titre)
- Region code preservee (<1% diff)
- Statistiques injection (succes > 0, taux echec < 10%)
- Pointeurs non corrompus dans la region texte
- ROM FR existante : structure valide, diff raisonnable vs EN

### 6.4 `test_translation_quality.py` (5 classes, 8+ tests)
- Couverture traduction (>80% des entrees)
- Encodabilite (toutes les traductions encodables)
- Round-trip stabilite
- Indicateurs francais (accents, patterns linguistiques)
- Preservation codes de controle (tokens FD)
- Contraintes de longueur (too_long < 10%)

### 6.5 `test_reinsertion_pipeline.py` (4 classes, 10+ tests)
- Injection sample (3 entrees, verification octets)
- Injection avec padding
- Skip si trop long (sans relocation)
- Relocation vers espace libre + mise a jour pointeur
- FreeSpaceAllocator (basique, multiple, echec, ROM reelle)
- Determinisme (2 injections identiques = meme resultat)
- Texte decodable aux offsets injectes

---

## 7. Commandes de Test

```bash
# Tous les tests existants
python3 -m pytest tests/ -v

# Tests E2E seulement
python3 -m pytest tests/e2e/ -v

# Tests E2E par fichier
python3 -m pytest tests/e2e/test_encoding_stress.py -v
python3 -m pytest tests/e2e/test_rom_integrity.py -v
python3 -m pytest tests/e2e/test_translation_quality.py -v
python3 -m pytest tests/e2e/test_reinsertion_pipeline.py -v

# Tests sans ROM (encodage seulement)
python3 -m pytest tests/e2e/test_encoding_stress.py -v -k "not Bulk"
```

---

## 8. Dependances pour les Tests

| Dependance | Requis pour | Disponibilite |
|-----------|-------------|--------------|
| pytest | Tous les tests E2E | `pip install pytest` |
| englishrom.gba | Tests injection, integrite | `input/roms/` |
| spanishrom.gba | Tests comparaison | `input/roms/` |
| GenedRom-fr.gba | Tests ROM FR existante | `output/roms/` |
| translation_ready.json | Tests qualite, injection | `output/translation/` |
| french_texts.json | Tests couverture FR | `output/translation/` |
