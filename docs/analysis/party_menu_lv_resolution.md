# Party-menu « Lv » → « N. » — RÉSOLU (fix par édition du glyphe-ligature)

**Statut : RÉSOLU.** Le « Lv » de la liste d'équipe (menu START → Pokémon, ex.
« Lv10 ») est un **glyphe-ligature de police** (codepoint `0x05` de la police FRLG
non-compressée `s@1EEF00`), pixels ROM à **`0x1ECFA0`**. Il est converti en
« N. » par `languages/fr/patches/party_lv_label.py` (chaîne `build-fr`, après
`repair_*`, à côté de `hp_labels.py`).

## Pourquoi F-113 avait conclu « graphique » (à tort)

Le glyphe `{Lv}` (0x05) est dessiné **directement** par le code du niveau, sans
passer par le mesureur de largeur du moteur de texte. Le read-watch des 11 tables
de largeur (piste F-113) ne voit donc jamais « Lv » et concluait « aucune police
ne rend Lv → graphique ». La bonne sonde est un **read-watch sur les données de
glyphes** (`0x1EC000–0x1ED780`) : pendant l'ouverture du menu, exactement UN
glyphe est lu sans lecture de table de largeur → cp `0x05` @ `0x1ECFA0`.

## Preuves

1. **Read-trace largeur** : `s@1EEF00` rend exactement `Embrylex` `10` `♀`
   `30 / 30` `Annuler` — aucun « Lv ».
2. **Read-watch glyphes** : le seul glyphe lu sans mesure de largeur = `0x05`
   @ `0x1ECFA0`. Calibration glyph_base=`0x1EAF00`, stride 32 o (match 16/16 des
   codepoints observés).
3. **Blanchiment ciblé** : mettre à zéro la zone de glyphes efface « Lv » **et**
   nom/chiffres, tandis que le label « PV » (bloc LZ77 `0x008001D0`, géré par
   `hp_labels.py`) **survit** → « Lv » vient de la police, pas du template.
4. **Copie/édition** : copier les octets du glyphe « E » (0xBF) dans `0x05`
   affiche « E10 » ; l'édition finale affiche « N.10 » (vérifié mGBA sur la ROM
   fraîchement buildée).

## Format de glyphe FRLG (rétro-ingénierie write/observe)

32 octets = 64 nibbles. `DecompressGlyphTile` place le nibble `n` sur une cellule
de 2 px de large à (row=`n//4`, col=`3-(n%4)`) d'une grille 4 colonnes × 16 lignes.
Sémantique de valeur après remap couleur de l'imprimeur : `5`→blanc (fg),
`8`→gris (ombre), `0`/`0xF`→transparent. Le nouveau glyphe « N. » = le vrai glyphe
« N » (cp 0xC8) + un point blanc dans la colonne droite restée vide (lignes 9-11),
donc l'antialiasing natif de la police est conservé.

## Couverture

Éditer le glyphe `0x05` corrige **tous** les écrans lisant cette ligature (liste
d'équipe). L'écran **Résumé** affiche encore « Lv10 » / « au Lv 10. » : il utilise
un **mécanisme différent** (chaînes pointées / autre chemin de rendu), pas le
glyphe `0x05` — hors périmètre de ce ticket, suivi par un ticket dédié.
