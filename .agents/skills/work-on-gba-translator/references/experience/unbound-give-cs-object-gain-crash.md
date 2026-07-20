---
name: unbound-give-cs-object-gain-crash
description: "Freeze 'pas de gain d'objet' post-Zeph (don CS Coupe par NPC, box give-CS map 46.0). RÉSOLU POUR DE BON (juin 2026, commit 2da7c92 sur gba_translator@unbound). Cause : desc Coupe 0x00482BD5 (slot VIDE 0xFF en EN, texte FR débordant en FR) lue via les structs field-move 0x083DEA80/0x0887AD30 → run fusionné sans 0xFF → GetStringWidth boucle. Fix reference-driven STRICTEMENT gardé (rejette police 0x489A08/data 0x489F74/code). LEÇON CAPITALE : détecter le freeze UNIQUEMENT par hash d'écran (pixels figés), JAMAIS par position (joueur immobile en dialogue) ni PC (REGISTERS = IRQ BIOS 0x1C4)."
metadata:
  node_type: memory
  type: project
  originSessionId: 20d787bc-9f7a-4332-8269-440187c6c042
---

Ticket « Problème pas de gain d'objet » (T-23, Unbound FR). Après **Zeph**, enlèvement → NPC donne la **CS Coupe/Cut** ; freeze sur la box give-CS (map 46.0:22,9). Build vivant : [[unbound-fr-build-lives-in-gba-translator]].

## ✅ RÉSOLU ET VÉRIFIÉ EN JEU (commit `2da7c92`) — après 9 passages ratés

**⚠️ LEÇON N°1 — POURQUOI 9 PASSAGES ONT ÉCHOUÉ : la détection de freeze.**
- **Position = inutile** : le joueur reste IMMOBILE pendant toute la conversation give-CS ; « bloqué à 46.0:22,9 » est vrai pour un dialogue SAIN comme pour un gel. Un détecteur position déclenche des faux « frozen ».
- **PC = inutile** : la commande `REGISTERS` du bridge lit les registres DANS l'IRQ VBlank → PC **toujours = BIOS `0x000001C4`**, que la boucle principale tourne ou non. Le « PC en GetStringWidth 0x08006xxx » des passages précédents était un artefact.
- **SEUL signal fiable = HASH D'ÉCRAN** : screenshot identique au pixel près sur ~45 pressions A consécutives = vrai gel. Sinon (l'écran change) = le dialogue avance, PAS de gel. `scripts/verify_givecs_no_freeze.mts` fait exactement ça (charge `.ss9`, mash A, hash écran), exit 0/1/2.

**Cause racine (prouvée in-engine via `.ss9` + hash écran) :** la desc de Coupe est à **`0x00482BD5`** — slot **VIDE (`0xFF`) en EN**, mais le build FR y écrit une longue phrase qui déborde et détruit le `0xFF` voisin → run fusionné *« Une attaque de base…abattre des arb**Frappe l'ennemi avec une rafale…** »* sans terminateur. Lu sur le chemin give-CS via les **structs field-move `0x083DEA80` / `0x0887AD30`** ; le word-wrap CFRU appelle `GetStringWidth` qui scanne un `0xFF` qui ne vient jamais → boucle infinie → écran figé. (EN ne gèle pas : slot vide = terminé immédiatement.) Au gel, `gStringVar4` (`0x02021D18`) = ce run non terminé.

**Pourquoi le « fix 9ᵉ passage » (3d3e5da) ne tenait pas :** (a) il avait été **reverté en working-tree** vers une version table-only (`0x488708` seule) → le build de l'utilisateur ne corrigeait PAS les structs ; (b) un scan **region-blind** repointe aussi la **police `0x489A08`**, le **data-struct `0x489F74`** et du **code Thumb** qui contiennent des valeurs dans la plage du pool → corruption → revert.

**Fix qui tient (`patch_dup_move_descriptions_fr.py`, dernier de `make build-fr`) :** reference-driven MAIS **strictement gardé**. Scanne tout pointeur word-aligné dans le pool `[0x482000,0x48A000)`, garde uniquement les cibles qui sont une **vraie description FR débordante** (ratio lettres, espacement mots, densité voyelles FR, pas de glyphe dominant — rejette police/data/code), relocalise une copie `combined_fr.txt` terminée `0xFF` par cible, repointe **chaque** référence. 4 offsets sans source autoritaire, référencés seulement par des singletons code/data isolés (EN a les mêmes, ne gèle pas) → laissés tels quels.

**Vérification before/after (ce qui manquait) :** ROM re-cassée (structs → `0x482BD5`) → `verify`=1 (gel) ; ROM corrigée → `verify`=0 (la cutscene se termine). `make build-fr` → structs give-CS → copie Coupe terminée. Gardes : `test_givecs_move_desc_freeze.py` (statique : aucun pointeur **clusterisé** = table/struct array ne pointe sur une desc FR non terminée ; rouge sur build buggé = 4 cellules struct give-CS, vert après ; **exclure les singletons isolés** non-clusterisés qu'EN partage) ; `test_givecs_freeze_replay.py` (rejoue via `verify_givecs_no_freeze.mts`, skip sans mGBA). Suite 470 passed / 30 skip ; pre-commit 334.

**How to apply (général Unbound) :**
- Pour TOUT freeze in-game : reproduire via savestate **avant** la séquence, mash A, **juger par hash d'écran**. Ne jamais conclure depuis la position ni le PC.
- Trouver la chaîne non terminée dans `gStringVar4` (`0x02021D18`) ou via les pointeurs RAM→ROM sans `0xFF`. Remonter au(x) consommateur(s).
- Repointer/terminer TOUTES les copies, mais **garder** par « la cible est-elle un vrai texte ? » et restreindre l'écriture aux **structures denses** (tables/struct arrays clusterisées) — un repoint region-blind corrompt police/data/code.
- Voir aussi [[unbound-summary-screen-labels]] (pointeurs dupliqués), [[unbound-mgba-harness-flags-invalid]], [[unbound-mgba-probe-quirks]] (flags/PC harness faux).

---

## ⚠️ RÉCIDIVE (B-108, juin 2026, commit fix sur gba_translator@test/pr) — le slot terminé-mais-corrompu

Le scan reference-driven est **gaté sur l'overflow** (`is_overflow` = aucun `0xFF` dans le budget). Mais une desc de move VOISINE peut déborder vers l'avant et déposer SON `0xFF` **dans** le slot `0x482BD5` → le slot devient **terminé-mais-corrompu** (`'tistique\nAttack .'` = queue de « …la statis**tique**\nAttack . » d'une danse-lames débordante). `is_overflow`=False → le scan le **rate** → les 4 consommateurs de Coupe (structs field-move `0x3DEA80`/`0x87AD30` + tables move-info `0x488720`/`0x904038`, tous → `0x482BD5`) montrent du charabia (et selon le build, peuvent re-déborder → gel). Pas de gel ici mais texte give-CS faux ; `test_give_cs_field_move_description_is_terminated` rouge.

**Fix :** `force_field_move_descriptions()` dans `patch_dup_move_descriptions_fr.py` — garde dédiée, NON gatée sur overflow, sur une liste documentée `FIELD_MOVE_DESC_OFFSETS = (0x482BD5,)`. Garde par contenu : agit seulement si `rom[off:]` ≠ texte `combined_fr` encodé ; relocalise la copie terminée + repointe TOUS les référents du pool. Idempotent (après repoint, plus aucune cellule ne vise l'offset pool). **Leçon :** l'overflow-gate ne voit pas un slot qu'un voisin a terminé — pour les slots VIDES-en-EN à consommateurs connus (give-CS field-move), garder explicitement par contenu autoritaire, pas par détection d'overflow. Build FR non rebâti from-scratch (dérive ~0,2 %) : patch appliqué en place sur la ROM committée — voir [[unbound-e2e-tests-gate-committed-rom]].

---
*Historique : runs 1-7 (statique seul, jamais rejoué) = faux. Run 8 (`08e7ba2`) table-only. Run 9 (`3d3e5da`) reference-driven mais region-blind + reverté + détection position/PC non fiable → l'utilisateur gelait encore. Run 10 (`2da7c92`) : garde stricte + détection hash écran + preuve before/after en jeu. CS = Coupe/Cut. mGBA `/opt/homebrew/bin/mgba` 0.11 `--script`, bridge TS `emulator-web/src/mgba-bridge.ts` (loadState/readMemory/screenshot/getState).*
