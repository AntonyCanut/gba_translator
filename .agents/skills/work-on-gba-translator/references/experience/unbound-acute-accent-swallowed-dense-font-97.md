---
name: unbound-acute-accent-swallowed-dense-font-97
description: "Accent aigu é « un pixel manquant » sur police pleine Pokédex/HUD (#97) — overlay_accent max avale l'accent sur le haut dense du e"
metadata:
  node_type: memory
  type: project
  originSessionId: 8ee7e8e6-7f7e-4580-bc9e-92926ce378d0
---

Issue #97 (B-462, réouvert 2026-07-17) : l'accent aigu (é/á) rendait « un pixel
manquant » sur la **petite police pleine** (non anti-aliasée) du Pokédex (catégorie
« Pokémon Neige Fraîche ») et du HUD de combat (« Flabébé »). Les polices
anti-aliasées (écran Résumé « Rencontré », menu d'action « Résumé ») étaient CORRECTES.

**Cause racine** : cette police (bloc `@0x2BA8D8` dans la ROM FR) dessine un `e`
au **haut dense (valeurs 14-15)** pile là où se pose l'accent aigu. `overlay_accent`
gardait le pixel le plus foncé (fusion `max`, `val > out[idx]`) → le pixel de gauche
de l'accent (valeur ~4) était avalé par le corps du `e` (14). Résultat : accent à
2 px au lieu de 3 (2 en haut + 1 en bas-gauche). Preuve depuis les captures user :
correct = 3 px, incorrect = 2 px (haut-gauche manquant).

**Le « fix » précédent (`range(1,7)` au lieu de `range(8)`) était un NO-OP prouvé** :
`build_acute_e` produit des glyphes **octet-identiques** avec range(8) vs range(1,7)
pour TOUS les blocs (les colonnes exclues étaient de toute façon avalées par collision).
D'où « le bug persiste ». Toujours vérifier qu'un correctif change réellement des octets.

**Vrai fix** : `overlay_accent(..., overwrite=True)` pour l'aigu seulement
(`build_acute_e`) → écrit l'accent inconditionnellement, la rangée d'accent du é
reconstruit devient **identique à celle de á** (source déjà correcte). Le grave garde
`max` (son décalage ne tombe jamais sur un haut dense ; passer en overwrite casserait
le è du bloc @0x32A800). Seul le bloc `@0x2BA8D8` change ; autres blocs + tous les
graves = octet-identiques. Test `TestAccentedEGlyphs::test_acute_accent_survives_dense_letter_top`.

**ROM : patch chirurgical, PAS `make build-fr` complet.** Sur unbound courant, un
`make prepare-fr build-fr` complet RÉGRESSE les types FR→EN (« ROCHE SOL »→« ROCK
GROUND ») et le marqueur « N. »→« Lv » (JSON périmé, cf [[unbound-make-build-fr-reuses-stale-same-day-json]]).
J'ai donc appliqué seulement `python3 languages/fr/patches/font.py --rom <ROM committée du parent>`
→ diff = 1790 o dans 1 région (le bloc police), zéro dérive, types/marqueur préservés
(vérifié en jeu écran Résumé). Committer CE ROM, pas le rebuild complet.

**Gotchas debug** : la police se décode en VRAM par un format packé non naïf
(codepoint*32 en 4bpp = bruit, cf [[unbound-e-accent-glyph-malformed]]) — impossible
de la visualiser hors moteur. Raisonner sur rows 0-1 (accent) vs 2-7 (corps) et
COMPARER à á. Vérif en jeu = sonde mGBA (ss2 overworld → START → A → A → A = menu
Résumé/Objet, ou → A → summary). Le Pokédex n'est PAS accessible sur la save ss2
(early game), donc bloc @0x2BA8D8+é non atteignable en jeu ici → preuve au niveau glyphe.
Le hook pre-commit (`npm --prefix emulator-web test`) relance un `make build-fr` qui
REMODIFIE le ROM du working tree APRÈS le staging → `git checkout -- <rom>` après commit.
