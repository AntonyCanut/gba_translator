# Enseigne Boutique Pokémon « SHOP » — plan d’implémentation

> **Pour les workers agentiques :** SOUS-COMPÉTENCE REQUISE : utiliser
> `superpowers:executing-plans` pour exécuter les tâches dans l’ordre. Chaque
> tâche suit le cycle TDD rouge/vert.

**But :** livrer une enseigne extérieure « SHOP » éditable et présente dans
le tileset vivant des Boutiques Pokémon de la ROM FR.

**Architecture :** le pipeline sprite sait sélectionner une fenêtre de tuiles
au sein d’un bloc LZ77 grâce à `start_tile`. Le registre FR décrit le bloc du
tileset, et le build réinjecte le PNG 16 × 8 après les réparations.

**Stack :** Python 3.11, pytest, PNG indexé 4 bpp, tuiles GBA 4 bpp, LZ77.

## Contraintes globales

- Ne jamais modifier `input/roms/*.gba`.
- Ne pas ajouter de dépendance.
- Préserver les 638 tuiles hors enseigne dans chaque bloc.
- Réinjecter après les réparations LZ77 de `make build-fr`.
- Vérifier les pixels décompressés dans la ROM construite.

---

### Tâche 1 : fenêtre partielle dans un bloc sprite

**Fichiers :**

- Modifier : `tests/unit/test_sprite_rom.py`
- Modifier : `src/graphics/sprite_rom.py`

**Interfaces :**

- `extract_block(..., start_tile: int = 0) -> tuple[Grid, int, int]`
- `insert_block(..., start_tile: int = 0) -> None`

- [ ] Écrire deux tests synthétiques qui sélectionnent puis remplacent la
  deuxième tuile d’un bloc de trois tuiles, en exigeant la préservation des
  première et troisième tuiles.
- [ ] Exécuter `python3 -m pytest tests/unit/test_sprite_rom.py -q` et constater
  l’échec car `start_tile` n’existe pas.
- [ ] Appliquer l’offset `start_tile * 32` aux chemins compressé et brut, avec
  validation de la taille totale requise.
- [ ] Réexécuter le fichier ciblé et obtenir 100 % de réussite.

### Tâche 2 : registre, CLI et asset « SHOP »

**Fichiers :**

- Modifier : `languages/fr/sprites.py`
- Modifier : `scripts/extract_sprite.py`
- Modifier : `scripts/insert_sprite.py`
- Créer : `tests/unit/fr/test_pokemon_mart_sign.py`
- Créer : `languages/fr/sprites/pokemon_mart_sign.png`

**Interfaces :**

- `SpriteDef.start_tiles: tuple[int, ...]`, vide pour un départ à zéro.
- `pokemon_mart_sign.blocks == (0x00CF91A0,)`.
- `pokemon_mart_sign.start_tiles == (413,)`.
- `pokemon_mart_sign.palette == 0x00EA1BC8`.
- L’asset mesure 16 × 8 px et utilise seulement les indices 0 à 15.

- [ ] Écrire les gardes de registre et d’asset ; les exécuter pour observer
  l’échec dû à l’entrée et au PNG absents.
- [ ] Ajouter `start_tiles` au registre et transmettre sa valeur dans les CLI.
- [ ] Extraire le sprite depuis `input/roms/englishrom.gba`, puis remplacer le
  motif 3 × 5 « MART » par « SHOP » sans changer le fond ni la palette.
- [ ] Réexécuter les tests ciblés et comparer visuellement l’asset agrandi.

### Tâche 3 : livraison dans le build FR

**Fichiers :**

- Modifier : `Makefile`
- Modifier : `tests/unit/fr/test_pokemon_mart_sign.py`

**Interfaces :**

- Deux appels `insert_sprite.py`, avec `--block-index 0` puis `1`, consomment
  l’asset `languages/fr/sprites/pokemon_mart_sign.png` après les réparations.

- [ ] Ajouter une garde qui vérifie la commande dans `make -n build-fr`
  et constater l’échec initial.
- [ ] Brancher la réinsertion après les réparations graphiques.
- [ ] Exécuter les gardes ciblées jusqu’à réussite.

### Tâche 4 : preuve ROM et intégration locale

**Fichiers :**

- Modifier : `tests/unit/fr/test_pokemon_mart_sign.py`
- Modifier : `tasks/todo.md`

- [ ] Ajouter une garde marquée `rom` qui décompresse le bloc de
  `output/roms/GenedRom-fr.gba` et compare les tuiles 413–414 à l’asset.
- [ ] Committer les sources et l’asset avant le build long.
- [ ] Exécuter le détecteur de processus, puis `make build-fr` et la garde ROM.
- [ ] Exécuter les tests ciblés, `make test`, `ruff check` ciblé et
  `git diff --check`.
- [ ] Relire le diff, documenter les résultats, committer, attendre la file
  d’intégration, rebaser puis revalider si la base a avancé.
- [ ] Publier le bilan sur l’issue #152, la clôturer en `completed` et terminer
  l’orchestration sans push.
