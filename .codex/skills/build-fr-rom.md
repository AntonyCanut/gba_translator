# Skill : build-fr-rom

**Quand** : construire/reconstruire la ROM française de bout en bout.

## Pré-requis
- `output/translation/*_translation_ready.json` à jour (chaîne
  `combined_fr.txt → CSV trilingue → json`).
- ROMs sources présentes (`make verify-roms`). `input/roms/` = lecture seule.

## Étapes
1. `make build-fr` — build générique puis patchs post-build automatiques :
   `patch_font_fr → patch_fixed_table_names → patch_time_format_fr →
   apply_inline_overrides_fr → repair_stable_lz77_blocks →
   repair_localized_lz77_blocks → repoint_stale_text_pointers → patch_pokedex_fr`.
2. Vérifier chaque patch (arrêt au premier échec → cause racine → relancer).
3. Audit traduction : orthographe, toponymes, glyphes police, placeholders positionnels,
   synchro des 3 sources.
4. `make test-playwright` sur les specs concernées.

## Garde-fous
- Sortie dans `output/` seulement. Sonde mGBA : sessions courtes + savestates, **jamais**
  sauvegarder en jeu. 100 % de réussite, pas de skip ni de fix hardcodé.
