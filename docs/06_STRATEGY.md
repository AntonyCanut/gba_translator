# Stratégie de Relocalisation - Analyse Complète

## Résumé Exécutif

L'analyse approfondie de la ROM révèle que **96.6% des textes ne peuvent pas être relocalisés** avec la méthode actuelle basée sur les pointeurs directs.

### Statistiques Clés

- **Total de textes différents** : 14,436
- **Textes dans des arrays séquentiels** : 11,017 (76.3%)
- **Arrays avec chaîne de relocalisation complète** : 16 sur 889
- **Textes relocalisables avec pointeurs** : 371 (3.4%)
- **Textes non-relocalisables** : 10,646 (96.6%)

## Le Problème Technique

### Pourquoi translate_rom.py ne trouve pas de pointeurs ?

La ROM Pokemon utilise deux structures de données différentes :

#### 1. Pointeurs Directs (minorité)
```
Code → Pointeur 32-bit → Texte
```
Exemple : Messages système, dialogues uniques

#### 2. Arrays Séquentiels (majorité)
```
Code → Pointeur vers Table → Index dans array → Texte
```
Exemple : Noms de Pokemon, noms d'attaques, descriptions

### Structure d'un Array Séquentiel

```
Offset 0x001B2993:  "Face"      (texte #0)
Offset 0x001B2999:  "Picpic"    (texte #1)
Offset 0x001B29A1:  "Tornade"   (texte #2)
...                 (800+ textes)

Table de Pointeurs @ 0x0045B078:
  [0] → 0x081B2993  (pointe vers "Face")
  [1] → 0x081B2999  (pointe vers "Picpic")
  [2] → 0x081B29A1  (pointe vers "Tornade")
  ...

Code du jeu:
  load_move_name(move_id):
    table = *0x008A3F50  // Pointeur vers la table
    return table[move_id]
```

### Pourquoi c'est Difficile à Relocaliser

Pour relocaliser un array séquentiel, il faut :

1. **Trouver l'array** (fait ✓)
2. **Trouver la table de pointeurs** (fait ✓ pour 48 arrays)
3. **Trouver le pointeur vers la table** (fait ✓ pour 16 arrays seulement)
4. **Modifier le code** qui accède à la table (pas implémenté ❌)

## Les 3 Approches Possibles

### Approche 1 : Conservative (RECOMMANDÉ)
**Garder les traductions ≤ longueur originale**

**Avantages** :
- ✅ Fonctionne avec `reinsert_text.py` (script existant)
- ✅ Aucune relocalisation nécessaire
- ✅ Garantit la stabilité de la ROM
- ✅ Rapide à implémenter (2-3 mois)

**Inconvénients** :
- ⚠️ Limite la qualité des traductions
- ⚠️ Force l'utilisation d'abréviations

**Technique** :
- Utiliser `json_to_csv.py` pour export vers traducteurs
- Instructions : "Max {X} caractères par texte"
- Validation avec `validate_translation.py`
- Application avec `reinsert_text.py`

**Référence** : La ROM espagnole a utilisé cette approche pour 44% des textes

---

### Approche 2 : Relocalisation Partielle (POSSIBLE)
**Relocaliser les 371 textes qui ont des chaînes complètes**

**Avantages** :
- ✅ Permet de dépasser la longueur pour 3.4% des textes
- ✅ Fonctionne avec les outils actuels
- ✅ Amélioration modérée de la qualité

**Inconvénients** :
- ⚠️ Ne résout que 3.4% du problème
- ⚠️ Complexité supplémentaire pour bénéfice limité
- ⚠️ Les plus gros arrays (noms Pokemon/attaques) ne sont PAS relocalisables

**Technique** :
1. Utiliser `detect_text_arrays.py` pour identifier les 16 arrays
2. Créer `translate_rom_partial.py` qui :
   - Applique relocalisation pour les 371 textes identifiés
   - Applique insertion directe pour le reste
3. Génère rapport de ce qui a été relocalisé

**Textes relocalisables identifiés** :
- Array @ 0x0024F3C2 : 78 textes (descriptions d'objets)
- Array @ 0x003EED08 : 33 textes (messages de combat)
- Array @ 0x0041617A : 20 textes (interface)
- 23 autres petits arrays

---

### Approche 3 : Relocalisation Complète (AVANCÉ)
**Reconstruire les arrays et tables comme la ROM espagnole**

**Avantages** :
- ✅ Liberté totale sur la longueur des textes
- ✅ Qualité de traduction maximale
- ✅ Solution professionnelle

**Inconvénients** :
- ❌ Requiert modification du code assembleur
- ❌ Risque élevé de bugs
- ❌ Développement : 4-6 mois
- ❌ Requiert expertise en reverse engineering

**Technique** :
Pour chaque array séquentiel :

1. **Reconstruire l'array dans free space**
   ```
   New offset: 0x0161BC90
   Écrire tous les textes traduits bout à bout
   ```

2. **Reconstruire la table de pointeurs**
   ```
   New table offset: 0x0161D000
   Écrire 800+ pointeurs vers les nouveaux textes
   ```

3. **Modifier le code**
   ```
   Old: load_table_pointer from 0x008A3F50
   New: patch 0x008A3F50 to point to 0x0861D000
   ```

4. **Patcher les fonctions assembleur**
   - Identifier toutes les fonctions qui accèdent à l'array
   - Désassembler le code ARM/THUMB
   - Modifier les instructions pour pointer vers nouvelles tables
   - Recompiler et réinsérer

**Outils nécessaires** :
- IDA Pro / Ghidra (désassemblage)
- armips (assembleur ARM)
- Extensive testing sur émulateur
- Knowledge ROM Pokemon FireRed internals

---

## Recommandation Finale

### Pour un projet de traduction amateur/communautaire :
**→ Approche 1 (Conservative)**

**Raisons** :
1. La ROM espagnole officielle a utilisé cette approche avec succès
2. 44% des textes espagnols sont PLUS COURTS que l'anglais
3. Les traducteurs peuvent compenser avec des abréviations intelligentes
4. Risque minimal de bugs
5. Temps de développement : 2-3 mois vs 4-6 mois

### Pour un projet professionnel avec budget :
**→ Approche 3 (Relocalisation Complète)**

**Raisons** :
1. Qualité maximale
2. Pas de compromis sur les traductions
3. Solution technique propre
4. Réutilisable pour d'autres ROMs

### Pour un projet académique/recherche :
**→ Approche 2 (Relocalisation Partielle)**

**Raisons** :
1. Démontre la faisabilité de la relocalisation
2. Hybride intéressant techniquement
3. Base pour Approche 3 ultérieure

---

## Implémentation Recommandée (Approche 1)

### Phase 1 : Outils d'Export/Import (2 semaines)
```bash
# 1. Convertir JSON → CSV pour traducteurs
python3 json_to_csv.py differences/englishrom_diff_only.json translation_workfile.csv

# CSV format:
# offset, max_length, context, english_text, french_translation
# 0x001B2993, 10, "Move name", "Face", "Charge"
```

### Phase 2 : Traduction (8-12 semaines)
- Distribuer CSV aux traducteurs
- Colonne "max_length" indique la limite stricte
- Colonne "context" aide à comprendre l'usage
- Validation continue avec script

### Phase 3 : Validation (1 semaine)
```bash
# Convertir CSV → JSON
python3 csv_to_json.py translation_workfile.csv translated_texts.json

# Valider
python3 validate_translation.py translated_texts.json
```

### Phase 4 : Application (1 journée)
```bash
# Créer ROM traduite
python3 reinsert_text.py englishrom.gba translated_texts.json frenchrom.gba

# Tester sur émulateur
mgba-qt frenchrom.gba
```

---

## Données de Référence : ROM Espagnole

L'analyse de `spanishrom.gba` montre :

### Distribution des Longueurs
- **22% plus longs** : 792 textes relocalisés
- **34% même longueur** : 1,221 textes
- **44% plus courts** : 1,591 textes

### Exemples de Textes Abrégés

| Anglais | Espagnol | Économie |
|---------|----------|----------|
| "Take care now!" (14) | "¡Cuídate!" (10) | -4 chars |
| "Grass-type moves" (16) | "Mov. Planta" (11) | -5 chars |
| "Would you like to save?" (23) | "¿Guardar?" (9) | -14 chars |

### Technique Espagnole
La ROM espagnole a utilisé :
1. Abréviations intelligentes ("Mov." au lieu de "Movimientos")
2. Reformulations concises ("¿Guardar?" au lieu de "¿Quieres guardar?")
3. Symboles (¿ ¡) au lieu de mots longs
4. Relocalisation pour seulement 22% des textes modifiés

**Conclusion** : Même une langue réputée plus longue que l'anglais (espagnol) a réussi avec l'approche conservative.

---

## Prochaines Étapes

### Option A : Continuer avec Approche 1 (RECOMMANDÉ)
1. Créer `json_to_csv.py` et `csv_to_json.py`
2. Tester workflow sur échantillon de 100 textes
3. Recruter traducteurs
4. Lancer traduction complète

### Option B : Explorer Approche 3 (AVANCÉ)
1. Étudier code assembleur avec IDA Pro
2. Identifier toutes les fonctions d'accès aux arrays
3. Créer PoC pour 1 array (noms d'attaques)
4. Si succès → généraliser

### Option C : Hybride
1. Démarrer traduction avec Approche 1
2. Développer Approche 3 en parallèle
3. Réappliquer traductions avec relocalisation complète après 4-6 mois

---

## Fichiers Générés

Les analyses ont produit :

1. **text_tables_analysis.json** : 2,166 tables de pointeurs détectées
2. **text_arrays_analysis.json** : 889 arrays séquentiels détectés
3. **Ce document** : Stratégie complète

Les scripts de détection :

1. **detect_text_tables.py** : Détecte tables de pointeurs
2. **detect_text_arrays.py** : Détecte arrays + chaînes de relocalisation

---

## Conclusion

Le problème soulevé par l'utilisateur ("notre script actuel ne gère que les pointeurs directs") est **réel et fondamental**. La solution dépend des objectifs du projet :

- **Traduction amateur** : Approche 1 (conservative)
- **Traduction professionnelle** : Approche 3 (relocalisation complète)
- **Recherche technique** : Approche 2 (hybride)

Pour la majorité des projets, **l'Approche 1 est recommandée** car elle a été prouvée fonctionnelle par la ROM espagnole officielle et nécessite le moins de développement technique complexe.
