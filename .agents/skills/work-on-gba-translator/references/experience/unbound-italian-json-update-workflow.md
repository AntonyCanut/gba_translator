---
name: unbound-italian-json-update-workflow
description: Smart Italian translation JSON update workflow with diffing and selective merging
metadata:
  node_type: memory
  type: project
  originSessionId: 91ba07f3-8024-4783-afab-2361fcde0e90
---

## Mise à jour intelligente des traductions italiennes

Quand l'utilisateur fournit un JSON italien UPDATED, utiliser le script intelligent `/gba_translator/scripts/process_italian_translations.py` pour :

1. **Comparer ancien vs nouveau JSON** — détecter quels offsets ont été ajoutés/modifiés
2. **Filtrer les entrées non-traduites** — retirer les entrées identiques à l'anglais (unchanged + corrupted/binary)
3. **Générer un diff lisible** — montrer les nouvelles traductions et les mises à jour
4. **Mettre à jour combined_it.txt sélectivement** — fusionner SEULEMENT les changements

### Comportement de merge (IMPORTANT)

Le script **fusionne** avec le fichier existant si `--output` pointe vers un fichier déjà présent :
- Entrées du JSON seulement → ajoutées
- Entrées présentes dans les deux → JSON gagne (override)
- Entrées dans l'existant mais absentes du JSON → **PRÉSERVÉES** (ne sont pas perdues)

Ce comportement est sûr même sans `--compare` : toujours faire un merge, jamais un remplacement.

### Commande standard (import ou update)

```bash
# Sans options : merge auto avec combined_it.txt existant
python3 scripts/process_italian_translations.py Italian_Translations_v2.json
```

Résultat : combined_it.txt avec ~13,598 traductions valides

### Commande avec affichage du diff

```bash
python3 scripts/process_italian_translations.py Italian_Translations_v2.json \
  --compare languages/it/combined_it.txt \
  --show-diff
```

Résultat :
- Rapport du diff (combien new/updated offsets détectés)
- Samples des nouveaux entrées et changements
- combined_it.txt mis à jour avec les traductions fraîches

### Format du JSON source attendu

```json
{
  "entries": [
    {
      "id": "tbl_pokemon_names_00001",
      "category": "pokemon_names",
      "address": "0x166A997",
      "original": "Bulbasaur",
      "translated": "Bulbasaur",
      "byte_length": 11,
      "table_name": "data.pokemon.names",
      ...
    }
  ]
}
```

Clés critiques :
- `address` (hex, ex: "0x166A997") → utilisé comme offset dans combined_it.txt
- `original` (EN) vs `translated` (IT) — comparaison pour détecter les non-traduites
- `category` (pokemon_names, move_descriptions, scripts, etc.) — pour identifier les entrées corrupted

### Filtres appliqués

1. **Unchanged** : `translated == original` (case-insensitive) → REJETÉ
2. **Corrupted/binary** : `category == "scripts"` ET `translated == original` → REJETÉ
3. **Empty** : pas de `translated` ou `address` → REJETÉ
4. **Duplicates** : dernier offset gagne (case-insensitive)

### Résultat attendu

Après processing :
- 11,920 entrées italiennes valides (~86.8% du JSON source)
- 1,813 entrées filtrées (~13.2%)
- Format : `<offset_hex>: <text_IT>` (une par ligne, trié)
- Contrôle codes préservés : `{B4}`, `{FD24}`, `\n`, `\p`, `\l`
- Accents italiens préservés : à, è, é, ì, ò, ù, ç

### Workflow futur

1. User → fournit nouvel Italian_Translations.json
2. Claude → `process_italian_translations.py --show-diff` → rapport d'update
3. Vérifier diff qualité (voir samples)
4. Commit + rebuild test : `python3 scripts/build_language.py it`
5. Vérifier ROM vs ancien (mGBA visuelle sur quelques dialogues IT)
