---
name: unbound-mega-cuff-reaction-strings
description: Texte de réaction Méga-Cuff (Vega) restait anglais — 2 templates battle-region trop longs/absents
metadata:
  node_type: memory
  type: project
  originSessionId: 00bf036d-2867-42e0-b1e5-1497dbaeb515
---

Séquence Méga-Évolution (combat, ex. Vega) : « X's Y is reacting to Z's Mega Cuff! » restait
EN. **Deux** templates distincts en région battle-string (lus directement, pas via pointeur) :

- `0x83008C` (buffers 0/1/2/3) : présent dans combined_fr.txt mais FR = 34 o pour un slot de
  **31 o** → `too_long: true` → droppé à l'injection (région moteur, **pas de repoint**) → EN.
- `0x96CC1C` (buffers 0/16/39/1) : **absent** de combined_fr.txt → jamais traduit → EN.

Le 3e message « X Mega Evolved into Mega Y! » (`0x96CC3C`) était déjà FR (« Méga-Évolue »).

**Fix** : trimmer les deux à **exactement 31 o** pour injection en place sans repoint :
`à la `→`au ` (−2) + supprimer l'espace fine avant `!` (−1, comme l'EN). Forme :
`Le <0xFD><0x01> de <0xFD><0x00> réagit\nau <0xFD><0x03> de <0xFD><0x02>!`. Garde les 4 codes
FD (pas d'élision risquée `L'`/`d'` sur noms d'espèces/objets à consonne).

Compter les octets : raw `<0xFD><0xNN>` = 2 o, `é`/`à` = 1 o, `\n`(0xFE) = 1 o ; valider la
méthode contre la `length` rapportée par csv_to_json. Test : `tests/test_battle_mega_reaction_fr.py`
(décode les 2 offsets dans la ROM bâtie). Voir [[combined-fr-duplicate-offsets-last-wins]],
[[gba-translator-token-pipeline-pitfalls]].
