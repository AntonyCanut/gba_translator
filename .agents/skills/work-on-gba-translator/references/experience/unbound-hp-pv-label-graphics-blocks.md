---
name: unbound-hp-pv-label-graphics-blocks
description: "Labels HP/PS → PV = 3 blocs LZ77 graphiques (party 0x8001D0, sprite jauge résumé 0xE9B4B8, ovale gris 0xE9A460) ; patch_hp_labels_fr.py ; méthode = dump VRAM mGBA + recherche de forme"
metadata:
  node_type: memory
  type: project
  originSessionId: cf05b7bf-80f0-4880-84a6-016860669b19
---

Les abréviations de points de vie en jeu sont des GRAPHIQUES 4bpp dans des blocs LZ77, jamais du texte (ticket « PS/HP → PV », 2026-07-02, commit gba_translator `feat(fr): remplacer les labels HP/PS par PV`) :

- **Menu équipe « HP » vert** : bloc `0x008001D0` (tileset CFRU 80 tuiles, feuille 8 de large), lettres réparties sur tuiles 51/52 lignes 5-7 + 59/60 lignes 0-2 (split 3+3), fond=6, contour=0xE, lettres=0xF. Cols 14-15 = amorce de jauge, à préserver.
- **Résumé jauge « PS » vert** : bloc `0x00E9B4B8` tuiles 9-10, affiché comme SPRITE (OBJ). EN=« HP », ES=« PS » (recopié par repair_localized). fond=0, contour=0xF, lettres=0x4.
- **Résumé stat « HP » gris** : bloc `0x00E9A460` (tileset images-mots ATTACK/DEFENSE…, 512 tuiles, feuille 16 de large), tuiles 100/101+116/117, lettres fines couleur 1 sur ovale 7.

**Fix** : `scripts/patch_hp_labels_fr.py` (validation stricte octets EN/ES connus, redraw contour par adjacence orthogonale, recompression in-place, idempotent), branché dans build-fr après les repairs LZ77. Tests : `tests/test_patch_hp_labels_fr.py` ; 0xE9B4B8 retiré de LOCALIZED_BLOCKS (comme 0xB1E280/KO).

**Méthode de localisation réutilisable** (quand un graphique est introuvable statiquement) : probe mGBA (`scripts/probe_hp_vram.mts`) → savestate committée `output/roms/GenedRom-fr.ss2` (in-game avec Pokémon) → screenshot + dump VRAM BG/OBJ + screenblocks → position pixel → entrée tilemap → tuile → recherche des octets exacts dans les blocs LZ77 décompressés. Piège : les labels peuvent être **composités en RAM** (fond différent) → recherche de FORME (classes bg/contour/lettre) avec lettres **réparties verticalement sur 2 rangées de tuiles** (split k, largeur de feuille W). Vérif auto : `scripts/verify_hp_labels_fr.py` sur les dumps. Voir aussi [[unbound-type-icons-are-graphics]], [[unbound-status-abbrev-sommeil]].
