# Leçons de tickets

## Issue #161 — valider le terme métier exact avant de figer une traduction

- Une classe anglaise proche d’un terme générique (`Tuber`) ne doit pas être
  assimilée à une autre classe existante (`Swimmer`) sur la seule base du sprite.
- Lorsqu’un contributeur corrige le libellé canonique, protéger à la fois la
  valeur d’origine et la traduction intermédiaire erronée dans
  `protected_entries.yaml`.
- La preuve finale reste le décodage de la cellule de classe dans la ROM
  reconstruite, avec son terminateur `0xFF`.
