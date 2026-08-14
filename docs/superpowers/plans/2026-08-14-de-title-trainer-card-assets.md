# German Title and Trainer Card Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produire et injecter les écrans titre et Carte Dresseur allemands sans modifier les variantes FR/IT.

**Architecture:** Un générateur DE reconstruit trois images indexées depuis les ressources exactes de la ROM anglaise, puis ne remplace que les rectangles de libellés par « START DRÜCKEN », « TRAINERPASS » et « LIGA-ORDEN ». Un patch DE réinjecte ces images après les réparations LZ77 à travers le moteur graphique existant et les tests relisent les pointeurs vivants de la ROM.

**Tech Stack:** Python 3.11, PNG/BMP indexés, tuiles GBA 4/8 bpp, LZ77, pytest, GNU Make.

**Spec:** Ticket « DE — Produire les assets titre et Carte Dresseur ».

## Global Constraints

- Ne modifier aucun asset ni aucune ROM FR/IT.
- Conserver palettes, dimensions, transparence, tuiles partagées et pointeurs connus.
- Exécuter l’insertion après `repair_lz77` et `repair_localized_lz77`.
- Vérifier chaque écran dans `output/roms/GenedRom-de.gba` via sa grille mappée vivante.

---

### Task 1: Gardes graphiques DE

**Files:**
- Create: `tests/unit/de/test_screen_graphics_de.py`
- Create: `languages/de/sprites.py`

**Interfaces:**
- Consumes: `src.graphics.sprite_rom.extract_mapped_block` et le registre FR éprouvé.
- Produces: `SPRITES: dict[str, SpriteDef]` pour les trois écrans DE.

- [ ] Écrire les tests qui exigent les trois définitions, les dimensions 256 × 160, les profondeurs 4/8 bpp, les palettes et pointeurs attendus.
- [ ] Lancer `python3 -m pytest tests/unit/de/test_screen_graphics_de.py -q` et constater l’échec dû au registre/aux assets absents.
- [ ] Ajouter le registre DE minimal, sans modifier `languages/fr/sprites.py`.
- [ ] Relancer la garde ciblée et conserver les échecs d’assets attendus pour le cycle suivant.

### Task 2: Sources éditables et reproductibles

**Files:**
- Create: `languages/de/tools/build_screen_assets.py`
- Create: `languages/de/sprites/{title_screen,trainer_card_front,trainer_card_back}.{png,bmp}`
- Modify: `tests/unit/de/test_screen_graphics_de.py`

**Interfaces:**
- Consumes: `build_assets(source_rom: Path, output_dir: Path) -> tuple[Path, ...]` et `LABELS`.
- Produces: six images indexées dont les grilles PNG/BMP sont identiques.

- [ ] Tester `LABELS == {title_screen: START DRÜCKEN, trainer_card_front: TRAINERPASS, trainer_card_back: LIGA-ORDEN}`.
- [ ] Tester qu’une reconstruction temporaire est pixel-identique aux six assets versionnés et qu’aucun pixel hors rectangle de libellé ne diffère de l’extraction EN.
- [ ] Exécuter la garde et constater l’échec dû au générateur absent.
- [ ] Implémenter le générateur avec extraction ROM existante, police bitmap déterministe et écriture indexée PNG/BMP.
- [ ] Générer les six sources, puis faire passer les gardes de reproductibilité.

### Task 3: Patch build-de et preuve ROM

**Files:**
- Create: `languages/de/patches/screen_graphics.py`
- Modify: `languages/de/lang.yaml`
- Modify: `tests/unit/de/test_screen_graphics_de.py`
- Modify: `tasks/todo.md`

**Interfaces:**
- Consumes: `apply_to_rom(rom_path: Path) -> int` et les trois assets PNG.
- Produces: trois écrans réinjectés dans la ROM DE, après les réparations LZ77.

- [ ] Tester l’ordre déclaratif du patch, l’idempotence, les backups et la lecture des trois grilles vivantes.
- [ ] Exécuter les gardes et constater l’échec dû au patch/à l’étape absents.
- [ ] Implémenter le patch DE avec `read_indexed_image`, `insert_mapped_block` et écriture atomique sauvegardée.
- [ ] Ajouter `screen_graphics` après les réparations LZ77 dans `languages/de/lang.yaml`.
- [ ] Construire DE deux fois, comparer les ROMs, puis exécuter les tests ciblés, `make test-python`, `ruff check` et les vérifications ROM DE.
- [ ] Vérifier que `git diff` ne contient aucun chemin `languages/fr`, `languages/it`, ni ROM FR/IT, puis committer.
