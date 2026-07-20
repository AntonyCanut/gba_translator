---
name: singularity-binary-rom-rebase-deadlock-merge-ours-driver
description: "Orchestration replays a dangling duplicate commit that can't binary-rebase the ROM; fix with a merge=ours driver"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 9836aea8-8769-4edb-b1fd-da4823117550
---

Duplicate-dispatch race (voir [[singularity-duplicate-dispatch-same-ticket-race]]) sur gba_translator : deux runs produisent le MÊME fix. Le run le plus avancé merge dans `unbound` (ex. `7787b12f` = fix rebasé sur les tickets suivants, ROM superset correcte). Mon run garde en métadonnées son commit brut sur base ancienne (ex. `2f037328`, parent périmé) — commit DANGLING (aucune ref ne le pointe).

`orchestration_complete` rejoue littéralement ce SHA stocké : `git rebase unbound` de `2f037328` → **conflit binaire sur `output/roms/GenedRom-fr.gba`** à chaque tentative. Git ne sait pas 3-way-merger un binaire ; les ROMs diffèrent (celle d'unbound inclut d'autres tickets). Manipuler la branche du worktree N'AIDE PAS (l'orchestration lit son SHA, pas le tip). rerere N'enregistre PAS les conflits binaires (pas de rr-cache).

**Why:** deadlock de bookkeeping orchestration, pas un souci de code — le fix est DÉJÀ correctement dans unbound (vérifier `font.py` byte-identique + ROM = superset).

**How to apply:** installer un merge driver `ours` sur le chemin ROM, dans le **common git dir partagé** (vu par le contexte de rebase de l'orchestration) :
```
git config merge.ours.driver true                       # écrit .git/config (commun)
printf 'output/roms/GenedRom-fr.gba merge=ours\n' >> "$(git rev-parse --git-common-dir)/info/attributes"
```
Le rebase auto-résout alors la ROM vers la version d'unbound et git DROP le commit (« patch contents already upstream »). ⚠️ Après `git reset --hard <dup>` + rebase, la working tree ROM reste périmée → `git checkout HEAD -- output/roms/GenedRom-fr.gba` pour rendre l'arbre propre AVANT complete (sinon rebounce « uncommitted » / commit ROM périmée). Toujours résoudre en gardant la ROM d'unbound, jamais la périmée (sinon régresse les autres tickets). Voir aussi [[unbound-rom-rebase-conflict-rebuild-resolution]].

**⚠️ DANGER découvert (B-522/#121, 2026-07-17) : ce driver est un footgun permanent, pas un fix ponctuel.** Il a survécu au-delà de son incident d'origine (rien ne le désinstalle) et s'applique désormais à **TOUT** rebase futur du repo, sur n'importe quel ticket. Conséquence : `git rebase unbound` réussit silencieusement (« Successfully rebased », AUCUN conflit signalé) mais **jette discrètement le contenu ROM du commit rejoué**, en gardant la version d'unbound — y compris quand ce commit portait un vrai correctif de traduction (repro : rebase de deux commits successifs modifiant la même cellule ROM → le 2e voit son changement ROM disparaître sans un mot). Rien dans `git status`/`git log` ne le signale ; seul un re-décodage des octets ROM après coup le révèle. J'ai supprimé la mappe d'attribut (`rm "$(git rev-parse --git-common-dir)/info/attributes"`) après avoir confirmé que le deadlock d'origine était résolu — la définition `merge.ours.driver=true` elle-même vit dans `~/.gitconfig` (global, inerte sans mapping de chemin) et n'a pas été touchée. **Règle qui en découle : après TOUT rebase touchant `output/roms/*.gba`, quel que soit le résultat rapporté (conflit ou "clean"), rebuild (`make build-fr`) et re-décoder les octets ciblés avant de committer/compléter — ne jamais faire confiance à un rebase "propre" sur un fichier binaire.** Si ce driver doit être réinstallé pour un futur deadlock, le retirer explicitement une fois le ticket concerné mergé, pas le laisser traîner.
