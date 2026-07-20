---
name: unbound-borrius-second-pokecenter-cluster
description: "Le « qq secondes » du Centre Pokémon = 2e cluster Borrius 0x1F4E5xx, distinct du principal 0x1A5xxx, absent de combined_fr.txt"
metadata:
  node_type: memory
  type: project
  originSessionId: b24f7284-e7fc-4f67-949e-c24d93c3a028
---

Il existe **DEUX** clusters de dialogues de Centre Pokémon dans Unbound, pas un :

1. **Principal** `0x1A5xxx` (0x1A5483 accueil, 0x1A54E1 « prends tes Pokémon », 0x1A552B merci…) — présent dans `combined_fr.txt`, traduit proprement.
2. **Borrius** `0x1F4E5xx` (0x1F4E528 accueil inline sans pointeur, 0x1F4E599, 0x1F4E6D8, 0x1F4E7ED, 0x1F4E83A) — **absent de `combined_fr.txt`**, donc les traductions automatiques dégradées (CSV/JSON uniquement) atteignaient la ROM sans correction.

Le bug B-53 signalé « ok, je prends tes Pokémon pour qq secondes » = **0x1F4E6D8** (cluster Borrius), PAS 0x1A54E1. Deux tickets précédents l'ont raté car ils ont corrigé 0x1A54E1 + les strings inline d'animation (0x770f6d/0x770f7b) sans voir le 2e cluster. La même phrase EN « Okay, I'll take your Pokémon for a few seconds. » a 2 entrées JSON (offsets 1725665 / 32827096).

**Méthode de détection** : ne pas chercher par offset dans `combined_fr.txt` (l'entrée bad n'y est pas) — encoder le texte (`secondes`, `qq `) et scanner les octets de la **ROM construite**, puis suivre le pointeur vivant. Le cluster Borrius est pointeur-référencé (0x599/6D8/7ED/83A ont 1 pointeur → relocalisables), sauf 0x1F4E528 (inline sans pointeur, budget 63 o → traduction longue rejetée silencieusement comme les strings inline du ticket précédent ; raccourcir pour tenir).

Fix : ajouter les 4 offsets au bloc minuscule de `combined_fr.txt`, chaîne de build (`apply_combined_fr --extend` → `09_csv_to_json_v2.py <csv trilingue> --allow-too-long` → `make build-fr`), vérif octets. Voir [[combined-fr-duplicate-offsets-last-wins]], [[unbound-fr-build-lives-in-gba-translator]], [[unbound-csv-offset-normalization]].

PIÈGE build : `09_csv_to_json_v2.py` SANS argument CSV prend par défaut `2026-01-13_translation_template.csv` (vide) → JSON à 0 traduction. **Toujours passer `output/translation/2026-01-15_trilingual_translation.csv` explicitement.**

Reste hors périmètre (dialogues scénario Borrius, même défaut « mots réduits ») : 0x1F48A96 / 0x1F4D8FD « qq part », 0x1F4A51E / 0x1F4A639 « stp ».
