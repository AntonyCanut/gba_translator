---
description: Construit la ROM française (make build-fr) puis enchaîne les patchs post-build
---

Construis la ROM FR depuis la dernière traduction prête.

1. Vérifie qu'un `output/translation/*_translation_ready.json` existe (sinon, signale-le).
2. Lance `make build-fr` — cette cible enchaîne : build générique →
   `patch_font_fr` → `patch_fixed_table_names` → `patch_time_format_fr` →
   `apply_inline_overrides_fr` → `repair_*_lz77_blocks` →
   `repoint_stale_text_pointers` → `patch_pokedex_fr`.
3. Confirme que `output/roms/GenedRom-fr.gba` a bien été (re)généré.
4. Ne modifie jamais `input/roms/`. Rapporte tout patch qui échoue avec sa cause.

$ARGUMENTS
