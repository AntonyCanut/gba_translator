# DE Battle And Summary Graphics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Versionner puis réinjecter de façon déterministe tous les graphismes allemands des écrans combat, équipe et résumé.

**Architecture:** Le registre `languages/de/sprites.py` décrit les fenêtres de tuiles réellement lues par le moteur. Un patch DE unique consomme les PNG indexés versionnés et les réinjecte après les réparations LZ77, tandis que les générateurs existants restent la source déterministe permettant de régénérer les rasters.

**Tech Stack:** Python 3.11, tuiles GBA 4 bpp, LZ77, PNG/BMP indexés, pytest, mGBA/Playwright.

**Spec:** Ticket F-604 — DE — Produire les assets graphiques combat et résumé.

## Global Constraints

- Aucun texte EN/FR résiduel ni queue de glyphes dans les surfaces couvertes.
- Préserver dimensions, indices de palette, tilemaps, compression, offsets et copies divergentes.
- Exécuter la réinjection après `repair_lz77` et `repair_localized_lz77`.
- Ne modifier que les sources DE et `output/roms/GenedRom-de.gba`.

---

### Task 1: Contrat des assets et gardes rouges

**Files:**
- Create: `tests/unit/de/test_battle_summary_graphics_assets.py`
- Modify: `languages/de/sprites.py`
- Modify: `languages/de/lang.yaml`

**Interfaces:**
- Consumes: `SpriteDef`, `extract_block()`, `read_indexed_image()`.
- Produces: noms de sprites DE, géométries et ordre de patch vérifiés.

- [x] Écrire les tests qui exigent les assets PNG/BMP indexés, toutes les copies, leurs dimensions et l’ordre post-LZ77.
- [x] Lancer le fichier ciblé et confirmer l’échec dû aux assets/entrées manquants.
- [x] Déclarer uniquement les fenêtres de tuiles nécessaires dans `languages/de/sprites.py`.
- [x] Relancer le fichier ciblé jusqu’au vert.

### Task 2: Sources raster et réinjection déterministe

**Files:**
- Create: `languages/de/patches/battle_summary_sprites.py`
- Create: `languages/de/sprites/{status_badges,type_icons_*,party_kp,summary_kp,battle_kp-*,summary_stat_labels}.{png,bmp}`
- Modify: `scripts/build_language.py`

**Interfaces:**
- Consumes: le registre DE et les PNG indexés générés depuis la ROM DE corrigée.
- Produces: `apply_to_rom(rom_path, asset_dir) -> int`, patch idempotent de toutes les copies.

- [x] Étendre les tests afin d’exiger l’identité pixel/tuile entre assets et ROM.
- [x] Confirmer l’échec avant création des rasters et du patch.
- [x] Extraire les fenêtres depuis la sortie déterministe des générateurs DE, écrire PNG et BMP avec le codec indexé du dépôt.
- [x] Implémenter le patch qui valide toutes les images avant d’écrire et réinjecte chaque copie.
- [x] Brancher `battle_summary_sprites` après les deux réparations LZ77 et les générateurs graphiques DE.
- [x] Relancer les tests ciblés jusqu’au vert.

### Task 3: Validation ROM et captures ciblées

**Files:**
- Modify: `tasks/todo.md`
- Modify: `output/roms/GenedRom-de.gba`
- Modify/Create: captures Playwright DE ciblées si le harness disponible les produit.

**Interfaces:**
- Consumes: `make build-de`, tests ROM pixel/tuile, probes mGBA existantes.
- Produces: ROM DE reconstruite et preuves reproductibles.

- [ ] Construire DE puis comparer chaque fenêtre extraite aux assets versionnés.
- [ ] Vérifier l’idempotence du patch et l’absence de pixels anglais/français connus.
- [ ] Exécuter les tests ciblés, la suite Python/Vitest et les scénarios mGBA disponibles.
- [ ] Vérifier que les ROM FR/IT et leurs assets restent inchangés.
- [ ] Relire le diff, consigner les preuves, committer et intégrer sans push.
