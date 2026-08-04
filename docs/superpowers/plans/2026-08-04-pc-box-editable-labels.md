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

  Expected: PASS, puis réinjection dans une copie temporaire et comparaison
  byte-identique des 4 608 octets décompressés.

- [x] **Step 5: valider et committer**

  Exécuter la suite rapide, le lint ciblé et `git diff --check`, puis committer
  avec `feat(fr): extraire les dessins des boîtes PC`.
