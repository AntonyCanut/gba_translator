---
name: unbound-gang-name-roitiflam-noir
description: Gang « Black Emboar » se traduit « Roitiflam Noir » (jamais franglais « Black Roitiflam »)
metadata:
  node_type: memory
  type: project
  originSessionId: b4555584-eb41-46ba-8ffb-3554356e8dfc
---

Le gang Unbound « Black Emboar » se traduit en FR par **« Roitiflam Noir »**
(Roitiflam = nom FR canonique d'Emboar, Noir = Black postposé). Forme déjà
utilisée par les entrées préexistantes (« Le Roitiflam Noir », « L'Emboar Noir »).

**Piège franglais :** NE PAS produire « Black Roitiflam » (Black anglais + Pokémon FR).
Gardé par `gba_translator/tests/test_translate_pokemon_names_fr.py::test_gang_proper_nouns_are_preserved_in_source`
qui exige `"Black Roitiflam" not in combined_fr` ET `"Black Emboar" in combined_fr`.

**Cellule à largeur fixe 0x23E7A1** = nom de classe de Dresseur (slot 13 octets, lu
par index, 0 pointeur → relocalisation impossible). « Roitiflam Noir » (15 o) n'y rentre
pas → garder l'anglais byte-exact « Black Emboar » (12 o, fit). C'est ce qui satisfait
l'assert `"Black Emboar" in text`. Toutes les autres occurrences (dialogue, bannière
« Combat ! », « Boss du… », quête CT 0x1F55AE8) passent par des strings à pointeur →
relocalisées en free space, vérifiées joignables. Voir [[unbound-item-name-cells-class2]],
[[combined-fr-duplicate-offsets-last-wins]].

**Suivi D-10 (résolu) — « Black {PLAYER} » + variables de genre.** Le gang se renomme
d'après le joueur : **« Black {PLAYER} » → « {PLAYER} Noir »** (Noir postposé, comme
Roitiflam Noir). ~76 copies joignables (chaque offset a un pointeur, aligné OU embarqué
dans un script). **Pourquoi le « mode glouton » a raté :** (1) le commit Roitiflam-Noir
précédent a été perdu par un reset de worktree concurrent (cf [[singularity-worktree-commit-early]]),
(2) beaucoup de copies vivent dans une région branche-difficulté, (3) **les copies VIVANTES
du bloc minuscule en bas réfèrent le gang via le token BRUT `Black <0xFD><0x01>`, pas la
brace `{PLAYER}`** → un find-replace sur `{PLAYER}` les rate (ex. 0x1edd2a8 L23670, 0x7f991f).
Chercher LES DEUX formes : `Black(\\[nlp]| )(Emboar|\{PLAYER\}|<0xFD>)`.

**Variables de genre (0x1F9DBD7, 0x1FA13F5)** : l'anglais réfère le joueur via les buffers
`<0xFD><0x03>` (« as he/she did ») / `<0xFD><0x02>` (« my boy/girl »), incohérents en FR.
Fix = comme l'espagnol, écrire le **nom du joueur** via le token BRUT `<0xFD><0x01>` (et
SANS aucune brace → `_apply_control_placeholders` retourne tôl si `'{' absent`, sinon il
consomme positionnellement les codes EN, nom ignoré, cf [[unbound-gender-pronoun-variable-removal]]).
« en son honneur » est neutre (his/her = son). Vérif octets : `<0xFD><0x02>`/`<0xFD><0x03>`=0
au pointeur vivant. `scripts/translate_black_emboar_fr.py` (transfo) + `scripts/verify_black_emboar_fr.py`
(suit le pointeur, décode, 28/28 verts) + 2 tests source. Cellule fixe 0x23E7A1 et
« Black Ferrothorn » (gang rival) restent anglais.
