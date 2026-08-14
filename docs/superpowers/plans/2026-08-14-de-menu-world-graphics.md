# German Menu and World Graphics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build all German equivalents of the named French out-of-battle graphics and prove they survive the DE rebuild.

**Architecture:** Keep every bitmap and patch language-local. Reuse the existing indexed sprite inserter and the established German post-LZ77 dispatch, then verify the real built ROM by extracting pixels and decoding fixed strings.

**Tech Stack:** Python 3.11, pytest, indexed PNG, GBA 4bpp tiles, LZ77, YAML registry.

**Spec:** `docs/superpowers/specs/2026-08-14-de-menu-world-graphics-design.md`

## Global Constraints

- Never modify `input/roms/*.gba`.
- Preserve the original palette indices, tilemaps, offsets and compression capacities.
- German assets contain no French text; proper place names remain the English originals.
- All graphic patches run after `repair_lz77` and `repair_localized_lz77`.
- FR and IT sources, descriptors and build recipes remain unchanged.

---

### Task 1: German indexed menu sprites

**Files:**
- Create: `languages/de/sprites.py`
- Create: `languages/de/sprites/*.png`
- Create: `languages/de/patches/menu_sprites.py`
- Modify: `languages/de/lang.yaml`
- Test: `tests/unit/de/test_menu_graphics_assets.py`

**Interfaces:**
- Consumes: `scripts/insert_sprite.py --rom PATH --lang de --sprite NAME --image PATH`.
- Produces: the `menu_sprites` descriptor step and byte-idempotent DE sprite pixels.

- [ ] Write tests that import the DE registry, inspect exact dimensions/palette indices,
  run the real patch twice on a disposable ROM, and extract the resulting pixels.
- [ ] Run the test and confirm it fails because the DE registry/assets are absent.
- [ ] Create the indexed PNGs, registry and patch wrapper with the five exact German labels.
- [ ] Run the targeted test and confirm all non-ROM cases pass.
- [ ] Commit the source assets before the full ROM build.

### Task 2: German World Map fixed labels and actions

**Files:**
- Create: `languages/de/patches/world_map_action_labels.py`
- Create: `languages/de/patches/worldmap_labels.py`
- Modify: `languages/de/lang.yaml`
- Test: `tests/unit/de/test_world_map_graphics.py`

**Interfaces:**
- Consumes: English source bytes for the proper-name cells and the CFRU encoder for German actions.
- Produces: deterministic `apply()` functions and two post-build descriptor steps.

- [ ] Write failing tests for the German action cells, known pointer targets, source-name preservation and idempotency.
- [ ] Run them and verify the modules are missing.
- [ ] Implement the smallest German-only in-place patches.
- [ ] Run the tests and confirm exact CFRU decoding and unchanged neighboring bytes.
- [ ] Commit the patch sources.

### Task 3: Built-ROM parity and documentation

**Files:**
- Create: `docs/24_DE_MENU_WORLD_GRAPHICS.md`
- Modify: `tasks/todo.md`
- Test: `tests/unit/de/test_menu_graphics_assets.py`, `tests/unit/de/test_world_map_graphics.py`, existing DexNav/junction suites.

**Interfaces:**
- Consumes: `make build-de` output at `output/roms/GenedRom-de.gba`.
- Produces: a documented FR→DE parity matrix and ROM-level regression evidence.

- [ ] Build DE after checking for concurrent test runners.
- [ ] Extract and compare every versioned asset from the built ROM.
- [ ] Verify DexNav compression/ghost clearing and all ten junction panels.
- [ ] Run the focused suites, `make test-python-fast`, ruff and diff checks.
- [ ] Confirm FR/IT tracked sources and build artifacts were not changed.
- [ ] Record results in `tasks/todo.md`, commit, rebase and repeat tests if the base advanced.
