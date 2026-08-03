# Enseigne Boutique Pokémon « SHOP » — plan d’implémentation du suivi

> **Pour les workers agentiques :** SOUS-COMPÉTENCE REQUISE : utiliser
> `superpowers:executing-plans` pour exécuter ce plan tâche par tâche. Les
> étapes de comportement suivent le cycle TDD rouge/vert.

**But :** remplacer les trois copies actives de « MART » par le lettrage
« SHOP » fourni, sans modifier les cadres ni les palettes des tilesets.

**Architecture :** le registre sprite existant référence les trois fenêtres
de tuiles. Le build injecte le BMP fourni dans sa variante native et un PNG
adapté dans les deux copies classiques, après toutes les réparations LZ77.

**Stack :** Python 3.11, pytest, Pillow, PNG/BMP indexés 4 bpp, tuiles GBA
4 bpp, compression LZ77.

## Contraintes globales

- Ne jamais modifier `input/roms/*.gba`.
- Conserver exactement le BMP utilisateur de SHA-256
  `93407be53e035fbebfa3659dfd9f8e96d3b594ece86c63830c2e76df4db76482`.
- Préserver tous les octets décompressés hors des tuiles 225–226 ou 413–414.
- Réinjecter après les réparations LZ77 de `make build-fr`.
- Vérifier les trois graphismes décompressés dans la ROM construite.

---

### Tâche 1 : gardes rouges des trois copies et du BMP fourni

**Fichiers :**

- Modifier : `tests/unit/fr/test_pokemon_mart_sign.py`

**Interfaces :**

- `SPRITES["pokemon_mart_sign"].blocks` contient trois offsets ordonnés.
- `pokemon_mart_sign.bmp` est la référence binaire exacte du commentaire.
- `pokemon_mart_sign_classic.png` est la variante des deux blocs classiques.

- [ ] Étendre le test de registre aux trois offsets, tuiles de départ et
  capacités compressées.
- [ ] Ajouter un test du SHA-256, des dimensions et de la grille complète du
  BMP fourni.
- [ ] Ajouter un test de parité BMP/PNG et un test du masque du PNG classique.
- [ ] Étendre le test `make -n build-fr` aux trois insertions ordonnées.
- [ ] Étendre le test ROM aux trois fenêtres décompressées.
- [ ] Exécuter
  `python3 -m pytest tests/unit/fr/test_pokemon_mart_sign.py -q` et constater
  les échecs dus au registre mono-bloc, aux assets absents et au build incomplet.

### Tâche 2 : registre et assets multi-copies

**Fichiers :**

- Modifier : `languages/fr/sprites.py`
- Créer : `languages/fr/sprites/pokemon_mart_sign.bmp`
- Modifier : `languages/fr/sprites/pokemon_mart_sign.png`
- Créer : `languages/fr/sprites/pokemon_mart_sign_classic.png`

**Interfaces :**

- `blocks == (0x007559B8, 0x00B89D5C, 0x00CF91A0)`.
- `start_tiles == (225, 225, 413)`.
- `max_compressed_sizes == (10_452, 10_531, 11_604)`.

- [ ] Ajouter les deux copies manquantes au registre avec leurs capacités
  physiques d’origine.
- [ ] Copier le BMP fourni octet pour octet dans le dossier des assets.
- [ ] Régénérer le PNG éditable depuis la grille indexée du BMP.
- [ ] Produire le PNG classique en conservant le cadre natif et en appliquant
  le masque « SHOP » officiel à son dégradé de lettres.
- [ ] Réexécuter les gardes d’asset et de registre jusqu’à réussite.
- [ ] Committer immédiatement les sources et assets avant le build long.

### Tâche 3 : insertion tardive des trois variantes

**Fichiers :**

- Modifier : `Makefile`

**Interfaces :**

- Deux commandes `--block-index 0/1` consomment
  `pokemon_mart_sign_classic.png`.
- Une commande `--block-index 2` consomme `pokemon_mart_sign.bmp`.

- [ ] Remplacer l’insertion mono-bloc par les trois commandes explicites.
- [ ] Exécuter la garde ciblée du build jusqu’à réussite.
- [ ] Committer le câblage avant la reconstruction.

### Tâche 4 : reconstruction et preuve ROM

**Fichiers :**

- Modifier : `output/roms/GenedRom-fr.gba`
- Modifier : `tasks/todo.md`

**Interfaces :**

- La ROM versionnée décompresse vers les grilles attendues aux trois fenêtres.

- [ ] Exécuter le détecteur de processus de test, puis reconstruire la ROM FR.
- [ ] Exécuter la garde ROM ciblée et comparer les tuiles voisines avant/après.
- [ ] Exécuter les tests graphiques ciblés, la suite rapide multilingue, Vitest,
  le lint ciblé et `git diff --check`.
- [ ] Documenter les résultats dans `tasks/todo.md` et committer la ROM.
- [ ] Rebaser via l’orchestrateur, revalider si la base a avancé, publier le
  bilan sur l’issue #152 et conserver son état `completed`, sans push.
