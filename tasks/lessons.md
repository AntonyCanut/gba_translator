# Leçons de tickets

## R-608 — distinguer le build public de la régénération mainteneur

- Publier uniquement un patch ne suffit pas si la CI télécharge encore une ROM
  pour le fabriquer : un vrai flux sans ROM prend le bundle BPS suivi comme
  unique entrée de validation et de publication.
- Les E2E de l'artefact doivent matérialiser localement leurs ROMs depuis la
  seule source anglaise de l'utilisateur. Les gardes qui dépendent des bases
  historiques patched-FR/ES appartiennent à un profil `private_build` séparé.
- Un manifeste BPS fiable lie une source commune, le numéro de version, les
  tailles, CRC32 et SHA-256. La promotion locale doit refaire le round-trip
  contre les cibles du builder avant un remplacement transactionnel.

## B-608 — un workflow de publication corrigé doit s’auto-déclencher

- Un filtre `on.push.paths` limité aux artefacts ignore aussi un push qui ne
  modifie que le workflow censé réparer leur publication.
- Si le prochain push doit appliquer la correction distante, inclure le fichier
  du workflow dans ses propres chemins surveillés et verrouiller ce contrat par
  un test de structure YAML.
- Un `workflow_dispatch` réussi ne prouve pas le déclenchement sur push : pour
  diagnostiquer, comparer systématiquement `event`, `headSha` et fichiers du commit.

## Issue #169 — employer « lettre » pour l’objet Courrier

- Dans le message d’absence du stockage d’objets du PC, la formulation
  naturelle attendue est « Pas de lettre ici. », même si les autres actions
  du menu nomment la catégorie « Courrier ».
- Une correction de texte doit conserver les contrôles de fin de chaîne : ici
  `{PAUSE_UNTIL_PRESS}` devient bien `FC 09` avant le terminateur `FF`.
- La preuve finale suit chaque pointeur vivant et compare les octets de la ROM
  reconstruite, pas uniquement la ligne de traduction.

## Issue #161 — valider le terme métier exact avant de figer une traduction

- Une classe anglaise proche d’un terme générique (`Tuber`) ne doit pas être
  assimilée à une autre classe existante (`Swimmer`) sur la seule base du sprite.
- Lorsqu’un contributeur corrige le libellé canonique, protéger à la fois la
  valeur d’origine et la traduction intermédiaire erronée dans
  `protected_entries.yaml`.
- La preuve finale reste le décodage de la cellule de classe dans la ROM
  reconstruite, avec son terminateur `0xFF`.

## Issue #176 — identifier l'écran avant de nommer ses pointeurs

- Deux chaînes identiques ne peuvent pas être attribuées à leur écran par leur seul texte
  ou par leur proximité avec du code supposé : il faut provoquer une modification isolée
  ou rejouer l'écran concerné.
- Les pointeurs `0x6FE80` et `0x1EB6220` alimentent l'écran de sauvegarde depuis
  `0x416190`; le pointeur `0xCF34` alimente la carte Dresseur depuis `0x41B6DC`.
- Une garde ROM doit nommer et vérifier le consommateur observé. Un décodage correct au
  mauvais pointeur protège précisément la régression inverse.
