---
name: build-fr-rom
description: Use when building or rebuilding the French ROM of Pokémon Unbound end-to-end — from a translation_ready.json through make build-fr, the post-build patch chain, and validation.
---

# Construire la ROM française

Procédure de bout en bout pour produire `output/roms/GenedRom-fr.gba`.

## Pré-requis
- Un `output/translation/*_translation_ready.json` à jour (issu de la chaîne
  `combined_fr.txt → CSV trilingue → json`). Si absent, le générer d'abord.
- Les ROMs sources `input/roms/englishrom.gba` et `spanishrom.gba` présentes (lecture
  seule, vérifiées par `make verify-roms`).

## Étapes
1. `make build-fr` — build générique puis enchaînement automatique des patchs :
   `patch_font_fr` → `patch_fixed_table_names` → `patch_time_format_fr` →
   `apply_inline_overrides_fr` → `repair_stable_lz77_blocks` →
   `repair_localized_lz77_blocks` → `repoint_stale_text_pointers` → `patch_pokedex_fr`.
2. Vérifier que chaque patch s'est appliqué sans erreur (la cible s'arrête au premier
   échec ; lire le message, corriger la cause racine, relancer).
3. Contrôle qualité de la traduction : déléguer à l'agent `translation-verifier`
   (orthographe, toponymes, glyphes, placeholders, synchro 3 sources).
4. Validation comportementale : `make test-playwright` sur les specs touchées (boot,
   gameplay, translation, visual-regression).

## Garde-fous
- Ne jamais modifier `input/roms/`. Tout sort dans `output/`.
- Sonde mGBA : sessions courtes + savestates, **ne jamais sauvegarder en jeu** (écrase la
  fixture `.sav` et casse les goldens Playwright).
- 100 % de réussite attendu ; pas de skip ni de fix hardcodé.
