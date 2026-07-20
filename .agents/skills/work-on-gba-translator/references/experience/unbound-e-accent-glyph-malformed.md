---
name: unbound-e-accent-glyph-malformed
description: "é/è rendaient mal partout — glyphes de base malformés, patch_font_fr ne reconstruisait que à/ç"
metadata:
  node_type: memory
  type: project
  originSessionId: 30e06df1-e671-44f5-9b9d-a50cebbc893e
---

Ticket "Accent é" (B-96, branche test/pr, 2026-06-30) : l'accent é s'affichait mal
partout (screenshot "Pokémon" Pokédex).

**Cause racine** : le `patch_font_fr.py` (post-build, lancé par `make build-fr`)
ne reconstruisait QUE `à` (CP_GRAVE_A=0x16) et `ç` (CP_C_CEDILLA=0x19). Les
glyphes `é`(0x1B)/`è`(0x1A) venaient verbatim de la police internationale de base,
où ils sont **malformés** : l'accent aigu de é est dessiné trop haut (occupe 4 rangées),
ce qui écrase le corps du `e`. Vérifié : é dans la ROM FR = byte-identique à é dans
englishrom.gba → le build ne corrompt pas, c'est la police source.

**Fix RÉELLEMENT LANDÉ le 2026-07-01** sur branche `test/pr` (ticket « Accent é » B-96,
worktree Singularity) — les passes précédentes n'avaient jamais atteint `test/pr` :
le code n'y patchait toujours que à/ç. Cette fois committé pour de bon + ROM `output/roms/GenedRom-fr.gba`
rebuildée (`make prepare-fr && make build-fr`) et committée. Étendre `patch_font_fr.py`
pour reconstruire é (CP 0x1B) et è (CP 0x1A) depuis le corps propre du `e` (CP_E=0xD9)
+ l'accent compact de `á` (rows 0-1 seulement), exactement le mécanisme prouvé pour à.
Helpers partagés `acute_accent_positions`/`grave_shift`/`overlay_accent` (build_grave_a
refactoré dessus) ; alias largeur é/è = e dans patch_width_tables ; no-op si pas d'accent
source. Tests : `tests/test_font_patch.py::TestAccentedEGlyphs` (unit) +
`tests/e2e/test_accent_glyphs_fr.py` (decode du ROM buildé).

**Caveat non-évident** : en sortie de `make build-fr`, ~5 blocs police portent l'accent ;
1-2 copies dupliquées (ex 0x3C139C, 0x3BFBE4) sont RESTAURÉES en anglais par une passe
LZ77-repair APRÈS patch_font_fr → é/è (ET à) y redeviennent malformés. Ce ne sont PAS les
polices de rendu en jeu (à shippe et marche dans les 4 blocs propres). Donc la couverture
é/è = couverture à : on vérifie via `_a_grave_patched(font)` que le bloc a gardé à avant
d'asserter é/è. Ne pas chercher à "réparer" 0x3C139C — c'est attendu.

**Gotcha visualisation police** : les blocs LZ77 de police décompressent dans un
espace 4bpp permuté qui NE se visualise PAS naïvement (codepoint*32 + tile→pixels
donne du bruit). Mais c'est l'espace ENGINE correct : `glyph_pixels(font, codepoint)`
= codepoint*32 est ce que le moteur lit (prouvé car le patch à/ç marche en jeu).
Ne PAS perdre du temps à rendre les glyphes en PNG — raisonner sur les rangées
"accent (0-1) vs corps (2-7)" dans cet espace et comparer à un glyphe bon connu (á, à patché).

**Impact free-space** négligeable : +1 relocation, +2112 o vs ~1.2 Mo libre (allocator
remplit les grandes régions d'abord). Voir [[unbound-font-patch-freespace-cascade]] (F-50).
Le build FR vit dans gba_translator [[unbound-fr-build-lives-in-gba-translator]] ;
ROM régénérée par CI release.yml sur push unbound/master.
