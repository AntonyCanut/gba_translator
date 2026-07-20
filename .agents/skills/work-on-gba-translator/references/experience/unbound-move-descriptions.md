---
name: unbound-move-descriptions
description: "Descriptions d'attaque Unbound — fenêtre 5 lignes/122px (calibrée sur le jeu, PAS l'ES), table 0x99F190, patch post-build re-wrap+relocate"
metadata:
  node_type: memory
  type: project
  originSessionId: 8f2f7a2e-dcd7-4682-ab0c-1d70762204e7
---

Écran « Capacités connues » : la description d'attaque tient en **5 lignes max, ~122 px/ligne** (≈21 c). Table de pointeurs `gMoveDescriptionPointers` à **0x99F190**, indexée par numéro d'attaque (1..893) ; noms à 0x1B2980 (stride 13).

**LEÇON budget (B-33, commit `55d8c78`)** : NE PAS calibrer sur la ROM espagnole (142 px = faux ; la table ES à 0x99F190 ne décode même pas ici). Le vrai budget = le **wrapping d'origine du jeu** : décoder chaque description originale via ses sauts de ligne codés en dur (`0xFE`) → 99 % des lignes du moteur tiennent en **≤122 px** (max propre ~124 px ; les >150 px sont des moves Unbound non pré-wrappés). Piège : abaisser `MOVE_LINE_WIDTH` ne crée PAS de marge — le wrapper re-remplit les lignes jusqu'au nouveau bord, donc elles restent collées au bord droit et rognent. Il faut viser le vrai bord (122 px) une bonne fois. 142→130→122 px (3 passes user « encore trop large »). 122 px ≈ « 21 caractères » du ticket (~21×5,8 px).

Bug d'origine (448/893 débordaient) : le builder générique écrivait la trad FR **sur place** dans le créneau d'origine, plus court → texte tronqué en plein mot **sans terminateur**, qui fusionnait avec la description suivante (Morsure « …tressailIl grogne… » = Charme ; Jet-Pierres enchaînait plusieurs descriptions). Ce sont des corruptions de build, pas juste des trads trop longues.

Fix livré (T-F30, commit `fix(moves)`): `scripts/patch_move_descriptions_fr.py` (post-build, calqué sur [[unbound-pokedex-entries]] / patch_pokedex_fr.py) re-wrappe chaque description, réécrit toujours 0xFF, relocalise en espace libre si trop long et repointe 0x99F190. `src/core/moves.py` = lecture table + budget (réutilise le wrapping de pokedex.py). `data/move_descriptions_fr_overrides.json` = **220** raccourcis manuels (84→148 à 130 px, puis 220 à 122 px) pour les textes trop verbeux pour 5 lignes. Branché dans `make build-fr`. Vérif : `scripts/check_move_descriptions.py` (budget partagé via moves), tests `tests/test_move_description_check.py` + `tests/test_patch_move_descriptions.py`.

`englishrom.gba` (gba_translator) est une base **partiellement FR** : attaques d'origine en FR, attaques ajoutées par Unbound en anglais (mal wrappées, jusqu'à 232 px). Voir [[unbound-fr-build-lives-in-gba-translator]].
