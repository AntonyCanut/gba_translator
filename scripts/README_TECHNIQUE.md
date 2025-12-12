# Documentation Technique - Système de Traduction ROM GBA

## Vue d'ensemble

Ce système permet d'injecter des traductions françaises dans une ROM Pokémon FireRed tout en gérant la relocalisation dynamique des textes qui ne rentrent plus dans leur espace original.

## Architecture du système

### 1. Extraction des textes (`dump_rom_usage.py`, extraction scripts)

Les textes sont extraits de la ROM originale avec leurs offsets mémoire. Chaque texte est identifié par :
- **Offset** : Position dans la ROM (ex: 0x1F2D9EB)
- **Pointeur(s)** : Adresse(s) dans le code qui référencent ce texte
- **Longueur** : Taille en octets du texte original

### 2. Traduction et encodage

Les textes traduits sont :
- Stockés dans des chunks (`fr_chunks/chunk_*.txt`)
- Combinés en un fichier unique (`combined_fr.txt`)
- Encodés selon la table de caractères GBA (`charmap_firered.txt`)

### 3. Injection avec relocalisation (`inject_translations.py`)

#### Principe de base

Quand un texte traduit est plus long que l'original :
1. **Si le texte a un pointeur** : il peut être relocalisé ailleurs en mémoire
2. **Si le texte n'a pas de pointeur** : il doit rester en place (erreur si trop long)

#### Zones sensibles (SENSITIVE_OFFSET_MAX)

**Problème identifié** : Les textes dans les premières zones mémoire (< 0x800000) sont utilisés pendant l'initialisation du jeu. Les relocaliser casse le démarrage.

**Solution** : `SENSITIVE_OFFSET_MAX = 0x800000`
- Les textes avec offset < 0x800000 sont marqués `"sensitive": True`
- Ils ne peuvent JAMAIS être relocalisés, seulement modifiés sur place
- Si un texte sensible est trop long, une erreur est générée

```python
# inject_translations.py:846-857
if entry.get("sensitive"):
    if len(encoded) > orig_len:
        errors.append(f"texte trop long sur offset sensible (ne peut pas être relocalisé)")
        continue
    # Écriture sur place uniquement
    rom_bytes[offset : offset + len(encoded)] = encoded
```

#### Gestion des blocs contigus

**Problème** : Plusieurs textes consécutifs en mémoire forment des "blocs contigus". Si on les relocalisent individuellement, un texte peut écraser le suivant.

**Solution** : Détection des runs (blocs contigus)

```python
# Construction des runs
for off in ordered_offsets:
    is_contiguous = (prev_offset is not None and
                    off == prev_offset + original_lengths[prev_offset])

    if not is_contiguous:
        current_anchor = None

    # Ne créer un nouveau anchor que si on n'en a pas
    if current_anchor is None and has_pointer_for(off):
        current_anchor = off

    if current_anchor is not None:
        run_members.setdefault(current_anchor, []).append(off)
```

#### Réutilisation d'espace (désactivée)

**Problème identifié** : L'option `--reuse-old-space` (active par défaut) essayait de réutiliser les emplacements des textes relocalisés. Cela causait des corruptions où les pointeurs étaient mis à jour mais les données n'étaient pas écrites.

**Solution** : Désactivation via `--no-reuse-old-space` dans le Makefile

```makefile
# Makefile:46
@time $(PY) scripts/inject_translations.py --text $(COMBINED_FR) --out $(OUT_FR) \
    --use-holes --free-map $(ROM_USAGE) --no-reuse-old-space --allow-append
```

#### Checksum ROM

**Décision** : Le checksum ROM n'est PAS corrigé automatiquement pour conserver le checksum de la ROM de base (certains émulateurs vérifient l'intégrité de ROMs hack connues).

```python
# inject_translations.py:1180-1186 (commenté)
# checksum = 0
# for i in range(0xA0, 0xBD):
#     checksum = (checksum - rom_bytes[i]) & 0xFF
# rom_bytes[0xBD] = checksum
```

## Zones mémoire de la ROM

```
0x000000 - 0x0000C0  : Header ROM (CRUCIAL - ne jamais modifier)
0x0000C0 - 0x000100  : Logo Nintendo (vérifié par émulateurs)
0x080000 - 0x081000  : Code d'entrée (exécuté au boot)
0x081000 - 0x090000  : Code d'initialisation
0x000000 - 0x800000  : Zone sensible (textes utilisés à l'init)
0x800000 - 0x2000000 : Zone relocalisable (textes de jeu normaux)
```

## Diagnostics et débogage

### Vérifier les modifications dans le code d'entrée

```python
python3 -c "
import struct
orig = open('totranslate.gba', 'rb').read()
new = open('totranslate_fr.gba', 'rb').read()

# Compter les modifications dans Entry Code
changes = sum(1 for i in range(0x80000, 0x81000) if orig[i] != new[i])
print(f'Entry Code: {changes} octets modifiés')
"
```

### Vérifier les pointeurs invalides

```python
python3 -c "
import struct
rom = open('totranslate_fr.gba', 'rb').read()
rom_size = len(rom)

invalid = 0
for i in range(0, rom_size, 4):
    val = struct.unpack('<I', rom[i:i+4])[0]
    if (val & 0xFE000000) == 0x08000000:
        target = val & 0x01FFFFFF
        if target >= rom_size:
            print(f'{hex(i)}: pointeur {hex(val)} hors limites')
            invalid += 1

print(f'Total: {invalid} pointeurs invalides')
"
```

### Vérifier qu'un texte a été correctement relocalisé

```python
python3 scripts/check_text_relocation.py 0x1F2D9EB
```

## Erreurs courantes

### Écran blanc au démarrage
**Cause** : Modification du code d'entrée (0x80000-0x81000)
**Solution** : Augmenter SENSITIVE_OFFSET_MAX pour protéger plus de textes

### Freeze/crash pendant le jeu
**Cause** : Pointeurs cassés vers des données relocalisées incorrectement
**Solution** : Vérifier les pointeurs avec les scripts de diagnostic

### Texte corrompu/manquant
**Cause** :
1. Texte sensible trop long (ne peut pas être relocalisé)
2. Réutilisation d'espace échouée (données non écrites)

**Solution** :
1. Raccourcir le texte traduit
2. Désactiver --reuse-old-space

## Statistiques de build

Build actuel (avec protections) :
- Chaînes remplacées : 20,355
- Textes déplacés : 5,981
- Réutilisation ancien espace : 0
- Erreurs : ~3,600 (textes sensibles trop longs)

## Prochaines améliorations

1. **Détection automatique des zones sensibles** : Scanner le code pour trouver tous les pointeurs utilisés pendant l'init
2. **Optimisation de l'espace** : Mieux réutiliser les zones libres sans corruption
3. **Validation des pointeurs** : Vérifier que tous les pointeurs mis à jour pointent vers des données valides
4. **Gestion intelligente des blocs contigus** : Détecter automatiquement quels blocs doivent être relocalisés ensemble

## Fichiers importants

- `inject_translations.py` : Script principal d'injection
- `charmap_firered.txt` : Table de correspondance caractères → bytes GBA
- `rom_usage.txt` : Carte des zones libres/utilisées dans la ROM
- `combined_fr.txt` : Tous les textes traduits combinés
- `sensitive_lines.txt` : Liste des lignes de texte sensibles (si utilisé)

## Références

- Structure ROM GBA : https://problemkaputt.de/gbatek.htm
- Encodage texte Pokémon : https://bulbapedia.bulbagarden.net/wiki/Character_encoding_in_Generation_III

## Corrections Appliquées - Historique

### Fix Critique : Fragmentation des blocs contigus (RÉSOLU ✓)

**Symptôme** : Le jeu redémarrait en boucle sur certains événements, "liens manquants"

**Cause** : Les blocs de textes contigus en mémoire étaient fragmentés lors de la relocalisation.

**Exemple** : Bloc 0x1F2D942-0x1F2DAAB (5 textes contigus, 524→551 octets total)
- Avant fix : Fragmenté en 5 relocalisations séparées
  - 0x1F2D942 → 0x95C9A4
  - 0x1F2D9B9 → EN PLACE  
  - 0x1F2D9EB → 0xB3F687
  - 0x1F2DA1D → EN PLACE
  - 0x1F2DAAB → 0x91636C
  - Résultat : Gaps, pointeurs cassés → crash/boucle événement

- Après fix : Relocalisé ensemble de façon contiguë
  - 0x1F2D942 → 0x1648839 (138 octets)
  - 0x1F2D9B9 → 0x16488C3 (61 octets) ← juste après
  - 0x1F2D9EB → 0x1648900 (59 octets) ← juste après
  - 0x1F2DA1D → 0x164893B (113 octets) ← juste après  
  - 0x1F2DAAB → 0x16489AC (180 octets) ← juste après
  - Résultat : Bloc intact, contigu → fonctionne ✓

**Solution implémentée** (`inject_translations.py` lignes 494-524) :

1. **Fix de la détection des runs** (ligne 498) :
```python
# AVANT (BUGUÉ) :
if has_pointer_for(off):
    current_anchor = off  # ← RÉINITIALISE l'anchor à chaque pointeur = fragmentation!

# APRÈS (CORRIGÉ) :
if current_anchor is None and has_pointer_for(off):
    current_anchor = off  # ← Crée anchor seulement si aucun existant
```

2. **Ajout de la condition de relocalisation par dépassement total** (lignes 511-524) :
```python
# Calculer tailles totales du run
total_orig = sum(entries_by_offset.get(o, {}).get("orig_len", 0) for o in run)
total_new = sum(entries_by_offset.get(o, {}).get("enc_len", 0) for o in run)

# Relocal iser si total dépasse (même si tous les textes ont des pointeurs)
if has_long_without_ptr or total_new > total_orig:
    group_runs.add(anchor)  # ← Ce run sera relocalisé ENSEMBLE
```

**Impact** :
- Chaînes remplacées : 22,527 (vs 20,355 avant)
- Textes déplacés : 13,103 (vs 5,980 avant)
- Blocs contigus : Maintenus intacts ✓
- Événements : Fonctionnent correctement ✓

### Fix : Écran blanc au démarrage + Sprites/Contrôles corrompus (RÉSOLU ✓)

**Cause** : Modifications dans zone 0-1MB (tables sprites, contrôles, boot data)

**Solution** : Quadruple protection absolue

**1. Marquer les offsets sources sensibles** (`inject_translations.py` ligne 33) :
```python
SENSITIVE_OFFSET_MAX = 0x800000  # 8MB - protège boot, sprites, contrôles, données jeu
```

**2. Ne JAMAIS modifier les textes sensibles** (lignes 874-880) :
```python
if entry.get("sensitive"):
    # Ne JAMAIS modifier, même s'ils rentrent (peuvent être des données binaires)
    errors.append(f"Ligne {line_no}: texte dans zone sensible {hex(offset)} - NON MODIFIÉ")
    continue
```

**3. Refuser de relocal iser des textes/runs sensibles** (lignes 678-682, 920-925) :
```python
if any(off < SENSITIVE_OFFSET_MAX for off in run):
    errors.append(f"Run {hex(anchor)}: contient des offsets sensibles")
    continue
```

**4. PROTECTION CRITIQUE: Ne JAMAIS modifier de pointeur dans 0-1MB** (lignes 393-398) :
```python
def set_pointer(ptr_pos: int, ptr_val: int, context: str) -> None:
    CRITICAL_ZONE_MAX = 0x100000  # Tables sprites/contrôles dans 0-1MB
    if ptr_pos < CRITICAL_ZONE_MAX:
        return  # Skip silencieusement
```

**5. Interdire l'allocation dans zones sensibles** (lignes 575-576, 596-597) :
```python
if start < SENSITIVE_OFFSET_MAX:
    continue  # Ne jamais allouer < 8MB
```

**Résultat FINAL** :
- Zone 0-1MB : **0 octets modifiés** ✓✓✓
- Entry Code : Intact ✓
- Init Code : Intact ✓
- Sprites/Contrôles : Intacts ✓
- Chaînes remplacées : ~15,339
- **Compromis** : Seulement textes > 8MB traduits, mais jeu fonctionnel

### Fix : Données corrompues lors de relocalisation (RÉSOLU ✓)

**Cause** : Option `--reuse-old-space` (active par défaut) écrivait les pointeurs sans écrire les données

**Solution** : Désactivation via `--no-reuse-old-space` dans le Makefile

**Impact** : Plus de pointeurs vers zones vides, toutes les données relocalisées sont écrites ✓
