# Description CT108 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restaurer la description complète de la CT108 et empêcher tout fragment court de CT/CS d’être classé comme sain.

**Architecture:** Le patch post-build existant compare la description encodée vivante à la dernière valeur canonique de `combined_fr.txt`. Seules les divergences sont relocalisées et repointées.

**Tech Stack:** Python 3.11, pytest, encodage CFRU, ROM GBA.

## Global Constraints

- Aucun cas spécial par item ou offset.
- Ne pas modifier `input/roms/`.
- Conserver le terminateur CFRU `0xFF` et l’idempotence du patch.
- Vérifier le résultat en décodant le pointeur vivant de la ROM construite.

---

### Task 1: Reproduire le fragment court terminé

**Files:**
- Modify: `tests/e2e/fr/test_tm_item_desc_freeze.py`

**Interfaces:**
- Consumes: table objets `0x876074`, stride 44, pointeur description `+0x14`.
- Produces: garde `test_ct108_description_is_complete`.

- [ ] **Step 1: Write the failing test**

Ajouter une assertion littérale sur le texte vivant de CT108 :

```python
assert _decode_description(fr_rom, "CT108") == (
    "Aboie menaçant.\nBaisse aussi\nl'Att. Spé\nennemie."
)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/e2e/fr/test_tm_item_desc_freeze.py -q`

Expected: FAIL avec le fragment actuel « nsi sa statistique de vitesse. ».

### Task 2: Corriger la classification du patch

**Files:**
- Modify: `languages/fr/patches/tm_item_descriptions.py`
- Create: `tests/unit/fr/test_tm_item_descriptions.py`

**Interfaces:**
- Consumes: `combined: dict[int, str]`, `_normalize()`, `TextEncoder`.
- Produces: `apply()` qui conserve uniquement une description byte-identique à sa valeur canonique.

- [ ] **Step 1: Write the failing unit test**

Construire une ROM synthétique contenant `CT108`, un pointeur dans la région
packée, le fragment court `nsi sa statistique de vitesse.` et la valeur
canonique complète dans `combined`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/fr/test_tm_item_descriptions.py -q`

Expected: FAIL car `relocated == 0` et le pointeur n’est pas modifié.

- [ ] **Step 3: Write minimal implementation**

Encoder d’abord la valeur canonique, comparer `rom[ptr:ptr + len(encoded)]`
à cette valeur, puis relocaliser seulement en cas de divergence.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/fr/test_tm_item_descriptions.py tests/e2e/fr/test_tm_item_desc_freeze.py -q`

Expected: test unitaire PASS ; le garde ROM reste rouge avant rebuild.

### Task 3: Livrer et vérifier la ROM

**Files:**
- Modify: `output/roms/GenedRom-fr.gba`
- Modify: `tasks/todo.md`

**Interfaces:**
- Consumes: `languages/fr/combined_fr.txt`, pipeline `make build-fr`.
- Produces: CT108 repointée vers une description CFRU complète et terminée.

- [ ] **Step 1: Commit source and tests before build**

Run: `git add <fichiers précis> && git commit -m "fix(fr): réparer les descriptions CT tronquées"`

- [ ] **Step 2: Build and verify**

Run: `make build-fr`

Expected: build réussi et garde CT108 verte.

- [ ] **Step 3: Run broader validation**

Run: `make test && make test-vitest && make test-rom`

Expected: 100 % de réussite.

- [ ] **Step 4: Commit generated ROM and review**

Run: `git add output/roms/GenedRom-fr.gba tasks/todo.md && git commit -m "build(fr): reconstruire la ROM avec la CT108 corrigée"`

Expected: arbre propre et diff limité au correctif, aux tests, au suivi et à la ROM.
