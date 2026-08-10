# Leçons de tickets

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
