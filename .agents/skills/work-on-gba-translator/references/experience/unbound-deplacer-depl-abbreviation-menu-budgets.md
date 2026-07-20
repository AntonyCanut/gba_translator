---
name: unbound-deplacer-depl-abbreviation-menu-budgets
description: "Issue #29 : \"Déplacer\"→\"Dépl.\" sur 9 offsets PC/menus. MAJ B-366 : \"Dépl.\" (5o) en place sur cellule \"Move\" de 4o CORROMPT (déborde le terminateur → \"Dépl.Dépl. où ?\") ; fix durable = repoint free-space (patch pc_move_labels.py), pas \"Dépl\" tronqué"
metadata:
  node_type: memory
  type: project
  originSessionId: e1ad60b9-ca98-4c63-90db-d4b3f2916d4c
---

## MAJ B-366 (issue #29 rouverte : « le texte est corrompu, veux « Dépl. » »)

La correction « Dépl » sans point était fragile et 0xA4E1F1 avait reçu
« Dépl. » (protégé par #111) → **corruption visible** : « Dépl. » (5o) écrit
dans la cellule « Move » de 4o écrase le terminateur et déborde sur la chaîne
voisine → le joueur voit « Dépl.Dépl. où ? ». (Le mécanisme n'est PAS toujours
un fallback anglais silencieux : quand FR == taille de slot exactement,
l'injecteur écrit en place SANS terminateur = corruption.)

**Fix durable = repoint, pas troncature.** Ces cellules « Move » sont
pointées par de vrais pointeurs 32-bit (scanner la ROM pour `offset|0x08000000`
en LE : 0x418484=2 ptrs, 0x418EB5=4 ptrs `{DPAD}`, 0xA4E1F1=1 ptr,
0x41858D=1 ptr). Patch class-3 dédié `languages/fr/patches/pc_move_labels.py`
(modèle : [[unbound-cancel-button-was-text-not-sprite]] /
party_cancel_button.py) : écrit « Dépl. »/« Dépl. Pokémon »/« {DPAD}Dépl. »
+ 0xFF dans un bloc **baseline-free** (0x15FBC90, 344 Ko de 0xFF présents dans
la ROM source ET jamais touchés par l'injecteur → déterministe, sans
collision), puis repointe tous les pointeurs (vérifie la valeur d'origine
avant, idempotent). Résultat : « Dépl. » AVEC point sur TOUS les menus, zéro
débordement. combined_fr.txt garde « Dépl » (4o) comme fallback sûr en place ;
protected_entries #111 mis à jour expected=« Dépl » (le point vient du patch).
0x4177DD « Move To Bag » (chaîne SANS pointeur, bloc walké — d'où le drop du
« Dépl au sac ») → « Vers le sac » en place (11=11).

> Leçon : sur cellule figée trop courte pour l'abréviation voulue, **reloger +
> repointer** (le repo le fait partout) plutôt qu'accepter un mot tronqué ou un
> fallback anglais. Scanner les pointeurs d'abord ; 0 pointeur = in-place only.

---
### Contexte d'origine (approche « sans point », désormais supersédée) :

9 occurrences de « Déplacer » dans `combined_fr.txt` (PC Box / trade / mail
menus, 0x4171F1, 0x4177DD, 0x418484, 0x41858D, 0x41859A, 0x418E77, 0x418EB5,
0xA4E1F1, 0xA4E1F6). Toutes ne partagent pas le même type de cellule :

- Cellules relogeables (0x4171F1, 0xA4E1F6, 0x418E77 avec `{DPAD_ANY}` token) :
  « Dépl. » (avec point) passe sans souci — assez de marge/pointeur.
- Cellules « no-pointer in-place » à liste de mots courts (0x418484, 0xA4E1F1
  dans une liste Annuler/Stocker/Retirer/Échanger/**Déplacer**/Placer/…) :
  budget = `len(encode(EN))` exact (ex. EN "Move" → budget 4 octets). Le
  point fait déborder de 1 octet → retombe silencieusement en anglais
  (aucune erreur bloquante, juste `too_long` → build affiche le mot EN
  d'origine). Fix = « Dépl » **sans point**.
- 0x41858D « Move Pokémon » (budget 12) : « Dépl Pokémon » (12, sans point)
  tient pile ; avec point (13) déborde.
- 0x41859A « Move Items » (budget 10) : même « Dépl objets » (11, sans
  point) déborde encore — abrégé en « Dépl. obj. » (10, avec point) pour
  tenir.
- 0x4177DD « Move To Bag » (budget 11) : « Dépl vers le sac » trop long
  même abrégé ; reformulé en « Dépl au sac » (11, sans point) pour tenir.
- 0x418EB5 (déjà fixé par un ticket antérieur en « Dépl » sans point,
  budget 9) : **piège** — si on uniformise avec point partout sans vérifier
  le budget de CETTE cellule précise, on la fait régresser en anglais.
  Toujours redécoder tous les offsets touchés dans la ROM buildée après
  coup, pas seulement ceux qu'on modifie explicitement.

Méthode de vérification : `TextEncoder.encode(text, 'pokemon')` (moins le
terminateur) pour calculer le budget exact avant d'écrire dans
`combined_fr.txt`, puis toujours redécoder les offsets dans la ROM buildée
(`TextDecoder.decode_pokemon`) — ne jamais se fier au fichier source seul.

Bonus : le pied de page HUD 0x418E77 (« Déplacer OK Retour ») était en
anglais de façon pré-existante faute de place (voir
[[unbound-move-status-header-budget-and-token-false-alarm]]) — le
raccourci "Dépl." l'a fait rentrer et il s'affiche désormais en français.

Rebase : 2 conflits binaires consécutifs sur `output/roms/GenedRom-fr.gba`
pendant `orchestration_pull` (tickets concurrents rebuildant la même ROM) —
résolus à chaque fois en rebuildant depuis le `combined_fr.txt` mergé
(jamais choisir ours/theirs), cf.
[[unbound-rom-rebase-conflict-rebuild-resolution]].
