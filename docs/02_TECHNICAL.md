# Documentation Technique - Système de Traduction GBA ROM

## Architecture du système

### Vue d'ensemble

Le système est composé de 6 scripts principaux qui permettent d'extraire, comparer, analyser et traduire les textes d'une ROM GBA avec support de relocalisation automatique.

```
ROM GBA (32 MB)
    ↓
[extract_text.py] → JSON (tous les textes)
    ↓
[compare_texts.py] → JSON (différences)
    ↓
[extract_english_diff.py] → JSON filtré (95.8% réduction)
    ↓
[translate_rom.py] → ROM traduite + rapport
```

## Structure d'une ROM GBA

### Adressage mémoire

Les ROMs GBA sont mappées à l'adresse de base **0x08000000** dans la mémoire de la Game Boy Advance.

Exemple :
- Offset ROM : `0x0018D42A`
- Adresse mémoire : `0x0808D42A` (0x08000000 + 0x0018D42A)

### Pointeurs

Les pointeurs dans la ROM sont des valeurs 32-bit little-endian qui référencent des adresses mémoire.

Exemple de pointeur pointant vers 0x0018D42A :
```
Bytes: 2A D4 18 08
Value: 0x0818D42A
```

### Espace libre

Pokemon FireRed contient plusieurs blocs d'espace libre (remplis de 0xFF) :

| Offset | Taille | Description |
|--------|--------|-------------|
| 0x015FBC90 | 336 KB | Bloc principal (utilisé pour relocalisation) |
| 0x01FE6C64 | 100 KB | Bloc secondaire |
| 0x001B56E6 | 22 KB | Bloc tertiaire |

**Total : ~576 KB d'espace libre**

## Encodage des textes

### ASCII Standard

Utilisé pour les textes techniques, noms de fichiers, etc.

```python
text = "Hello"
encoded = b'Hello'
```

### Pokemon Encoding

Encodage propriétaire utilisé pour les dialogues et textes du jeu.

#### Table de caractères (partielle)

| Code | Caractère | Code | Caractère |
|------|-----------|------|-----------|
| 0x00 | espace | 0xBB-0xD4 | A-Z |
| 0xD5-0xEE | a-z | 0xA1-0xAA | 0-9 |
| 0xAB | ! | 0xAC | ? |
| 0xAD | . | 0xAE | - |
| 0xB8 | , | 0xB4 | ' |
| 0xFE | newline | 0xFF | fin de chaîne |

#### Exemple d'encodage

Texte : `"Take care now!"`

```
Bytes: CE D5 DF D9 00 D7 D5 E6 D9 00 E2 E3 EB AB FF
       T  a  k  e  _  c  a  r  e  _  n  o  w  !  END
```

## Scripts et leur fonctionnement

### 1. extract_text.py

**Objectif** : Extraire tous les textes d'une ROM GBA

**Méthodes d'extraction** :
1. **ASCII** : Recherche de séquences de caractères ASCII printables (0x20-0x7E)
2. **Pokemon** : Recherche de séquences utilisant la table Pokemon terminées par 0xFF

**Algorithme** :
```python
for offset in range(rom_size):
    if is_pokemon_char(byte):
        text = decode_pokemon_string(offset)
        if valid(text):
            save_text(offset, text, 'pokemon')
    elif is_ascii(byte):
        text = decode_ascii_string(offset)
        if valid(text):
            save_text(offset, text, 'ascii')
```

**Performance** :
- ROM 32 MB scannée en ~30 secondes
- ~340,000 textes extraits

### 2. compare_texts.py

**Objectif** : Comparer les textes de deux ROMs et identifier les différences

**Types de différences détectées** :
- **modified** : Texte existant mais différent
- **only_in_rom1** : Texte uniquement dans ROM 1
- **only_in_rom2** : Texte uniquement dans ROM 2

**Calcul de similarité** :
```python
from difflib import SequenceMatcher
similarity = SequenceMatcher(None, text1, text2).ratio()
```

### 3. extract_english_diff.py

**Objectif** : Filtrer uniquement les textes anglais aux offsets où il y a des différences

**Résultat** :
- 339,821 textes originaux → **14,436 textes filtrés**
- **Réduction de 95.8%** du volume à traduire

### 4. analyze_rom_structure.py

**Objectif** : Analyser la structure de la ROM pour comprendre l'organisation des données

**Fonctionnalités** :
1. **Informations ROM** : Titre, code jeu, taille
2. **Détection d'espace libre** : Recherche de blocs 0xFF
3. **Détection de tables de pointeurs** : Séquences de pointeurs valides
4. **Analyse de région** : Hex dump et recherche de pointeurs vers un offset

**Exemple d'utilisation** :
```bash
# Analyser un texte spécifique
python3 analyze_rom_structure.py englishrom.gba 0x0018D42A
```

### 5. reinsert_text.py (Basique)

**Objectif** : Réinsérer des textes modifiés dans la ROM (taille fixe uniquement)

**Algorithme** :
```python
for entry in texts:
    encoded = encode_text(entry['text'], entry['encoding'])

    if len(encoded) > entry['length']:
        # TRONQUER
        encoded = encoded[:entry['length']]

    rom_data[entry['offset']:entry['offset']+len(encoded)] = encoded

    # Padding si plus court
    if len(encoded) < entry['length']:
        pad_with_zeros(entry['offset'] + len(encoded),
                      entry['length'] - len(encoded))
```

**Limitations** :
- ❌ Ne supporte pas les textes plus longs
- ❌ Pas de relocalisation
- ✅ Simple et rapide

### 6. translate_rom.py (Avancé) 🚀

**Objectif** : Traduire la ROM avec support de textes plus longs via relocalisation

**Algorithme de relocalisation** :

```python
def translate_text(entry):
    encoded = encode_text(entry['text'], entry['encoding'])

    if len(encoded) <= entry['length']:
        # Cas 1: Texte plus court ou égal → écriture directe
        write_in_place(entry['offset'], encoded)
        return

    # Cas 2: Texte plus long → relocalisation nécessaire

    # Étape 1: Trouver tous les pointeurs vers ce texte
    pointers = find_all_pointers(entry['offset'])

    if not pointers:
        # Pas de pointeurs trouvés → écriture directe (tronquée)
        write_in_place(entry['offset'], encoded[:entry['length']])
        return

    # Étape 2: Écrire le nouveau texte dans l'espace libre
    new_offset = free_space_ptr
    write_to_free_space(new_offset, encoded)

    # Étape 3: Mettre à jour tous les pointeurs
    for ptr_location in pointers:
        update_pointer(ptr_location, new_offset)

    # Étape 4: Effacer l'ancien emplacement
    clear_original(entry['offset'], entry['length'])

    # Étape 5: Avancer le pointeur d'espace libre
    free_space_ptr += len(encoded)
```

**Recherche de pointeurs** :

```python
def find_all_pointers(target_offset):
    """
    Recherche tous les pointeurs 32-bit little-endian
    qui pointent vers target_offset.
    """
    GBA_ROM_BASE = 0x08000000
    target_pointer = GBA_ROM_BASE + target_offset
    target_bytes = struct.pack('<I', target_pointer)

    pointers = []
    for i in range(0, rom_size - 3, 4):  # Alignement 4 bytes
        if rom_data[i:i+4] == target_bytes:
            pointers.append(i)

    return pointers
```

**Performance** :
- Traitement de 14,436 textes en ~45 secondes
- Relocalisation automatique des textes trop longs
- Génération d'un rapport détaillé

## Format des fichiers JSON

### extracted_texts/englishrom_texts.json

```json
{
  "rom_name": "englishrom.gba",
  "rom_size": 33554432,
  "text_count": 339821,
  "texts": [
    {
      "offset": 1625130,
      "text": "Take care now!",
      "length": 14,
      "encoding": "pokemon"
    }
  ]
}
```

### differences/differences.json

```json
{
  "rom1": "englishrom.gba",
  "rom2": "spanishrom.gba",
  "total_differences": 25183,
  "differences": [
    {
      "offset": 1625130,
      "type": "modified",
      "similarity": 0.42,
      "rom1_text": "Take care now!",
      "rom2_text": "¡Cuídate!",
      "rom1_encoding": "pokemon",
      "rom2_encoding": "pokemon"
    }
  ]
}
```

### *.relocation_report.json

```json
{
  "relocated_count": 42,
  "pointers_updated": 127,
  "relocated_texts": [
    {
      "original_offset": 1625130,
      "new_offset": 23166096,
      "text": "Take care now, my friend!",
      "size": 25,
      "pointers_updated": 3
    }
  ],
  "pointer_updates": [
    {
      "pointer_at": "0x001A8C40",
      "old_target": "0x0018D42A",
      "new_target": "0x0161BC90"
    }
  ]
}
```

## Cas d'usage et patterns

### Cas 1 : Traduction simple (mêmes tailles)

```bash
make extract
# Éditer extracted_texts/englishrom_texts.json
make reinsert-en
```

**Résultat** : ROM modifiée avec textes traduits

### Cas 2 : Traduction avec textes plus longs

```bash
make all
# Éditer differences/englishrom_diff_only.json
make translate-en
```

**Résultat** : ROM traduite avec relocalisations automatiques

### Cas 3 : Analyse d'un texte spécifique

```bash
# Trouver l'offset du texte
grep -r "Take care now" extracted_texts/

# Analyser le texte
python3 analyze_rom_structure.py englishrom.gba 0x0018D42A
```

**Résultat** : Hex dump, pointeurs, contexte

## Limitations et considérations

### Limitations connues

1. **Textes sans pointeurs** : Les textes dans des arrays séquentiels n'ont pas de pointeurs directs. La relocalisation ne fonctionnera pas pour ces textes.

2. **Tables de pointeurs** : Si un texte fait partie d'une table de pointeurs, tous les pointeurs de la table doivent être mis à jour de manière cohérente.

3. **Encodage incomplet** : La table Pokemon peut être incomplète selon la version du jeu. Des caractères spéciaux peuvent manquer.

4. **Espace limité** : Malgré 576 KB d'espace libre, des ROMs très modifiées peuvent manquer d'espace.

### Bonnes pratiques

1. **Toujours tester sur émulateur** après modification
2. **Conserver les backups** (.gba.bak)
3. **Vérifier le rapport de relocalisation** pour comprendre les modifications
4. **Utiliser la méthode basique** quand possible (plus rapide, plus sûre)
5. **Analyser la ROM** avant de faire des modifications importantes

## Développements futurs possibles

### Améliorations potentielles

1. **Détection de tables de textes** : Identifier automatiquement les arrays de textes séquentiels
2. **Édition graphique** : Interface GUI pour éditer les textes
3. **Support multi-langue** : Insérer plusieurs langues dans une même ROM
4. **Compression de textes** : Implémenter une compression pour économiser l'espace
5. **Validation automatique** : Vérifier que la ROM modifiée fonctionne
6. **Import/Export CSV** : Format plus facile pour les traducteurs
7. **Support d'autres jeux GBA** : Adapter les tables de caractères

### Extensions possibles

```python
# Table de caractères étendue
EXTENDED_POKEMON_TABLE = {
    # Caractères accentués français
    0xF9: 'é', 0xFA: 'è', 0xFB: 'à',
    # Caractères espagnols
    0xFC: 'ñ', 0xFD: '¿', 0xFE: '¡',
    # etc.
}
```

## Conclusion

Ce système fournit une solution complète et robuste pour :
- ✅ Extraire tous les textes d'une ROM GBA
- ✅ Comparer deux versions (anglais/espagnol)
- ✅ Traduire avec support de textes plus longs
- ✅ Relocaliser automatiquement dans l'espace libre
- ✅ Mettre à jour tous les pointeurs
- ✅ Générer des rapports détaillés

Le code est modulaire, documenté et facile à étendre pour d'autres jeux GBA.
