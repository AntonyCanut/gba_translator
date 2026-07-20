---
name: unbound-type-icons-are-graphics
description: "Les noms de types affichés (résumé + menu d'attaque combat) sont un GRAPHIQUE, pas du texte ; offsets + astuce mGBA écran verrouillé"
metadata:
  node_type: memory
  type: project
  originSessionId: d488fe59-114a-4426-ab6f-221b4f3356dc
---

Les badges de TYPE affichés sur l'écran résumé (pages Infos/Capacités) et dans le
menu d'attaque en combat sont un **graphique de tuiles 4bpp**, PAS du texte lu
dans une table de chaînes.

**Ce qui NE marche PAS** (vérifié en jeu, ne pas refaire) :
- patcher `gTypeNames` @ `0x024F1A0` (table vanilla MORTE — aucun pointeur littéral ne la cible)
- patcher le gabarit « a TYPE move » @ `0x3FE890` (c'était la cible erronée d'un run précédent)
- patcher les chaînes « ROCK »/« GROUND » du ROM (mettre ZZZZ partout n'a rien changé)

**La vraie source** : le nom du type est dessiné en pixels dans une planche de
16 tuiles de large, présente en **deux copies** :
- `0xB1EC64` (tuile 0) → écran résumé (copie VIVANTE confirmée : l'éditer change l'affichage)
- `0x961A00` (tuile 0) → menu d'attaque combat
Chaque icône fait **4×3 tuiles (32×24 px)**, fenêtre affichée = lignes 8-19 (12 px) :
lignes 8-9 et 18-19 = pastille, **le nom anglais fait 8 px de haut et occupe les
lignes 10-17** — donc il DÉBORDE dans la 3e rangée de tuiles. Table `typeicon`
(w,h,tileoff) @ `0x961954`. PIÈGE : la planche est de 16 tuiles de large et les
icônes partagent des tuiles (la 3e rangée de tuiles d'une icône = la 1re rangée,
non affichée, d'une autre) — mais aucune zone effacée d'une icône ne recouvre la
zone affichée d'une voisine (vérifié : aucun tileoff des 18 types vanilla ne
diffère de 0x10).

⚠️ **Les deux copies NE sont PAS octet-identiques** (172 tuiles diffèrent sur
0x00-0x140 : pastille/fond en index palette différent). Les **18 types vanilla**
partagent le MÊME tileoff dans les deux copies (FEU 0x24, ROCHE 0x44, TÉNÈBRES
0x8C…) — mais **FÉE (type ajouté par CFRU) est à un tileoff DIFFÉRENT par copie** :
- copie combat `0x961A00` → tuile **0xA8**
- copie résumé `0xB1EC64` → tuile **0x100** (en 0xA8 = garbage inutilisé)
Un seul `TILEOFF["Fairy"]=0xA8` partagé tamponnait « FEE » dans le garbage de la
copie résumé pendant que le vrai badge résumé en 0x100 restait « FAIRY » → bug
« le type fée est encore écrit FAIRY ». Fix = `TILEOFF_OVERRIDE = {0xB1EC64:
{"Fairy": 0x100}}` + `_tileoff(base, icon)` (commit gba_translator `4af9718`).
LEÇON : ne jamais supposer qu'un même offset vaut pour les deux copies — décoder
et rendre CHAQUE badge dans CHAQUE copie ; les types CFRU (Fée) sont placés à part.

Le correctif vit dans `gba_translator/scripts/patch_type_icons_fr.py` (post-build,
idempotent, lit/écrit 3 tuiles, efface TOUTE la bande 10-17 puis redessine ;
remplissage=palette 15, ombre=14). **STEEL→ACIER** (pas METAL),
DARK→TENEBR, ROCK→ROCHE, FIRE→FEU… Appelé par `make build-fr`.
Voir [[unbound-fr-build-lives-in-gba-translator]].

**Police = celle du jeu, 7 px (pas 5)** : les glyphes du `_FONT` sont extraits
**pixel-pour-pixel de la planche anglaise** (FIRE/GROUND/ROCK/GHOST/WATER/NORMAL/
BUG/PSYCHIC) → les noms FR ont EXACTEMENT la même hauteur (lignes 10-16 + ombre 17)
et le même style que l'art anglais/FR intact (POISON, DRAGON). Le « V » n'existe
dans aucun nom de type anglais → dessiné à la main dans le style 3px des Y/T du
jeu. Le « M » du jeu (badge NORMAL) est un M 4px atypique (`#..#/####/#..#×5`) :
on le réutilise tel quel pour que COMBAT colle au modèle. Une police 5px plus
courte = régression « lettres trop petites » signalée par le proprio (corrigé).

⚠️ BUG HISTORIQUE : ne lire/effacer que 2 tuiles (lignes 10-15) laisse les
lignes 16-17 de l'ancien mot anglais visibles SOUS le nom français
(« le tag affiche encore le mot en dessous »). Toujours effacer la bande
complète 10-17 sur 3 tuiles.

**Astuce mGBA capitale (Mac verrouillé)** : sur écran verrouillé mGBA se met en
pause et le bridge Lua ne répond jamais (PING timeout). Créer
`~/.config/mgba/config.ini` avec `pauseOnFocusLost=0` (+ `mute=1`) le fait tourner
sans focus → on peut piloter/screenshot/dumper la VRAM. Lancer mGBA via
`nohup` depuis le shell (pas Popen imbriqué). ROM en lecture seule dans mGBA
(WRITE sur 0x08xxxxxx ignoré → impossible de binary-searcher par écriture live).
Voir [[unbound-mgba-probe-quirks]].
