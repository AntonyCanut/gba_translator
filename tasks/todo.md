# B-552 — Fix mail move-to-bag label mapping

- [x] Trace the rebuilt ROM mismatch to the dedicated patch preimage guard.
- [x] Add a regression for the generic « Dépl au sac » build output.
- [x] Normalize supported source/build preimages to « Vers le sac ».
- [x] Run focused tests, the fast suite, and decoded-ROM verification.
- [x] Review the diff and commit the focused generation-path fix.

## Review

- Root cause: the generic build could leave the older 11-byte « Dépl au sac »
  preimage, while `pc_move_labels.py` accepted only the English bytes and
  skipped the canonical in-place rewrite.
- The dedicated patch now accepts only the two known upstream preimages
  (English and the legacy French abbreviation) and normalizes both to
  « Vers le sac »; its existing unknown-byte safety guard and idempotence stay
  intact.
- Verification: 15 focused patch tests passed; the guarded commit passed
  1,511 Python tests (1 skipped), 68 Vitest tests, and full FR/IT/DE builds.
  The rebuilt FR ROM test passed and bytes at `0x4177DD` decoded exactly to
  « Vers le sac ».
- The rebuilt ROM artifact was restored after verification because the parent
  ticket still tracks four unrelated rebuild regressions; this slice does not
  ship those changes.

# Issue #143 — icônes de statut FR

- [x] Lire l’issue et confirmer l’absence de commentaires.
- [x] Identifier les quatre blocs LZ77 utilisés en combat et dans l’équipe.
- [x] Ajouter l’extraction/réinjection en PNG indexé sans perdre les indices palette.
- [x] Fournir l’asset PNG rééditable des badges FR.
- [x] Tester le round-trip PNG et tous les badges dans les quatre blocs ROM.
- [x] Reconstruire la ROM FR et vérifier les pixels décodés.
- [ ] Relire le diff, committer et clôturer l’issue GitHub.

## Revue

- La couture de bordure venait d’un indice palette `9` forcé dans les tuiles
  centrales, alors que deux copies utilisent l’indice `1`. Le patch lit
  désormais l’indice de la tuile de fermeture propre à chaque bloc.
- `extract_sprite.py --all-blocks` produit quatre PNG indexés numérotés ;
  `insert_sprite.py --all-blocks` les réinjecte séparément pour conserver les
  palettes de combat et du menu.
- Le registre autorise le LZ77 compact uniquement pour ces badges : le flux
  VRAM-safe dépassait de trois octets et rendait la réinjection impossible.
- Vérifications : build FR complet réussi, 25 tests ciblés, round-trip PNG
  réel 4/4 blocs, puis 1 508 tests Python rapides réussis (1 ignoré).

# Issue #142 — « Annul » → « Annul. » dans la liste Pokédex

- [x] Ajouter un test rouge sur la valeur active de l’entrée `0x415F51`.
- [x] Corriger chirurgicalement la source FR et protéger la valeur attendue.
- [x] Regénérer la chaîne FR et reconstruire la ROM jouable.
- [x] Vérifier les octets décodés depuis le pointeur vivant du Pokédex.
- [x] Exécuter les tests ciblés, ROM et rapides.
- [x] Relire le diff et committer le correctif.

## Revue

- La valeur active `0x415F51` est désormais
  `{DPAD_UPDOWN}Choix {SE_SHOP}OK {B_BUTTON}Annul.` et est protégée par le
  manifeste FR.
- Les trois pointeurs vivants `0x103234`, `0x103514` et `0x1423A8` ciblent la
  même chaîne CFRU terminée, décodée en `Choix / OK / Annul.`.
- Le build FR est byte-identique sur deux reconstructions consécutives.
- Vérifications : 4 tests ciblés, 1 498 tests Python rapides, 68 tests Vitest,
  puis 497 tests ROM/E2E réussis (37 scénarios optionnels ignorés).

# Pipeline de release — reprise d’upload d’artefact

- [x] Lire les journaux du run #81 et isoler la cause racine.
- [x] Vérifier l’historique autour de `e064865d`.
- [x] Écrire un test de régression pour l’échec transitoire d’upload.
- [x] Ajouter une seconde tentative sûre dans `release.yml`.
- [x] Brancher le garde ciblé dans le hook pré-commit.
- [x] Exécuter les validations, relire le diff et committer.
- [x] Relancer la pipeline et confirmer son résultat.

## Revue

- Le build et la vérification FR du run #81 étaient réussis ; seul
  `FinalizeArtifact` a reçu un `403 Forbidden`, après l’envoi complet des octets.
- `e064865d` ne modifie pas la CI. La dépendance à l’artefact sans reprise vient
  de la parallélisation introduite par `94acdd8a`.
- Le premier upload est toléré uniquement pour déclencher une seconde tentative
  non tolérée, avec `overwrite: true` pour nettoyer un éventuel artefact partiel.
- Le test ciblé, la syntaxe YAML/shell, `actionlint`, `git diff --check` et les
  1 501 tests Python rapides passent (`1 500 passed`, `1 skipped`).
- La tentative 2 du run #81 est verte : builds FR/IT/DE, trois artefacts et
  publication de la release réussis.

# Carte mondiale — libellé court « Annul. » après rebuild

- [x] Comparer les pointeurs vivants de la ROM commitée et du rebuild régressé.
- [x] Ajouter un test rouge reproduisant le repoint vers « Annuler ».
- [x] Restaurer les deux cellules courtes et les trois vrais pointeurs carte.
- [x] Reconstruire la ROM FR et vérifier les octets pointés.
- [x] Exécuter les tests ciblés et la validation rapide pertinente.
- [x] Relire le diff, committer et documenter les résultats.

## Revue

- Le rebuild régressé envoyait `0xC06FC`, `0xC1B28` et `0xC50C0` vers une
  relocalisation de la chaîne générique « Annuler ». Le patch post-build
  restaure désormais les cibles carte `0x418E95`, `0x418E9E`, `0x418E95`.
- Les deux cellules reçoivent `{SE_SHOP}Annul.` sur exactement 9 octets,
  terminateur compris, soit la largeur de `{SE_SHOP}Cancel`.
- La chaîne générique « Annuler » et les pointeurs du menu Équipe restent
  inchangés ; une seconde application du patch est sans effet.
- Vérifications : 1 512 tests Python rapides et 68 tests Vitest réussis,
  builds FR/IT/DE réussis, puis 3 assertions ROM ciblées réussies.
