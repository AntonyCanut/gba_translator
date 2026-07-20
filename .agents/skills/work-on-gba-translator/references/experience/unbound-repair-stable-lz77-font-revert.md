---
name: unbound-repair-stable-lz77-font-revert
description: "repair_stable_lz77_blocks.py revertait 7/8 blocs de police FR vers l'anglais malformé (#42, accents petit texte)"
metadata:
  node_type: memory
  type: project
  originSessionId: 870a4cbc-1b13-4d5a-a491-cc11a897c197
---

Issue #42 « Accents sur petit texte cassés » (menus, noms Pokémon, Pokédex) : les
accents é/è/à visibles dans les captures d'écran du ticket montraient exactement le
symptôme pré-fix décrit dans [[unbound-e-accent-glyph-malformed]] (accent flottant,
décalé, mordant sur la ligne du dessus) — alors que ce bug était censé être réglé
depuis B-96.

**Cause racine (nouvelle, différente de B-96)** : ce n'est PAS une deuxième police
« petite taille » séparée — `find_font_blocks` trouve bien les 8 mêmes blocs LZ77
0x2000/256-glyphes dans `englishrom.gba`, et `patch_font_fr.py` les corrige tous les
8 correctement en isolation. Le problème est une étape **postérieure** du pipeline
FR (`languages/fr/lang.yaml` : `font` → … → `repair_lz77` → `repair_localized_lz77`) :
`scripts/repair_stable_lz77_blocks.py` restaure vers l'anglais tout bloc LZ77 dont
les octets compressés EN==ES ("stable"). Comme la police n'est pas localisée en
espagnol, TOUS les blocs de police sont EN==ES → tous "stables" → tous réécrasés
vers la version anglaise malformée juste après le patch font, avant même que
`repair_localized_lz77_blocks.py` (qui exclut déjà `is_font_block`, cf. son ligne 113)
n'ait une chance d'agir. Résultat mesuré sur la ROM buildée : seul 1 bloc sur 8
survivait avec l'accent (le memory B-96 pensait que seuls "1-2 copies dupliquées"
étaient concernées — en réalité c'était 7/8).

**Piège** : `tests/test_font_patch.py::test_apply_patches_rewrites_e_accents` ne
testait QUE `apply_patches()` en isolation (jamais le pipeline `repair_*` complet),
et le commentaire dans ce test ("some duplicate blocks are restored to English
downstream") normalisait le symptôme au lieu de le questionner — ce test ne pouvait
donc pas détecter la régression.

**Fix** : ajouter la même exclusion `is_font_block(en_dec): continue` dans
`repair_stable_lz77_blocks.py` que celle déjà présente dans
`repair_localized_lz77_blocks.py`. Nouveau test
`tests/test_repair_stable_font_exclusion.py` qui patche une ROM complète et vérifie
que TOUS les blocs de police (pas juste un échantillon) gardent l'accent après la
passe stable — capture la régression que l'ancien test manquait.

**Piège rebase concurrent** : conflit binaire sur `output/roms/GenedRom-fr.gba`
pendant `orchestration_pull` avec un ticket concurrent (#43, Paramètres→Options) —
résolu en rebuild complet (`make prepare-fr && make build-fr`) après le rebase du
texte, pas en choisissant ours/theirs. Voir [[unbound-rom-rebase-conflict-rebuild-resolution]].

**Gotcha visuel** : le rendu ASCII naïf des glyphes (`glyph_pixels` → grille 8x8)
ne ressemble PAS à des lettres lisibles pour la plupart des blocs — c'est attendu
(police stockée dans un espace 4bpp permuté, cf. le memory B-96), ne pas s'y fier
pour valider, utiliser la comparaison programmatique `build_grave_a`/`build_acute_e`
contre le contenu du bloc.
