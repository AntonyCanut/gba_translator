---
name: unbound-ellipsis-pause-b0-glyph
description: "Restaurer une pause/ellipse en jeu = octet brut <0xB0> (1 o, byte-fidèle EN), PAS « … » (3 o) ni suppression ; sinon débordement → relocalisations → épuisement marge free-space → régression panneaux Carte du monde"
metadata:
  node_type: memory
  type: project
  originSessionId: f76bdc1a-92b7-46f7-87b4-c73f518b04b8
---

R-09 follow-up #2 (commits a45c8c0 → 2e4d829 → 675b753, branche unbound).

**Le bug utilisateur :** un dialogue affichait un guillemet seul (« Bref" tu
vois, ils détestent quand les gens fouinent »). C'est une ex-ellipse : l'anglais
utilise l'octet **0xB0** (glyphe « … » de la police FireRed/CFRU) pour la pause
« Anyway… », décodée en `"` droit puis ré-encodée en vrai guillemet 0xB1/0xB2.

**R-09 avait SUPPRIMÉ ces guillemets** (`clean_wordless_quotes_fr.py`, d1aaa6f) —
jetant la pause voulue. L'utilisateur : « ça aurait dû rester … ». La bonne forme
est l'ellipse.

**Comment restaurer (LEÇON CLÉ) :** écrire l'octet **brut `<0xB0>`** dans
combined_fr (rendu « … »), PAS `…`/`...`. L'encodeur développe `…`→`...`=3×0xad
(3 o) — voir [[unbound-ellipsis-no-single-byte]] (qui dit qu'aucun glyphe ellipse
1-octet n'est ÉMIS par l'encodeur ; mais on peut écrire la forme brute `<0xB0>`).
`<0xB0>` = 1 o = même taille que le guillemet remplacé → l'entrée reste **en
place**, zéro free-space consommé. La forme 3 o faisait déborder ~30 entrées →
relocalisation de la chaîne ENTIÈRE en free space. `restore_ellipsis_pauses_fr.py`
rejoue le diff d1aaa6f, écrit `<0xB0>` (runs réduits à 1). Audit JSON+EN : 1 seule
ex-ellipse hors combined_fr (0x1F2D412, ajoutée). 0xB0 n'est PLUS un bug guillemet
depuis 3ab66ad (`«»` → 0xB1/0xB2) ; test_quote_glyphs_fr ne vise que Zygarde/
montagne, donc des `<0xB0>` ailleurs ne le cassent pas. Voir
[[unbound-straight-quote-is-ex-ellipsis]], [[unbound-guillemets-render-as-ellipsis]].

**Marge free-space RAZOIR (~5 Ko) — toute relocalisation en plus régresse.**
`FreeSpaceAllocator` (src/core/text_reinserter.py) n'alloue que les runs 0xFF
≥1024 o et EXCLUT 0x230000-0x500000 + 0x1000000-0x1FE0000 (donc le gros bloc de
344 Ko et toute la région texte 0x1Fxxxxx sont hors allocation). À b29b016 il
restait 1 bloc de 5130 o après build ; mes ellipses 3-o l'avaient mis à 0 →
`patch_worldmap_junction_panels_fr.py` (tourne tard, ligne ~65 du Makefile)
échouait « ÉCHECS (free space) : 8 » → 8 panneaux Carte du monde restaient
anglais (B-76 régressé). Mesurer : `FreeSpaceAllocator(rom, reserved_rom=ES).blocks`
= liste de `[start, length]`. Vérifier les panneaux : `wm.verify(rom)`.

**Deux fragilités de build exposées par les relocalisations (corrigées) :**
- `repoint_stale_text_pointers.py` : relocaliser la chaîne 0x09f62908 (« I swam,
  of course! ») fait que le repointeur réécrit TOUTES les occurrences de cette
  valeur — dont les fenêtres `setflag` du rituel (faux positifs). Le veto
  `_is_setflag_chain` lisait la ROM VIVANTE (perturbée par les étapes inline/LZ77
  avant le repoint) et ratait 0x1e5db34. Fix : veto sur la **source anglaise**
  (bytecode jamais traduit) via nouveau param `--source` (défaut englishrom).
- `patch_legendary_ritual_fr.py` : ne réparait que le clobber connu 0x08C277E1 ;
  or l'adresse relocalisée VARIE selon la disposition free-space. Fix : sur un
  site setflag découvert (signature CANON `08 29 F6 09` précédé de 0x29), restaurer
  le canonique pour TOUT clobber ressemblant à un pointeur GBA. Voir
  [[unbound-hooh-lugia-ritual-repointer-corruption]].

Tests : `test_restore_ellipsis_pauses_fr.py`, `tests/e2e/test_ellipsis_pauses_fr.py`
(0x1F2D412 porte 0xB0, zéro 0xB1/0xB2 ; runs réduits). [[unbound-fr-build-lives-in-gba-translator]]
