---
name: unbound-start-menu-move-hint-baked-lz77-graphic
description: "START-menu \"SELECT Move\" reorder hint is a baked LZ77 graphic (0xB1BBE0), not string text"
metadata:
  node_type: memory
  type: project
  originSessionId: b81ed922-5f5d-469c-8faa-285b03dc4662
---

Le "Move" du menu START (barre d'indice `SELECT Move` en bas, = appuyer SELECT
pour réordonner les icônes) n'est **pas** du texte d'une table de chaînes : il est
baké pixel-par-pixel dans un graphique LZ77 à **0x0B1BBE0** (15 tuiles ; tuiles
8-11 = keycap SELECT, tuiles 12-14 = mot "Move"), pointé depuis le code du menu à
**0xA0C210**. Police biseautée (fill clair 0x0F + biseau sombre 0x0E) sur fond
dégradé vertical (index 1/2/3/4 par paire de rangées).

**Pourquoi ça piège** : recherche texte exhaustive de "Move" = perte de temps
(le run précédent a abandonné). Aucune entrée `combined_fr.txt` ne peut l'atteindre.
Signes de graphique baké : absent de la RAM pendant le menu, absent des tables de
libellés (0xA4E4xx / pointeurs 0xA6D160), pas de pointeur de chaîne dans le code
du menu (0xA0B000-0xA0C400), tuiles introuvables en brut dans la ROM.

**Tentative 1 (REVERTÉE)** : patch procédural post-build `start_menu_move_hint.py`
qui redessinait les tuiles 12-14 à la volée puis recompressait → **faisait glitcher
tout le menu START** en jeu (le user a demandé le revert). Supprimé + ROM restaurée.
Ne PAS redessiner ce sprite par code procédural.

**Fix retenu (issue #43, rouverte)** : brancher le graphique sur le pipeline sprite
éditable-à-la-main déjà présent (`scripts/extract_sprite.py` / `insert_sprite.py`,
registre `languages/fr/sprites.py`, modèle status_badges/selection). Sprite enregistré
`start_menu_move_hint` = bloc 0x0B1BBE0, `tiles_wide=15, tiles_tall=1` (120×8),
compressed=True. BMP exporté → `languages/fr/sprites/start_menu_move_hint.bmp`
(indexé 16c : fill=index 15, biseau=14, fond dégradé=1-4). Round-trip extract→insert
**octet-exact** (253/263 o recompressé, 480 o décompressé identiques) → un BMP
redessiné "Move"→"Dépl." à la main s'injecte proprement, sans glitch. Reste à :
éditer le BMP (tuiles 12-14) puis câbler `insert_sprite.py --sprite start_menu_move_hint`
dans `make build-fr`. Commit revert : `313b469`.

Autres libellés du menu START (Pokédex, Pokémon, Options, Save Game…) = table à
0xA6D160 (stride 0x10 : {gfx_ptr, label_ptr, u32, u32}), rendus texte à la volée
en VRAM. "Save Game"/"DexNav"/"Exit" y sont restés anglais (candidats futurs).
Méthode de diagnostic graphique-vs-texte : dump VRAM (BG0 charblock 2) + reconstruction,
puis `scripts/find_hint_graphic.py` pour localiser la source LZ77. Voir aussi
[[unbound-hp-pv-label-graphics-blocks]], [[unbound-special-text-rules]].
