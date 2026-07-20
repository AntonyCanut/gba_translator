---
name: unbound-battle-healthbox-hp-label-blocks
description: "Libellé « HP » de la barre de vie EN COMBAT = 4 blocs LZ77 healthbox (0xD1F604/0xEEF0AC/0xEEF380/0xEEF688), sprite OBJ non localisé ES ; hp_labels.py (H→P, P→V). B-523: 0xD1F604 manqué au 1er fix, scanner par FORME pas octets exacts (#125)"
metadata:
  node_type: memory
  type: project
  originSessionId: 835bb174-5053-4b66-ae9f-c14c648b1cbe
---

Le « HP » à côté de la barre de vie **en combat** (issue #125) est un graphique
sprite OBJ 4bpp, pas du texte — distinct des 3 libellés HP déjà connus
([[unbound-hp-pv-label-graphics-blocks]] : menu Équipe 0x8001D0, jauge Résumé
0xE9B4B8, stat grise Résumé 0xE9A460).

Il vit dans **4 blocs LZ77** des feuilles de healthbox EN :
- `0x00EEF0AC` (128 tuiles, doubles) : « H » = tuile 20, « P » = tuile 21
- `0x00EEF380` (64 tuiles, singles) : « H » = tuile 19, « P » = tuile 20
- `0x00EEF688` (64 tuiles, singles) : « H » = tuile 19, « P » = tuile 20
- `0x00D1F604` (64 tuiles) : « H » = tuile 19, « P » = tuile 20 — **variante de
  slot de palette** (bordure haute couleur 3 au lieu de 2)

⚠ **B-523 (réouverture) : le 1er fix ne couvrait que les 3 blocs 0xEE… et « HP »
restait en combat.** 0xD1F604 avait été manqué car il a la MÊME forme mais des
octets de tuile différents (bordure haute 3 vs 2) → une recherche par **octets
exacts** ne le trouve pas. Le retrouver = scan **par forme** de lettre sur TOUTE
la ROM : pour chaque paire de tuiles adjacentes, tester si les cellules du
masque-lettre sont d'une couleur uniforme A et les cellules pastille d'une
couleur B≠A (H puis P). Ce scan prouve qu'il n'existe **que ces 4 feuilles** «
HP ». Leçon : toujours scanner par forme, pas par octets exacts.

Lettres = couleur 1 (blanc), pastille = couleur 7. Le corps de la tuile « P » est
identique partout ; seuls la bordure haute et l'ombrage col 0 de « H » varient →
`BATTLE_P_TILE_HEX` et `BATTLE_H_TILE_HEX` sont des dicts par bloc. Le draw
générique ne touche que les rangées 3-6 des lettres, donc marche quelle que soit
la bordure. ES ne localise aucun de ces blocs → `repair_localized` ne les touche
pas → « HP » résiduel en FR.

**Fix** : 4e volet dans `languages/fr/patches/hp_labels.py`
(`BATTLE_BLOCKS`, `_make_draw_battle_label`) — redessine la tuile « H » en « P »
(cols 2-6) et la tuile « P » en « V » (cols 0-4), bordures/embouts/jauge
intacts. Strict + idempotent, recompression in-place. `BATTLE_BLOCKS` liste les
4 blocs, `BATTLE_P_TILE_HEX`/`BATTLE_H_TILE_HEX` = dicts par bloc. Tests dans
`tests/test_patch_hp_labels_fr.py`.

**Localisation (réutilisable)** : les savestates du repo ne sont PAS en combat
et le flag `inBattle` @0x030022C8 est **non fiable** en Unbound. Pour atteindre
un combat : booter `tests/fixtures/saves/post-zeph-pre-cs.srm` (copié en
`<rom>.sav`), START→A→A (Continuer), marcher DOWN → cinématique kidnapping →
double combat Zeph ; détecter via buffers texte sv1/sv2/sv4
(0x02021CD0/CF4/D18), pas le flag. Puis dump OBJ VRAM 0x06010000..0x06018000,
repérer la tuile « HP » (~tuile 20-21), chercher les octets exacts dans les
blocs LZ77 EN décompressés. ⚠ mGBA meurt si `advanceFrames` > ~30 par appel :
découper. Voir aussi [[unbound-mgba-probe-quirks]], [[translating-unbound-skill]].
