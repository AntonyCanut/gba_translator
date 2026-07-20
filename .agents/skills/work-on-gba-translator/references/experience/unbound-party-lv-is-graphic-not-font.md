---
name: unbound-party-lv-is-graphic-not-font
description: "CORRIGÉ : Party-menu « Lv » EST un glyphe-ligature de police (cp 0x05 @ ROM 0x1ECFA0), pas un graphique — F-113 s'était trompé"
metadata:
  node_type: memory
  type: project
  originSessionId: 337c482c-b2c8-479e-807a-1f812aa2d872
---

⚠️ **RENVERSEMENT (ticket enfant de F-113)** : le « Lv » de la liste d'équipe EST
un **glyphe-ligature de police** (codepoint **0x05**, pixels ROM à **0x1ECFA0**
dans la police non-compressée s@1EEF00), PAS un graphique de template. La
conclusion « graphique » de F-113 (ci-dessous) était FAUSSE.

**Pourquoi F-113 s'est trompé** : le glyphe {Lv}=0x05 est dessiné DIRECTEMENT par
le code du niveau (blit de glyphe fixe, SANS lecture de table de largeur). Donc le
read-watch des tables de largeur ne le voit jamais → F-113 a conclu « aucune police
ne rend Lv → graphique ». Mais un read-watch sur les DONNÉES DE GLYPHES
(0x1EC000–0x1ED780) attrape exactement UN glyphe lu sans mesure de largeur : 0x05
@ 0x1ECFA0. Calibration : glyph_base=0x1EAF00, stride 32 o (match 16/16 codepoints
Embrylex/10/♀/30//Annuler). Preuve directe : blanchir la zone de glyphes fait
disparaître « Lv » ET nom/chiffres, alors que le graphique « PV » (bloc LZ77
0x008001D0) SURVIT.

**RÉSOLU EN JEU** = `languages/fr/patches/party_lv_label.py` réécrit le glyphe
0x05 @ 0x1ECFA0 → « N. » (câblé build-fr après hp_labels). Vérifié : liste
d'équipe affiche **« N. 10 »**. La version canonique (mergée concurremment par le
ticket frère) **réutilise le vrai glyphe « N » de la ROM (cp 0xC8)** + point —
plus propre que redessiner « N. » à la main (ce que faisait ma 1re impl, cédée).
⚠️ format de glyphe FRLG NON-linéaire : `font.py:tile_to_pixels` NE le décode PAS
(pseudo-bruit) — voir docstring de party_lv_label.py pour la correspondance
octet→pixel. Copie secondaire du glyphe à **0x1EB580** (glyphe 0x34 {LV} table
principale) NON patchée par la version canonique — à vérifier si un texte FR
utilise le code {LV} brut.

---
**(HISTORIQUE — conclusion réfutée de F-113, conservée pour trace)** : F-113 avait
conclu « Lv » blit par fenêtre `0x08004aa4` call #0 source `r4=0x083D0070`, fond
dégradé LZ77 depuis `0x08B1BCE8`. Fix proposé (faux) : graphique comme
[[unbound-hp-pv-label-graphics-blocks]] / `hp_labels.py`. Suivi : ticket B-236.

**Infra réutilisable** (nouvelle) : `emulator-web/src/lua/bridge.lua` a maintenant
WATCHPOINT/BREAKPOINT/CLEARBP/WATCHHITS/CAP (mGBA ≥ 0.11), capture des registres
ARM sur hit ; client `mgba-bridge.ts` : `setWatchpoint/setRangeWatchpoint/`
`setBreakpoint/drainWatchHits`. Sondes : `scripts/probe_party_lv_{trace,source,
blit}.mts`, `probe_party_vram_dump.mts`. Cf. [[unbound-lv-level-abbreviation-fixes]].
