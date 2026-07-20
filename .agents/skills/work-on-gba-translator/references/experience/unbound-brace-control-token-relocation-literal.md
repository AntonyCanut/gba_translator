---
name: unbound-brace-control-token-relocation-literal
description: "Les tokens de contrôle en accolade ({PAUSE_UNTIL_PRESS}, {FC09}) ne sont PAS développés par l'encodeur de réinsertion/relocalisation — sur un slot court qui déborde ils sont écrits en TEXTE LITTÉRAL ; utiliser la forme brute <0xFC><0x09>"
metadata:
  node_type: memory
  type: project
  originSessionId: c76e214c-746c-4581-aa94-5471c38c36d9
---

Dans le pipeline FR (gba_translator), l'encodeur de réinsertion ne reconnaît que les
tokens de contrôle **bruts** `<0xXX>` (regex `<0x([0-9A-Fa-f]{2})>` dans
`src/translators/19_build_translated_rom_generic.py`). Les formes en accolade
`{PAUSE_UNTIL_PRESS}` / `{FC09}` n'ont **aucune définition** dans l'encodeur.

**Piège :** une entrée combined_fr.txt avec `{PAUSE_UNTIL_PRESS}` sur un slot EN **court**
qui doit être **relocalisé** voit le token écrit en **texte littéral** dans la ROM
(constaté : `Tu gagnes ¥ !?PAUSE?UNTIL?PRESS?`). Les 126 entrées `{PAUSE_UNTIL_PRESS}`
existantes « marchent » seulement parce qu'elles sont **en place** (gros slot EN) : leur FC09
est en réalité l'octet FC09 **résiduel de l'anglais** non écrasé (le FR est plus court), pas
une expansion du token.

**Fix :** écrire la forme brute `<0xFC><0x09>` dans combined_fr.txt. `csv_to_json` la compte
comme 2 octets, et l'encodeur (en place comme en relocalisation) la convertit en FC 09.
Vérifié : `0xA4C670` (message « Tu gagnes ¥X ! », STRINGID_PLAYERGOTMONEY, affiché in-combat
après « Vaincu <Dresseur> » et avant le gain) décode `Tu gagnes ¥<buffer> !<FC09>` (FC 09 FF),
en place, pointeur consommateur `0x3FDF84` intact. Ticket « Phrase fin combat ».

`length`/`too_long` de csv_to_json sont indicatifs : le build recalcule la taille réelle après
expansion des `{UNKNOWN_STR}`→`<0xFD>` et écrit **en place** si ça tient (donc `too_long=True`
ne force pas forcément la relocalisation). Voir [[gba-translator-token-pipeline-pitfalls]] et
[[unbound-fr-build-lives-in-gba-translator]].

Concurrence : ce ticket a vu un agent parallèle réécrire combined_fr.txt (revert de l'édition
non commitée) — commiter immédiatement avec chemin précis et vérifier `git show HEAD:` ; cf.
[[singularity-worktree-commit-early]].
