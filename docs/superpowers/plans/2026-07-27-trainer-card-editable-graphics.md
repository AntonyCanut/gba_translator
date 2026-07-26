# Graphismes éditables de la carte de Dresseur — plan d’implémentation

> **Pour les workers agentiques :** SOUS-COMPÉTENCE REQUISE :
> `superpowers:executing-plans`. Exécuter les tâches dans l’ordre avec leur cycle
> TDD rouge/vert.

**But :** fournir deux PNG indexés 256 × 160 du recto et du verso de la carte de
Dresseur, réinjectables dans leurs planches LZ77 via les tilemaps du jeu.

**Architecture :** le registre de sprites associe optionnellement une tilemap à
chaque planche graphique. Le cœur graphique reconstruit l’écran avec les indices
et flips de la tilemap, puis inverse exactement cette opération à l’insertion en
refusant les éditions contradictoires d’une tuile partagée.

**Stack :** Python 3.11, pytest, PNG indexé 4 bpp, tuiles GBA 4 bpp, LZ77.

## Contraintes globales

- Ne jamais modifier `input/roms/*.gba`.
- Ne pas ajouter de dépendance.
- Préserver la tilemap, les tuiles hors écran et les octets voisins.
- Ne pas brancher ces images encore anglaises dans `make build-fr`.
- Les nouvelles fonctions publiques ont des types et des docstrings françaises.

---

### Tâche 1 : reconstruction réversible par tilemap

**Fichiers :**

- Modifier : `tests/unit/test_sprite_rom.py`
- Modifier : `src/graphics/sprite_rom.py`

**Interfaces :**

- Produit :
  `extract_mapped_block(rom, tiles_offset, tilemap_offset, tiles_wide,
  tiles_tall, *, compressed=True) -> tuple[Grid, int, int]`
- Produit :
  `insert_mapped_block(rom, tiles_offset, tilemap_offset, grid, tiles_wide,
  tiles_tall, *, compressed=True, vram_safe=True) -> None`

- [ ] Écrire un test synthétique qui compose quatre cellules depuis trois
  tuiles, dont une occurrence retournée horizontalement et verticalement.
- [ ] Exécuter
  `python3 -m pytest tests/unit/test_sprite_rom.py -q` et constater l’échec
  d’import des nouvelles fonctions.
- [ ] Implémenter le décodage des entrées 16 bits (`index`, `hflip`, `vflip`),
  la composition et l’opération inverse.
- [ ] Ajouter un test qui modifie deux occurrences d’une même tuile de façon
  incompatible et exige `ValueError`.
- [ ] Exécuter le fichier ciblé jusqu’à réussite complète.

### Tâche 2 : registre et scripts CLI

**Fichiers :**

- Modifier : `languages/fr/sprites.py`
- Modifier : `scripts/extract_sprite.py`
- Modifier : `scripts/insert_sprite.py`
- Créer : `tests/unit/test_trainer_card_sprites.py`

**Interfaces :**

- `SpriteDef.tilemaps: tuple[int, ...]`, vide pour les sprites linéaires.
- `trainer_card_front` :
  planche `0x01FDA2BC`, tilemap `0x01FDA820`, écran 32 × 20 tuiles.
- `trainer_card_back` :
  planche `0x01FDAA4C`, tilemap `0x01FDB2AC`, écran 32 × 20 tuiles.

- [ ] Écrire un test exigeant les deux entrées et l’appariement exact
  bloc/tilemap.
- [ ] Exécuter
  `python3 -m pytest tests/unit/test_trainer_card_sprites.py -q` et constater
  l’échec dû aux entrées absentes.
- [ ] Ajouter `tilemaps` et sa validation au registre.
- [ ] Faire choisir aux deux scripts le chemin mappé quand `tilemaps` est
  renseigné, sans changer le chemin historique.
- [ ] Exécuter les tests ciblés des sprites.

### Tâche 3 : assets éditables et preuve ROM

**Fichiers :**

- Créer : `languages/fr/sprites/trainer_card_front.png`
- Créer : `languages/fr/sprites/trainer_card_back.png`
- Modifier : `tests/unit/test_trainer_card_sprites.py`
- Modifier : `tasks/todo.md`

**Interfaces :**

- Les deux PNG sont indexés 4 bpp, ont une palette de 16 couleurs et mesurent
  256 × 160.

- [ ] Ajouter au test les dimensions et le format indexé attendus ; constater
  l’échec tant que les assets sont absents.
- [ ] Extraire les deux images depuis `input/roms/englishrom.gba` avec
  `scripts/extract_sprite.py`.
- [ ] Réinjecter chaque PNG dans une copie temporaire de la ROM avec
  `scripts/insert_sprite.py`.
- [ ] Comparer les contenus LZ77 décompressés avant/après et exiger une égalité
  octet pour octet.
- [ ] Ouvrir les deux PNG et confirmer visuellement que « TRAINER CARD » et
  « LEAGUE BADGES » sont lisibles.
- [ ] Documenter les commandes et résultats dans la revue de `tasks/todo.md`.

### Tâche 4 : validation et intégration locale

**Fichiers :** tous les fichiers ci-dessus.

- [ ] Exécuter le détecteur de processus de test du dépôt.
- [ ] Exécuter les tests sprites ciblés.
- [ ] Exécuter `make test`, `ruff check` sur les fichiers Python modifiés et
  `git diff --check`.
- [ ] Relire le diff, committer avec des chemins explicitement stagés et
  vérifier `git show --stat HEAD`.
- [ ] Attendre la file d’intégration, rebaser via l’orchestrateur et revalider
  si la branche de base a avancé.
- [ ] Publier le bilan sur l’issue #148, la clôturer comme terminée et terminer
  l’orchestration.
