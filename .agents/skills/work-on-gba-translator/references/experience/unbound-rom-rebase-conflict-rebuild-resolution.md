---
name: unbound-rom-rebase-conflict-rebuild-resolution
description: "orchestration_pull rebase conflict sur output/roms/GenedRom-fr.gba (binaire) — résoudre en reconstruisant, pas en choisissant ours/theirs"
metadata:
  node_type: memory
  type: project
  originSessionId: 293d05cf-fd43-4141-a176-cd2ed486cfce
---

Quand deux tickets gba_translator concurrents modifient `languages/fr/combined_fr.txt` et rebuildent la ROM chacun de leur côté, `orchestration_pull` rebase proprement le texte (merge auto sur le fichier texte) mais échoue TOUJOURS sur `output/roms/GenedRom-fr.gba` (fichier binaire, `git` ne sait pas fusionner deux builds différents) — `CONFLICT (content): Merge conflict in output/roms/GenedRom-fr.gba`.

**Why:** Prendre `--ours` ou `--theirs` perdrait la moitié des deux corrections (soit la mienne, soit celle de l'autre ticket) — le seul résultat correct contient les deux.

**How to apply:** Après le conflit, NE PAS choisir un côté. `combined_fr.txt` (déjà auto-mergé par git, texte) contient déjà les deux correctifs → relancer `make prepare-fr && make build-fr` pour régénérer la ROM à partir du fichier mergé, re-décoder/re-tester les offsets touchés (suivre le pointeur vivant, cf. [[unbound-patch-repoint-via-live-cell-not-original-offset]]), puis `git add output/roms/GenedRom-fr.gba && git rebase --continue`. Le diff binaire résultant reste petit (~279 octets sur 32 Mo dans ce cas) — dispersion normale liée à l'ordre de relocalisation, pas un signe d'erreur (voir [[unbound-e2e-tests-gate-committed-rom]]).

**Variante (F-108) :** si MON changement de ROM ne vient PAS de `combined_fr.txt` mais d'un script de patch post-build direct (ex. `status_badges.py`, `status_abbrevs.py`), `make build-fr` complet n'est pas nécessaire/pas souhaitable. Prendre plutôt la ROM de la nouvelle base (`git show HEAD:output/roms/GenedRom-fr.gba > output/roms/GenedRom-fr.gba` pendant le rebase — `HEAD` pointe alors sur la base, pas sur mon commit), puis rejouer uniquement MES scripts de patch dessus (les fichiers `.py` eux-mêmes se rebasent proprement puisqu'ils ne touchent pas `combined_fr.txt`), revalider les tests `@pytest.mark.rom` concernés ET ceux du ticket concurrent (pour confirmer que les deux corrections coexistent), puis `git add` + `git rebase --continue`.

**Round 2 (#47, réouverture après échec merge) :** `orchestration_pull` peut re-avancer la base une 2e fois même après un rebase propre (autres tickets concurrents mergés entre-temps) — rebuild à nouveau depuis `combined_fr.txt` à chaque avancement signalé, ne pas supposer qu'un seul rebuild suffit pour toute la session. Vérifier par `cmp` que le nouveau build diffère du commit précédent (sinon rebuild inutile) et re-décoder les offsets ciblés par CE ticket après CHAQUE rebuild. Piège annexe : un delta de tests passés/skippés après rebuild (ex. 1429→1427 passed, 3→5 skipped) peut venir d'un artefact gitignored manquant (`output/extracted/extracted_texts/englishrom_texts.json`, régénérable via `make extract-en`) plutôt que d'une vraie régression — comparer le nombre de tests AVANT de conclure à un problème.
