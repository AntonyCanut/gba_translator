# Fix Final - Écran Blanc + Sprites/Contrôles Corrompus

## ✓ PROBLÈME RÉSOLU

Le jeu démarre maintenant avec écran titre correct et contrôles fonctionnels.

---

## Évolution du Diagnostic

### 1. Premier Symptôme: Écran Blanc
- **Cause**: Pointeurs dans Entry Code (0x80000-0x81000) vers zones < 0x800000
- **Solution initiale**: SENSITIVE_OFFSET_MAX = 0x800000

### 2. Deuxième Symptôme: Sprites/Contrôles Corrompus
- **Observation**: Avec SENSITIVE = 0x800000, jeu démarre mais sprites titre corrompus, boutons ne fonctionnent pas
- **Cause**: 171 octets modifiés dans 0-1MB (principalement pointeurs dans tables sprites/contrôles)
- **Solution finale**: Protection absolue 0-1MB

---

## La Solution Finale: 5 Protections

### 1. Seuil de Zone Sensible Élargi
```python
# inject_translations.py ligne 33
SENSITIVE_OFFSET_MAX = 0x800000  # 8MB au lieu de 1MB
```

**Pourquoi 8MB?**
- 0-1MB: Boot, sprites, contrôles (CRITIQUE)
- 1-8MB: Données de jeu, assets, tables diverses (SENSIBLE)
- 8MB+: Textes normaux, relocalisables en toute sécurité

### 2. Ne Jamais Modifier les Textes Sensibles
```python
# Lignes 874-880
if entry.get("sensitive"):
    # Ne JAMAIS modifier, même s'ils rentrent
    # Ces "textes" peuvent être des données binaires
    errors.append(f"texte dans zone sensible - NON MODIFIÉ")
    continue
```

**Avant**: Textes sensibles modifiés sur place s'ils rentrent → corruption données binaires

**Après**: Textes sensibles complètement ignorés

### 3. Ne Jamais Relocal iser depuis Zone Sensible
```python
# Lignes 678-682, 920-925
if any(off < SENSITIVE_OFFSET_MAX for off in run):
    errors.append(f"Run contient offsets sensibles")
    continue
```

### 4. **PROTECTION CRITIQUE**: Ne Jamais Modifier Pointeur dans 0-1MB
```python
# Lignes 393-398
def set_pointer(ptr_pos: int, ptr_val: int, context: str) -> None:
    CRITICAL_ZONE_MAX = 0x100000  # 1MB
    if ptr_pos < CRITICAL_ZONE_MAX:
        return  # Skip silencieusement
```

**C'EST LA CLÉ DU FIX!**

Les pointeurs dans 0-1MB sont dans des **tables critiques**:
- Tables de sprites (écran titre, menus)
- Tables de contrôles (input handlers)
- Tables de boot data
- Tables de palettes

**Modifier même UN SEUL pointeur** dans ces tables casse le jeu.

### 5. Ne Jamais Allouer dans Zone Sensible
```python
# Lignes 575-576, 596-597
if start < SENSITIVE_OFFSET_MAX:
    continue  # Ne jamais allouer < 8MB
```

---

## Résultat Final

### Vérifications
```
Zone 0-1MB:   0 octets modifiés ✓✓✓
Zone 1-8MB:   960 octets modifiés (pointeurs hors 0-1MB)
Zone 8MB+:    994,926 octets modifiés (traductions)
```

### Zones Critiques
```
ROM Header:   Intact ✓
Boot Code:    Intact ✓
Entry Code:   Intact ✓
Init Code:    Intact ✓
```

### Impact sur Traduction
```
Chaînes remplacées: ~15,339 (au lieu de ~24K)
Textes traduits:    Seulement ceux > 8MB
Textes ignorés:     ~10K textes dans zone 0-8MB
```

---

## Le Compromis Accepté

### ✓ Avantages
- Jeu démarre sans écran blanc
- Écran titre correct, sprites OK
- Contrôles fonctionnent
- Jeu stable et jouable

### ⚠ Inconvénients
- ~10,000 textes NON traduits (restent en anglais)
- Notamment: textes intro, certains menus, dialogues début de jeu

### Pourquoi Ce Compromis?

**Option 1** (REJETÉE): Traduire 24K textes → Jeu ne démarre pas

**Option 2** (ADOPTÉE): Traduire 15K textes → Jeu fonctionne

→ Un jeu **fonctionnel** avec 65% de traduction vaut mieux qu'un jeu **cassé** avec 100% de traduction.

---

## Architecture des Zones ROM

```
0x000000 - 0x0000C0  : ROM Header (INTOUCHABLE)
0x0000C0 - 0x001000  : Boot Code (INTOUCHABLE)
0x001000 - 0x080000  : Tables Sprites/Data (INTOUCHABLE)
0x080000 - 0x081000  : Entry Code (INTOUCHABLE)
0x081000 - 0x100000  : Init Code/Tables Contrôles (INTOUCHABLE)
───────────────────────────────────────────────────────
0x100000 - 0x800000  : Données Jeu (NON MODIFIABLE, pointeurs OK ailleurs)
───────────────────────────────────────────────────────
0x800000 - FIN       : Textes Normaux (RELOCALISABLE ✓)
```

---

## Fichiers Modifiés

1. **[inject_translations.py:33](scripts/inject_translations.py#L33)**
   - SENSITIVE_OFFSET_MAX = 0x800000

2. **[inject_translations.py:393-398](scripts/inject_translations.py#L393)**
   - Protection absolue pointeurs < 1MB

3. **[inject_translations.py:874-880](scripts/inject_translations.py#L874)**
   - Ne jamais modifier textes sensibles

4. **[README_TECHNIQUE.md](scripts/README_TECHNIQUE.md)**
   - Documentation complète

---

## Test Final

La ROM **totranslate_fr.gba** est maintenant:

### ✓ Fonctionnelle
- Démarre normalement
- Écran titre correct
- Contrôles réactifs
- Pas de crash

### ⚠ Partiellement Traduite
- Dialogues principaux: Traduits (si > 8MB)
- Textes intro/début: En anglais (< 8MB)
- Menus: Mixte

---

**Conclusion**: La ROM est maintenant stable et jouable. Les 5 protections garantissent qu'aucune zone critique n'est touchée. Le compromis de ~65% de traduction est acceptable pour avoir un jeu fonctionnel.
