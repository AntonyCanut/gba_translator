---
name: unbound-move-status-header-budget-and-token-false-alarm
description: "0x418EB5 \"Déplacer\" (secret-base decoration drag HUD) truncated → \"Dépl\" fix ; piège TextEncoder.encode direct sur {DPAD_ANY}/{SE_SHOP}/{B_BUTTON} = faux positif"
metadata:
  node_type: memory
  type: project
  originSessionId: 68e7048e-7619-4f18-9366-fdd3c851baae
---

Le titre HUD icône+mot pendant le déplacement d'une décoration en Base Secrète
(`0x418EB5`, EN `{F8:0C}Move`) est une cellule à budget d'octets serré :
`max_length = original_length(6) + padding_available(2) + 1 = 9`. « Déplacer »
encodé (11 o une fois le token résolu) dépasse ; fix = `{DPAD_ANY}Dépl` (7 o).
Le footer voisin `0x418E77` (« Déplacer OK Retour ») reste anglais après
rebuild (25 o > budget ~23, pas de pointeur relocalisable trouvé) — pas
régressif, pré-existant, hors scope de ce fix.

**Piège de diagnostic** : tester `TextEncoder.encode()` directement sur un
texte contenant `{DPAD_ANY}`/`{SE_SHOP}`/`{B_BUTTON}`/`{DPAD_UPDOWN}` fait
croire que le token n'est pas reconnu (il est encodé lettre par lettre →
+10 o de garbage). En réalité ces tokens SONT résolus, mais seulement par
`TranslatedROMBuilder._apply_control_placeholders(translation, english,
english_raw)` dans `src/translators/19_build_translated_rom_generic.py`
(gba_translator), appelée pendant l'étape réelle d'injection — pas par
`TextEncoder` seul. Toujours simuler via cette fonction (ou lancer le build
réel) avant de conclure qu'un token brace est cassé. Ne pas confondre avec
[[unbound-brace-control-token-relocation-literal]] (`{FC09}` etc.) qui est
un bug réel documenté ailleurs — ici les tokens `{DPAD_ANY}` etc. fonctionnent
correctement dans le pipeline normal.

**Pattern B confirmé en direct** : au moment du commit, un autre agent a
avancé HEAD entre mon `git add -p` (isolant mon hunk du chantier « Trainer
Catalogue » déjà stagé par un autre agent) et mon `git commit`, provoquant
`fatal: cannot lock ref 'HEAD'`. Le hunk ciblé avait néanmoins déjà été
committé ailleurs par ce même agent concurrent (retrouvé dans HEAD après
re-vérification) — aucune perte, mais illustration concrète du risque
documenté dans [[singularity-worktree-commit-early]] : toujours relire
`git show HEAD -- <fichier>` après un échec de commit avant de re-tenter.
