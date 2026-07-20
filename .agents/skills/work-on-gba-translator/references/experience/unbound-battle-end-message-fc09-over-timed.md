---
name: unbound-battle-end-message-fc09-over-timed
description: Message fin de combat « trop rapide » → préférer FC 09 (attente bouton) au FC 08 timed-pause ; victoire 0x3FD1C7 « Tu as battu X »
metadata:
  node_type: memory
  type: project
  originSessionId: 9079fd0f-6bb5-4488-b24d-48b2838a7052
---

Plainte récurrente « le message de fin de combat passe trop vite » : la pause
**temporisée `<0xFC><0x08><NN>`** (ex. 0x7F ≈ 2,1 s) est SUBJECTIVE et a été
jugée encore trop rapide par l'utilisateur. Solution robuste = **`<0xFC><0x09>`
(PAUSE_UNTIL_PRESS, attente bouton)** : le joueur appuie pour continuer →
lisible à coup sûr, indépendant du timer.

**Preuve que FC 09 est sûr en combat** : la ligne de prix voisine `0xA4C670`
(« Tu gagnes ¥X !<FC09> ») tourne déjà sans freeze dans le build joué — même
système de message de combat. Donc FC 09 sur n'importe quelle ligne fin-combat
(victoire/défaite/prix) se comporte pareil, pas de hang.

**Victoire dresseur `0x3FD1C7`** (gBattleStringsTable, « You defeated\n{1C} {1D}!») :
- traduction passée de « Vaincu X » (sèche) à **« Tu as battu {classe}\n{nom} ! »**
  (demande user), terminée par `<0xFC><0x09>`, SANS saut de page (comme la ligne
  de prix ; le moteur efface la boîte après l'appui).
- Écrit **en place** : slot 21 o (= len EN), 3 pointeurs 0xD776C/0x3FE410/0x9BE104
  NON repointés par la pipeline → garder ≤ 21 o. `Tu as battu`(11)+sp+FD1C+FE+
  FD1D+!+FC09 = 20 o + FF = 21 o. Buffers classe/nom (FD1C/FD1D) préservés.
- FC 08 7F (3 o) + « Tu as battu » + saut de page **déborderait** le slot →
  FC 09 (2 o) est aussi le seul qui rentre en place.

Voir [[unbound-brace-control-token-relocation-literal]] (FC09 brut vs accolade)
et [[unbound-battle-defeat-end-strings]] (défaite).

Piège rencontré au passage : `09_csv_to_json_v2.py` SANS l'argument CSV explicite
choisit un template périmé → JSON vide (0 traduction). Toujours passer le CSV
généré : `python3 src/translators/09_csv_to_json_v2.py output/translation/<date>_trilingual_translation.csv --allow-too-long`.
