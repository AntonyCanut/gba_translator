# DE English Toponyms Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore every German-build place name covered by the English canon to the exact English spelling across source text, map surfaces, signs, regional descriptions, and live ROM pointers.

**Architecture:** Keep German prose but replace only source-anchored proper-place spans in `combined_de.txt`. Make the existing map patches language-data-driven, add thin DE wrappers for missing zone/map layers, and verify both source values and the built ROM through live pointers.

**Tech Stack:** Python 3.11, pytest, YAML, CFRU text codec, generic DE ROM pipeline.

**Spec:** Ticket “DE — Conserver les noms originaux des villes et lieux”.

## Global Constraints

- English ROM bytes are the canonical spelling authority.
- Preserve control-code order, line breaks, page breaks, and arrow glyph placement.
- Match only named places anchored by the corresponding English source entry; never replace ambiguous common nouns globally.
- Do not modify French or Italian content.
- Edit only last-wins DE translation entries and protect every changed offset.

---

### Task 1: Canon and source audit

**Files:**
- Create: `languages/de/data/english_toponyms.yaml`
- Create: `tests/unit/de/test_english_toponyms_de.py`
- Modify: `languages/de/combined_de.txt`
- Modify: `languages/de/protected_entries.yaml`

**Interfaces:**
- Consumes: paired EN/DE entries and English ROM strings.
- Produces: canonical records containing English spelling, aliases, source offsets, and surface type.

- [ ] Write tests proving the catalog decodes exactly from the English ROM, source replacements are last-wins, and German common nouns outside source-anchored entries are untouched.
- [ ] Run the focused tests and confirm failure because the catalog/source corrections do not exist.
- [ ] Add the smallest canonical data set covering cities, routes, dungeons, buildings, regions, special places, signs, and regional blurbs.
- [ ] Apply surgical last-occurrence corrections to `combined_de.txt` and protect the offsets.
- [ ] Re-run the focused tests.

### Task 2: Deliver all map layers

**Files:**
- Modify: `languages/fr/patches/worldmap_junction_panels.py`
- Modify: `languages/fr/patches/worldmap_labels.py`
- Modify: `languages/fr/patches/zone_names.py`
- Create: `languages/de/patches/worldmap_labels.py`
- Create: `languages/de/patches/zone_names.py`
- Modify: `languages/de/lang.yaml`
- Modify: `tests/unit/test_patch_de_wrappers.py`
- Modify: `tests/test_patch_worldmap_labels_fr.py`
- Modify: `tests/test_patch_zone_names_fr.py`

**Interfaces:**
- Consumes: last-wins `--combined` values.
- Produces: exact language-specific verification of in-place and relocated map strings.

- [ ] Add failing tests showing the shared patches reject non-FR values and DE lacks two wrappers.
- [ ] Change verification to compare against the actual combined value at each target.
- [ ] Add thin DE wrappers and tail-order their steps before collision audit.
- [ ] Re-run focused FR/DE patch tests.

### Task 3: Live-pointer and sign audit

**Files:**
- Create: `scripts/audit_english_toponyms_de.py`
- Create: `tests/e2e/de/test_english_toponyms.py`
- Modify: `Makefile`

**Interfaces:**
- Consumes: canonical YAML, English ROM, built DE ROM.
- Produces: non-zero exit for a translated/FR place alias, dead/misdirected pointer, unterminated panel, changed control topology, or mid-line arrow.

- [ ] Write the failing source/ROM audit tests first.
- [ ] Implement the audit using English pointer sites and direct-label offsets.
- [ ] Register a DE ROM audit target and run focused tests.
- [ ] Build DE and verify decoded bytes, pointer liveness, terminators, and arrow positions.

### Task 4: Regression and completion gates

**Files:**
- Modify: `tasks/todo.md`

**Interfaces:**
- Consumes: completed implementation and built ROM.
- Produces: clean commit ready for orchestrated rebase/integration.

- [ ] Run translation integrity, focused ROM audit, full Python suite, and DE build verification.
- [ ] Confirm no FR/IT content diff and review every changed DE offset.
- [ ] Commit with `fix(de): restore English place names` and verify the worktree is clean.

