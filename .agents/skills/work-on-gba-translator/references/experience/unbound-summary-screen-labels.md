---
name: unbound-summary-screen-labels
description: "Page Infos Pokémon — labels graphiques vs texte, pointeurs dupliqués, bug PE/T/EM"
metadata:
  node_type: memory
  type: project
  originSessionId: d2f16fef-bcbd-47bd-b583-b7bb74b28b57
---

Page « Infos Pokémon » (résumé Pokémon) d'Unbound FR.

**Mécanisme mixte** :
- `No` / `NAME` / `IDNo` / `Lv.` = chaînes texte CFRU (~0x4160EA région, ex. `IDNo.`@0x416104).
- **`TYPE` / `OT` / `ITEM` = images de mots cuites** (word-images), PAS du texte. Les
  glyphes vivent dans le bloc LZ77 `0xE9A460` (512 tuiles, ptr `0x135FFC`), chargé en
  charblock-0. Un tilemap (`0xE9BA30`) + tileset localisé (`0xE9B598`) positionnent/
  découpent ces tuiles.

**Bug PE/T/EM (le correctif précédent passait les tests mais restait invisible en jeu)** :
`repair_localized_lz77_blocks.py` écrase tilemap+tileset EN par les versions ESPAGNOLES
en place (le tilemap ES référence des tuiles charblock-1 >= 512 → mauvaise VRAM →
labels = queues des mots EN : tyPE→PE, oT→T, itEM→EM). Le tilemap/tileset sont
référencés par **PLUSIEURS pointeurs dupliqués** ; la page info se rend via le **second**
groupe. Repointer TOUS : tilemap `0x135B54`+`0x135D8C` ; tileset `0x135B34`+`0x135DBC`
+`0x13B5EC` (jeux complets trouvés en scannant la ROM pour `0x08E9BA30`/`0x08E9B598`).
`patch_summary_labels_fr.py` les repointe tous vers une copie EN relocalisée. Le restore
en place échoue (EN recompressé 382/391 o > slot ES 348/330 o) → relocalisation obligatoire.

**Traduction FR des mots (Dress/Objet) = suivi non fait** : éditer le bloc word-image
`0xE9A460` (pixel art ; glyphes `B`,`J` absents de la police de labels) — risqué, repoussé.

**Nav e2e mGBA jusqu'au résumé** (depuis overworld) : `START` → `RIGHT` (Pokémon) →
`A` (liste) → `A` (menu contextuel) → `A` (Résumé), avec ~70-90 frames de pause/étape.
Détection écran résumé : `DISPCNT & 0x0F00 == 0x0F00` (4 BG actifs). Voir
`tests/e2e/test_summary_screen_render.py` + `test_summary_screen_labels.py`.
Voir aussi [[unbound-fr-build-lives-in-gba-translator]], [[unbound-mgba-probe-quirks]].
