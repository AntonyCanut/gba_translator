---
name: unbound-tight-quotes-no-inner-space
description: "Unbound FR: guillemets serrés «mot» sans espace intérieur (préférence user), + le guillemet fait partie du mot pour le wrapping"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 08ff3114-94e8-4213-b655-64db7105dab6
---

L'utilisateur veut les citations **serrées** : `«mot»` / `"mot"`, **PAS** la typo
française espacée `« mot »`. Donc aucune espace littérale immédiatement à l'intérieur
d'un guillemet (après `«`/`“`/`"` ouvrant, avant `»`/`”`/`"` fermant).

**Why:** dans la police CFRU les guillemets s'affichent collés ; l'espace intérieure crée
un vide disgracieux et provoquait des sauts de ligne moches (le guillemet ouvrant orphelin
en fin de ligne).

**How to apply (R-09, juin 2026) :**
- Texte : `scripts/clean_quote_inner_spaces_fr.py --apply` retire l'espace intérieure dans
  `combined_fr.txt` (openers `«“‹` + `"` droit résolu par alternance par entrée ; jamais les
  breaks `\n \l \p` ni les glyphes ; ne fait que raccourcir → pas d'overflow). 160 entrées,
  326 espaces retirés. Test : `tests/test_clean_quote_inner_spaces_fr.py`.
- Wrapping : `src/core/dialogue_linewrap.py` `_split_words` soude un guillemet **ouvrant** au
  mot **suivant** (et le fermant au précédent) — le guillemet fait partie du mot pour décider
  d'un saut, donc jamais orphelin (`«Rejoindre` reste insécable). Le `"` droit (le pipeline
  stocke `«»` en `"`) est mis en attente et résolu par ce qui suit (mot=ouvrant, ponctuation/fin=
  fermant). Vérifié octets ROM à 0x1BD51B : `“Rejoindre Groupe”.`.

Toute nouvelle trad FR doit suivre la convention serrée. Voir [[unbound-fr-build-lives-in-gba-translator]],
[[unbound-guillemets-render-as-ellipsis]].
