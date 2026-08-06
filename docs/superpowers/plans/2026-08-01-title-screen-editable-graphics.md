# Graphisme éditable de l’écran titre — plan d’implémentation

> **Pour les workers agentiques :** SOUS-COMPÉTENCE REQUISE : utiliser
> `superpowers:executing-plans`. Les étapes suivent des cases à cocher et le
> cycle TDD rouge/vert.

**But :** exporter et réinjecter l’écran titre 8 bpp sous forme de PNG indexé
256 couleurs afin de rendre « PRESS START » modifiable.

**Architecture :** le pipeline existant devient paramétrable en profondeur de
palette, sans changer le comportement 4 bpp. Le registre FR décrit la planche,
la tilemap et la palette de l’écran titre ; les CLI transmettent cette
profondeur au cœur graphique.

**Stack :** Python 3.11, pytest, PNG indexé, tuiles GBA 4/8 bpp, LZ77.

## Contraintes globales

- Ne jamais modifier `input/roms/*.gba`.
- Ne pas ajouter de dépendance.
- Préserver les octets voisins et les données hors écran.
- Ne pas brancher l’asset anglais dans `make build-fr`.
- Conserver le comportement existant de tous les sprites 4 bpp.

---

### Tâche 1 : PNG indexé 256 couleurs

**Fichiers :**

- Modifier : `tests/unit/test_sprite_png.py`
- Modifier : `src/graphics/sprite_png.py`
- Modifier : `src/graphics/sprite_bmp.py`

**Interfaces :**

- `write_indexed_png(..., palette: Palette)` choisit 4 ou 8 bits selon la palette.
- `read_indexed_png(...)` accepte des indices 0..255 pour une palette 256 couleurs.
- `write_indexed_image(...)` refuse BMP si la grille ou la palette exige 8 bpp.

- [x] Ajouter un test avec une palette littérale de 256 couleurs et une grille
  contenant `0xF3`, puis exiger un IHDR 8 bpp et un round-trip exact :

```python
palette = [(i, i, i) for i in range(256)]
grid = [[0x00, 0x10, 0x80, 0xF3]]
write_indexed_png(out, 4, 1, grid, palette)
assert out.read_bytes()[24] == 8
assert read_indexed_png(out) == (4, 1, grid)
```

- [x] Lancer `python3 -m pytest tests/unit/test_sprite_png.py -q` et constater
  l’échec attendu sur la limite de 16 couleurs/indices.
- [x] Généraliser la validation, le paquetage des scanlines et le contrôle de
  palette au 4/8 bpp, sans changer le PNG 4 bpp historique.
- [x] Relancer le test ciblé jusqu’à réussite complète.

### Tâche 2 : tuiles GBA mappées 8 bpp

**Fichiers :**

- Modifier : `tests/unit/test_sprite_rom.py`
- Modifier : `src/graphics/sprite_rom.py`

**Interfaces :**

- Ajouter `bits_per_pixel: int = 4` à `tiles_to_grid`, `grid_to_tiles`,
  `extract_block`, `insert_block`, `extract_mapped_block` et
  `insert_mapped_block`.
- Ajouter `colours: int = 16` à `read_gba_palette`.

- [x] Ajouter un round-trip synthétique de deux tuiles 8 bpp et une tilemap
  avec flip horizontal :

```python
tiles = bytes((x + 17 * y) % 256 for tile in range(2) for y in range(8) for x in range(8))
grid = tiles_to_grid(tiles, 2, 1, bits_per_pixel=8)
assert grid_to_tiles(grid, 2, 1, bits_per_pixel=8) == tiles
```

- [x] Lancer `python3 -m pytest tests/unit/test_sprite_rom.py -q` et constater
  l’échec dû au nouvel argument absent.
- [x] Implémenter les tuiles de 64 octets en 8 bpp, les bornes de pixels et la
  taille de palette, en conservant 32 octets/16 couleurs par défaut.
- [x] Relancer le fichier ciblé jusqu’à réussite complète.

### Tâche 3 : registre, CLI et asset écran titre

**Fichiers :**

- Modifier : `languages/fr/sprites.py`
- Modifier : `scripts/extract_sprite.py`
- Modifier : `scripts/insert_sprite.py`
- Créer : `tests/unit/test_title_screen_sprite.py`
- Créer : `languages/fr/sprites/title_screen.png`

**Interfaces :**

- `SpriteDef.bits_per_pixel: int = 4`, validé dans `__post_init__`.
- `title_screen`: planche `0x01FD4854`, tilemap `0x01FD6514`, palette
  `0x01FD699C`, écran 32 × 20, 8 bpp.

- [x] Ajouter un test exigeant l’entrée exacte du registre, puis le lancer pour
  observer l’échec dû à l’entrée absente.
- [x] Ajouter `bits_per_pixel` au registre et transmettre sa valeur dans les
  deux CLI ainsi qu’à `read_gba_palette(..., colours=256)`.
- [x] Ajouter les gardes d’asset suivantes et constater leur échec tant que le
  PNG n’existe pas :

```python
width, height, grid = read_indexed_image(ASSET)
assert (width, height) == (256, 160)
assert max(pixel for row in grid for pixel in row) > 15
assert any(grid[y][x] for y in range(144, 153) for x in range(64, 176))
```

- [x] Extraire le PNG avec :

```bash
python3 scripts/extract_sprite.py --rom input/roms/englishrom.gba \
  --lang fr --sprite title_screen \
  -o languages/fr/sprites/title_screen.png
```

- [x] Réinjecter le PNG dans une copie sous `output/` et comparer la planche
  LZ77 décompressée avant/après, octet pour octet.
- [x] Relancer tous les tests sprites ciblés.

### Tâche 4 : validation et intégration locale

**Fichiers :** tous les fichiers ci-dessus et `tasks/todo.md`.

- [x] Exécuter le détecteur de processus de test.
- [x] Lancer les tests sprites/PNG ciblés, puis `make test`.
- [x] Lancer la collecte canonique `make lint` et `git diff --check`.
- [x] Relire la spécification, le plan, le diff et la preuve de round-trip.
- [x] Documenter les résultats dans la revue de `tasks/todo.md`.
- [ ] Stager uniquement les chemins du ticket, committer au format conventionnel
  et vérifier `git show --stat HEAD` ainsi que `git status --porcelain`.
- [ ] Attendre la file d’intégration, rebaser via l’orchestrateur et revalider si
  la branche de base a avancé.
- [ ] Publier le bilan GitHub, clôturer l’issue #155 en `completed`, puis terminer
  l’orchestration.

### Tâche 5 : intégrer le dessin français fourni lors de la réouverture

**Fichiers :**

- Modifier : `tests/unit/test_title_screen_sprite.py`
- Modifier : `languages/fr/sprites/title_screen.png`
- Modifier : `languages/fr/sprites.py`
- Modifier : `Makefile`
- Modifier : `tasks/todo.md`

**Interfaces :**

- `languages/fr/sprites/title_screen.png` conserve 256 × 160 pixels, une palette
  indexée de 256 couleurs et les indices animés 163/164.
- `make build-fr` appelle `scripts/insert_sprite.py --sprite title_screen` sur
  `$(FR_BUILD)` après les autres assets manuels.

- [x] Ajouter une garde qui identifie la grille « PRESSEZ START » et le câblage
  exact de `build-fr`.
- [x] Lancer la garde et constater qu’elle échoue sur le dessin anglais et
  l’étape de build absente.
- [x] Convertir le BMP fourni vers le PNG indexé sans changer sa palette ni ses
  indices, puis ajouter l’appel minimal dans le `Makefile`.
- [x] Ramener à l’index de fond les deux pixels qui débordent dans la tuile 99,
  afin de conserver la planche et la tilemap historiques.
- [x] Réinjecter le PNG dans une copie de ROM, réextraire l’écran et comparer
  la grille ainsi que la palette.
- [ ] Reconstruire la ROM FR, vérifier le clignotement sur plusieurs frames et
  exécuter les validations ciblées puis complètes.
- [ ] Relire le diff, committer, intégrer localement et publier le bilan sur
  l’issue sans push.

### Tâche 6 : restituer les deux pixels du dernier « T »

**Fichiers :**

- Modifier : `tests/unit/test_title_screen_sprite.py`
- Modifier : `tests/unit/test_sprite_rom.py`
- Modifier : `languages/fr/sprites.py`
- Modifier : `languages/fr/sprites/title_screen.png`
- Modifier : `scripts/extract_sprite.py`
- Modifier : `src/graphics/sprite_rom.py`
- Modifier : `docs/superpowers/specs/2026-08-01-title-screen-editable-graphics-design.md`
- Modifier : `tasks/todo.md`

**Interfaces :**

- `SpriteDef.block_pointers` référence `0x01ED7C7C` et `0x01ED7EC0` pour la
  planche du titre.
- `SpriteDef.tilemap_pointers` référence `0x01ED7C84` et `0x01ED7EC8` pour sa
  tilemap.
- Après insertion, les pointeurs de planche restent à `0x01FD4854`, ceux de la
  tilemap ciblent un même nouveau flux et la grille réextraite contient
  l’indice 164 aux pixels `(160,152)` et `(160,153)`.
- `resolve_live_offset` exige que tous les pointeurs connus convergent vers une
  adresse ROM valide ; l’extracteur suit ainsi les blocs relocalisés sans scan.

- [x] Modifier le test d’asset pour exiger l’empreinte du BMP complet et les
  deux valeurs littérales `grid[152][160] == grid[153][160] == 164`.
- [x] Modifier le test ROM pour lire les offsets relocalisés depuis les quatre
  pointeurs, puis comparer la grille réextraite à l’asset complet.
- [x] Lancer `python3 -m pytest tests/unit/test_title_screen_sprite.py -q` et
  constater l’échec attendu sur les deux pixels encore à 31.
- [x] Déclarer les deux ensembles de pointeurs dans `title_screen`, puis
  convertir le BMP fourni en PNG indexé en conservant exactement la palette et
  les 40 960 indices.
- [x] Relancer le test ciblé avec marqueur ROM et exiger 100 % de réussite.
- [x] Exécuter `make build-fr`, suivre les pointeurs dans
  `output/roms/GenedRom-fr.gba` et comparer la grille finale à l’asset.
- [x] Vérifier le clignotement mGBA sans sauvegarde en jeu, puis lancer les
  tests graphiques ciblés, la suite rapide complète et le lint.
- [x] Corriger après revue l’extraction sur ROM relocalisée et remplacer
  l’empreinte partielle par les 40 960 indices plus la palette complète.
- [ ] Relire le diff, committer les chemins exacts, rebaser via
  l’orchestrateur, republier le résultat sur l’issue #155 et terminer sans push.
