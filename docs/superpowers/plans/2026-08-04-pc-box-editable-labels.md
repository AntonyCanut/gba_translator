# Dessins éditables des boîtes PC — plan d’implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** fournir un PNG indexé réinjectable contenant les trois libellés
graphiques anglais des boîtes PC.

**Architecture:** ajouter une entrée au registre de sprites existant pour la
planche LZ77 commune, puis produire l’asset au moyen du CLI existant. Les tests
comparent les pixels indexés aux tuiles de la ROM et prouvent le round-trip.
Le CLI transmet les pointeurs déclarés au chemin générique des blocs non
mappés : si une édition ne tient plus en place, elle est relocalisée uniquement
via ces pointeurs connus, sans scan de la ROM.

**Tech Stack:** Python 3.11, pytest, PNG indexé 4 bpp, tuiles GBA 4 bpp, LZ77.

## Global Constraints

- Ne jamais modifier `input/roms/*.gba`.
- Ne pas ajouter de dépendance ni de logique graphique spécifique au PC.
- Ne pas brancher l’image anglaise dans `make build-fr`.
- Utiliser uniquement le pointeur ROM vérifié `0x0008F034`, sans scan aveugle.

---

### Task 1: Registre et asset éditable

**Files:**

- Modify: `languages/fr/sprites.py`
- Create: `languages/fr/sprites/pc_box_labels.png`
- Create: `tests/unit/fr/test_pc_box_label_sprite.py`
- Modify: `tasks/todo.md`

**Interfaces:**

- Consumes: `SpriteDef`, `extract_block`, `read_indexed_image`.
- Produces: `SPRITES["pc_box_labels"]`, bloc `0x00E9C438`, palette
  `0x003CE5DC`, pointeur `0x0008F034`, grille 16 × 9 tuiles.

- [x] **Step 1: écrire les tests rouges**

  Ajouter des tests qui exigent l’entrée de registre, un asset indexé 128 × 72
  et l’égalité de ses indices avec `extract_block` sur la ROM anglaise.

- [x] **Step 2: vérifier l’échec attendu**

  Run: `python3 -m pytest tests/unit/fr/test_pc_box_label_sprite.py -q`

  Expected: FAIL car `SPRITES["pc_box_labels"]` et l’asset sont absents.

- [x] **Step 3: ajouter l’entrée minimale et extraire le PNG**

  Ajouter le `SpriteDef`, puis exécuter :

  `python3 scripts/extract_sprite.py --rom input/roms/englishrom.gba --lang fr --sprite pc_box_labels -o languages/fr/sprites/pc_box_labels.png`

- [x] **Step 4: vérifier le vert et le round-trip**

  Run: `python3 -m pytest tests/unit/fr/test_pc_box_label_sprite.py tests/unit/test_sprite_rom.py tests/unit/test_sprite_png.py -q`

  Expected: PASS. Le test marqué `rom` réinjecte réellement le PNG avec le CLI
  dans une copie temporaire de `englishrom.gba`, compare byte-identique les
  4 608 octets décompressés et contrôle le backup `.bak`.

- [x] **Step 5: valider et committer**

  Exécuter la suite rapide, le lint ciblé et `git diff --check`, puis committer
  avec `feat(fr): extraire les dessins des boîtes PC`.

### Task 2: Intégrer le dessin français contribué

**Files:**

- Modify: `languages/fr/sprites/pc_box_labels.png`
- Modify: `languages/fr/sprites.py`
- Modify: `tests/unit/fr/test_pc_box_label_sprite.py`
- Modify: `Makefile`
- Modify: `tasks/todo.md`

**Interfaces:**

- Consumes: le BMP 4 bpp joint au commentaire GitHub #163 et
  `SPRITES["pc_box_labels"]`.
- Produces: un PNG canonique dont l’empreinte de grille est
  `3e8856cdfc9e605b732905e923ec42f950462a6156bef0a971db10b3dea28c9d`
  et une ROM FR dont le bloc pointé contient cette grille.

- [x] **Step 1: écrire les gardes rouges**

  Remplacer la garde d’absence du build par une assertion exigeant :

  ```text
  python3 scripts/insert_sprite.py --rom output/roms/GenedRom-fr.gba --lang fr --sprite pc_box_labels --image languages/fr/sprites/pc_box_labels.png
  ```

  Ajouter une empreinte SHA-256 des 9 216 indices du PNG et un test `rom` qui
  suit `block_pointers[0][0]` avant d’extraire la planche construite.

- [x] **Step 2: vérifier l’échec attendu**

  Run: `python3 -m pytest tests/unit/fr/test_pc_box_label_sprite.py -q -m "not rom"`

  Expected: FAIL parce que le PNG anglais n’a pas l’empreinte contribuée et
  parce que `build-fr` ne contient pas encore la commande d’insertion.

- [x] **Step 3: convertir et câbler l’asset**

  Lire le BMP avec `read_indexed_image`, écrire sa grille dans
  `languages/fr/sprites/pc_box_labels.png` avec `write_indexed_image` et la
  palette ROM existante, puis ajouter la commande ci-dessus à `build-fr` après
  `$(PATCH_SUMMARY_STAT_LABELS_SCRIPT)`.

- [x] **Step 4: vérifier le vert rapide**

  Run: `python3 -m pytest tests/unit/fr/test_pc_box_label_sprite.py -q -m "not rom"`

  Expected: PASS, avec le hash de grille et le câblage exact du Makefile.

- [x] **Step 5: construire et vérifier la ROM**

  Run: `make build-fr`

  Run: `python3 -m pytest tests/unit/fr/test_pc_box_label_sprite.py -q`

  Expected: PASS ; le pointeur vivant mène à 4 608 octets qui correspondent
  pixel par pixel au PNG contribué.

- [x] **Step 6: valider et committer**

  Exécuter `make test`, `make test-vitest`, `git diff --check` et le lint
  ciblé, puis committer les fichiers précis avec
  `fix(fr): injecter les dessins des boîtes PC`.
