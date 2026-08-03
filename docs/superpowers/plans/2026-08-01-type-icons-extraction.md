# Type Icons Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exporter les deux planches d’icônes de types en PNG indexés éditables et réinjectables.

**Architecture:** Déclarer séparément les deux planches brutes dans le registre FR existant afin de réutiliser sans duplication les CLI génériques et les codecs 4 bpp. Versionner les deux exports parce que leurs dimensions, leurs pixels et l’emplacement du type Fée diffèrent.

**Tech Stack:** Python 3.11, pytest, codecs PNG indexé et tuiles GBA internes.

## Global Constraints

- Ne jamais modifier `input/roms/`.
- Conserver deux images distinctes : résumé 128 × 152, combat 128 × 104.
- Les images sont des PNG indexés limités aux indices 0 à 15.
- La réinjection doit passer par le CLI existant et créer une sauvegarde `.bak`.

---

### Task 1: Déclarer les planches de types

**Files:**
- Modify: `languages/fr/sprites.py`
- Create: `tests/unit/test_type_icons_editable_assets.py`

**Interfaces:**
- Consumes: `SpriteDef(blocks, tiles_wide, tiles_tall, compressed)`.
- Produces: `SPRITES["type_icons_summary"]` et `SPRITES["type_icons_battle"]`.

- [x] **Step 1: Écrire le test rouge du registre**

```python
def test_type_icons_registry_exposes_both_raw_sheets() -> None:
    assert SPRITES["type_icons_summary"].blocks == (0x00B1EC64,)
    assert SPRITES["type_icons_battle"].blocks == (0x00961A00,)
    assert SPRITES["type_icons_summary"].tiles_tall == 19
    assert SPRITES["type_icons_battle"].tiles_tall == 13
```

- [x] **Step 2: Vérifier l’échec attendu**

Run: `python3 -m pytest tests/unit/test_type_icons_editable_assets.py -q`
Expected: échec `KeyError: 'type_icons_summary'`.

- [x] **Step 3: Ajouter l’entrée minimale au registre**

```python
"type_icons_summary": SpriteDef(
    blocks=(0x00B1EC64,),
    tiles_wide=16,
    tiles_tall=19,
    compressed=False,
),
"type_icons_battle": SpriteDef(
    blocks=(0x00961A00,),
    tiles_wide=16,
    tiles_tall=13,
    compressed=False,
),
```

- [x] **Step 4: Vérifier le passage au vert**

Run: `python3 -m pytest tests/unit/test_type_icons_editable_assets.py -q`
Expected: réussite du test du registre.

### Task 2: Livrer et vérifier les PNG éditables

**Files:**
- Create: `languages/fr/sprites/type_icons_summary.png`
- Create: `languages/fr/sprites/type_icons_battle.png`
- Modify: `tests/unit/test_type_icons_editable_assets.py`
- Modify: `tasks/todo.md`

**Interfaces:**
- Consumes: `scripts/extract_sprite.py`, `scripts/insert_sprite.py`, `read_indexed_image`.
- Produces: deux images indexées dont les indices peuvent être réinjectés sans perte.

- [x] **Step 1: Ajouter les gardes rouges d’assets et de round-trip**

```python
def test_type_icon_assets_are_indexed_sheets() -> None:
    for name, height in (("type_icons_summary", 152), ("type_icons_battle", 104)):
        width, actual_height, grid = read_indexed_image(SPRITES_DIR / f"{name}.png")
        assert (width, actual_height) == (128, height)
        assert all(0 <= pixel <= 15 for row in grid for pixel in row)
```

- [x] **Step 2: Vérifier l’échec attendu sur les fichiers absents**

Run: `python3 -m pytest tests/unit/test_type_icons_editable_assets.py -q`
Expected: échec `FileNotFoundError` pour `type_icons_summary.png`.

- [x] **Step 3: Extraire les deux planches de la ROM FR**

```bash
python3 scripts/extract_sprite.py --rom output/roms/GenedRom-fr.gba \
  --lang fr --sprite type_icons_summary \
  -o languages/fr/sprites/type_icons_summary.png
python3 scripts/extract_sprite.py --rom output/roms/GenedRom-fr.gba \
  --lang fr --sprite type_icons_battle \
  -o languages/fr/sprites/type_icons_battle.png
```

- [x] **Step 4: Vérifier le round-trip et les validations élargies**

Run: `python3 -m pytest tests/unit/test_type_icons_editable_assets.py tests/unit/test_sprite_rom.py tests/unit/test_sprite_png.py tests/unit/test_insert_sprite_safety.py tests/test_type_icons_fr.py -q`
Expected: tous les tests réussissent.

Run: `make test-python-fast`
Expected: 100 % de réussite.

Run: `ruff check languages/fr/sprites.py tests/unit/test_type_icons_editable_assets.py`
Expected: aucun diagnostic.

### Task 3: Intégrer les retouches fournies dans le build FR

**Files:**
- Modify: `languages/fr/sprites/type_icons_summary.png`
- Modify: `languages/fr/sprites/type_icons_battle.png`
- Modify: `tests/unit/test_type_icons_editable_assets.py`
- Modify: `Makefile`
- Modify: `tasks/todo.md`

**Interfaces:**
- Consumes: les deux BMP 4 bpp joints au commentaire GitHub #156.
- Produces: une ROM FR dont les deux blocs bruts correspondent pixel par pixel
  aux PNG versionnés.

- [x] **Step 1: Ajouter les gardes rouges du build**

Ajouter un test rapide exécutant `make -n build-fr` et exigeant les deux appels
à `scripts/insert_sprite.py`, puis un test `rom` qui extrait les deux blocs de
`output/roms/GenedRom-fr.gba` et les compare aux assets.

Run: `python3 -m pytest tests/unit/test_type_icons_editable_assets.py -q`
Expected: échec car la recette ne contient encore aucune insertion des icônes.

- [x] **Step 2: Convertir les BMP sans perte**

Lire chaque BMP avec `read_indexed_image`, écrire son PNG avec
`write_indexed_image`, puis relire les deux formats et exiger l’égalité des
dimensions et de chaque indice 0–15.

- [x] **Step 3: Câbler les deux insertions**

Ajouter les commandes `type_icons_summary` et `type_icons_battle` juste après
`$(PATCH_TYPE_ICONS_SCRIPT)` dans `build-fr`, afin que les retouches manuelles
prennent la priorité sur le rendu procédural.

- [x] **Step 4: Vérifier le passage au vert et la ROM**

Run: `python3 -m pytest tests/unit/test_type_icons_editable_assets.py -q`
Expected: réussite des tests rapides.

Run: `make build-fr && python3 -m pytest tests/unit/test_type_icons_editable_assets.py -q -m rom`
Expected: les deux grilles extraites de la ROM correspondent aux PNG.
