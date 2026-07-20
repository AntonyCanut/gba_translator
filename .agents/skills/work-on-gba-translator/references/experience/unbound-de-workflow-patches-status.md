---
name: unbound-de-workflow-patches-status
description: État du workflow/patches DE (allemand) au 2026-07-03 — ce qui est déjà générique vs le trou de parité FR restant (F-83)
metadata:
  node_type: memory
  type: project
  originSessionId: bfcf7640-a8f5-4283-86aa-e545eb4f3970
---

F-70 (traduction allemande) a un workflow de build déjà solide, pas juste des batches de texte brut : `scripts/build_language.py` + `languages/de/lang.yaml` (gba_translator, branche `unbound`) câblent déjà pour DE : font (glyphes ä ö ü ß via patch_font_de.py), inline overrides, anti-freeze repair_lz77/repair_localized_lz77/repoint_stale, legendary_ritual, status_abbrevs (GIF/VBR/GEF/PAR/SCH/KO officiels), version (bandeau DE.2.0.<build>). Deux hooks génériques existent en plus (tm_item_descriptions, move_descriptions) mais pas encore activés dans lang.yaml DE — prêts dès que ces zones seront traduites.

**Why:** le driver generic build_language.py (déjà utilisé pour IT) est réutilisé tel quel pour DE — pas de code dupliqué, patches paramétrés par langue.

**Trou restant :** ~10 patches spécifiques FR (Pokédex catégories/fiches, labels HP/PS graphiques, icônes de type, badges statut LZ77 combat, en-têtes DexNav, date carte dresseur, descriptions mission, panneaux jonction carte du monde, tables fixes noms talents/objets, suppression pronom genré) ne sont PAS généralisés pour DE. Formalisé dans le ticket de suivi **F-83**, à démarrer seulement après que combined_de.txt soit complet (batches F-72→F-82) — le calibrage dépend du texte allemand final (mots généralement plus longs qu'EN/FR). `.github/workflows/release.yml` ne build que FR+IT ; ajouter DE en continue-on-error une fois `status: complete` dans lang.yaml.

**How to apply:** avant de dire "DE workflow pas pensé", vérifier `languages/de/lang.yaml` (liste `patches:`) et `scripts/build_language.py` (dispatch `apply_patches`) dans gba_translator — c'est là que vit la vérité, pas dans ce repo Test/Unbound. Voir aussi [[unbound-multilang-build-registry]], [[unbound-de-batch-fixed-window-not-skip-existing]], [[unbound-fr-build-lives-in-gba-translator]].
