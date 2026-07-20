---
name: unbound-font-patch-freespace-cascade
description: Ajouter un glyphe à patch_font_fr.py décale toute la relocalisation free-space et casse les descriptions de missions (budget RAZOIR)
metadata:
  node_type: memory
  type: project
  originSessionId: 92349353-87e6-4e27-9d56-b3657da7fcc1
---

Régression F-50 (réparée commit `08d1775`, gba_translator) : le build-fr a cessé de
fonctionner après que `scripts/patch_font_fr.py` ait reçu `build_u_umlaut()` (dessin
du glyphe ü slot 0x65, ajouté pour le multilingue DE).

**Cause racine en deux temps :**
1. `ENCODE_ALIASES` (`src/core/text_codec.py`) replie `ä→a ö→o ü→u` **avant** le
   charmap dans `encode_pokemon`. Donc FR (et IT) **n'émettent jamais** les octets
   0x60-0x65 : dessiner leurs glyphes dans patch_font_fr est du **code mort**.
2. Mais dessiner ü dans chaque bloc de police le rend *différent* → le patch font
   **relocalise plus de blocs en free space** → décale le curseur d'allocation → les
   ~21 595 octets de pointeurs/strings relocalisés glissent → la **marge free-space
   RAZOIR (~5 Ko)** est épuisée → 14/47 descriptions de missions ne tiennent plus →
   `make build-fr` échoue à son garde-fou `test_location_names_fr`.

**Leçon :** toute modif de `patch_font_*` ou de tout patch qui relocalise en free
space peut casser silencieusement les patchs *en aval* (missions = dernier + le plus
gourmand). Vérifier par byte-identité vs ROM committée connue-bonne (`cmp -s`), PAS
par « les tests passent ». Les glyphes umlaut allemands vivent dans le
`patch_font_de.py` indépendant — ne jamais les ajouter à patch_font_fr.

Conséquence DE distincte (même cause #1) : ENCODE_ALIASES neutralise les trémas
littéraux de combined_de.txt → glyphes 0x60-0x65 jamais émis côté DE non plus → bug
[[unbound-multilang-build-registry]] suivi par ticket B-81. Voir aussi
[[unbound-bounty-mission-3line-box]] (budget missions) et
[[unbound-ellipsis-pause-b0-glyph]] (marge free-space razoir).
