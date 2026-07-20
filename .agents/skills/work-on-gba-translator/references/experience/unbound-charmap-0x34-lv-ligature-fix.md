---
name: unbound-charmap-0x34-lv-ligature-fix
description: "Issue #63 'N. à la place de Lv' — 3e mécanisme distinct de rendu 'Lv' : codepoint charmap normal <0x34> ('[LV]'), embarqué inline dans le texte (pas une icône F9 05, pas un glyphe hardcodé cp 0x05) ; 32 chaînes combined_fr.txt affectées"
metadata:
  node_type: memory
  type: project
  originSessionId: bd1eca40-3524-48af-839b-2dace2ca2386
---

Troisième bug distinct de la famille « Lv » au lieu de « N. » (voir [[unbound-summary-lv-extra-symbol-f905]] et [[unbound-party-lv-is-graphic-not-font]] pour les deux précédents). Ici le codepoint **`0x34`** du charmap CFRU (`CHARMAP[0x34] == '[LV]'`) est un octet NORMAL de texte (pas une icône `F9 05`, pas un glyphe hardcodé blitté par le code comme cp `0x05` de la liste équipe) — il apparaît directement inline dans `combined_fr.txt`, encodé/décodé comme n'importe quel caractère, et rend toujours « Lv » quel que soit le contexte.

32 chaînes de `languages/fr/combined_fr.txt` contenaient ce codepoint brut (`<0x34>` ou `{LV}` selon la représentation) : indices d'évolution Hidden Power (« Il monte au N. `<0x34>` {STR_VAR_2} »), badges d'Arène (obéissance Pokémon échangés), Œufs Chance, Brac. Macho, Pièce Rune, Défi Frontière. Deux sous-cas :
1. Un « N. » ou « Nv » littéral avait déjà été ajouté à la main à côté du codepoint (fix précédent incomplet) → duplication visible « N. Lv 26 » (exactement la capture d'écran de l'issue #63, Badge Feuille de Sylvain @0x1F15FD6).
2. Le codepoint seul, sans aucun texte « N. »/« niveau » → affichait juste « Lv » (ex. Badge Marais @0x1f18a97, Œufs Chance @0x1F09838).

**Fix** : édition directe de `combined_fr.txt` (PAS de patch post-build glyphe/icône comme pour les 2 bugs précédents — ce codepoint est un caractère texte normal, le fix est donc textuel) : suppression du codepoint quand « N. »/« niveau » était déjà présent dans la phrase (dédoublonnage), remplacement par « N. » littéral sinon. Piège lors de l'édition par script : le fichier utilise `\n`/`\l`/`\p` comme séquences **littérales backslash+lettre** (pas de vrais retours à la ligne) — un script Python qui split sur `"\n"` réel casse le pattern matching des lignes multi-segments.

**Découverte du bug par capture d'écran** : le JWT signé des images `private-user-images.githubusercontent.com` dans le corps d'issue GitHub expire en ~5 min (300s) — le premier `curl` a échoué en 404 (expiré), il a fallu rappeler `github_issues_get` pour obtenir une URL fraîchement signée et la télécharger immédiatement.

**Piège méthodologique** : un scan brut d'octets `<0x08000000+offset>` pour vérifier les pointeurs vivants donne des faux négatifs si la chaîne a été relogée par l'injecteur (l'adresse EN d'origine devient une chaîne MORTE, cf. [[unbound-trace-live-pointer-not-original-offset]]) — vérifier via `patchedfrenchrom_texts.json`'s `pointer_offsets`, lire la valeur ACTUELLE du pointeur dans la ROM construite, puis décoder à cette nouvelle adresse.

**Session note** : ce ticket a été résous une première fois plus tôt dans la même conversation (commits `f727e0f`+`0cfe5c1`, ROM rebuild, commentaire GitHub) avant une compaction de contexte ; la reprise a re-dérivé indépendamment la même analyse et confirmé le fix déjà en place au lieu de le redupliquer — juste fermé l'issue GitHub (restée ouverte) et re-vérifié la suite de tests (1443 passed).
