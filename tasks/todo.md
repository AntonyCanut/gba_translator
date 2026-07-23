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
