# Régression #111/#131 — résidu « Annul. » sur la carte mondiale

- [x] Reproduire le test ROM et relever les octets/pointeurs vivants.
- [x] Tracer l’historique #111/#131 et confirmer la suppression du patch post-build.
- [x] Ajouter des tests unitaires synthétiques pour le vrai littéral `0x9FB64`.
- [x] Créer un patch post-build idempotent qui restaure la cellule `0x418E77` et son pointeur.
- [x] Enchaîner le patch dans `make build-fr` après les autres libellés de menu.
- [x] Exécuter les tests ciblés, le rebuild déterministe et les validations du dépôt.
- [x] Contrôler le diff et committer la ROM reconstruite.

## Revue

- Cause : #131 a retiré l’ancien patch `world_map_action_labels.py`; le rebuild
  pouvait donc conserver `Annul.` à `0x418E77` malgré la source `Annul` protégée.
- Le nouveau patch réécrit la cellule canonique et force le seul littéral vivant
  `0x9FB64` à la viser après chaque `make build-fr`.
- La ROM finale contient `0x9FB64 → 0x418E77` et la chaîne se termine par
  `bbe2e2e9e0ff`, sans l’octet `ad` du point résiduel.
- Vérifications : 7 tests carte-monde, 1 476 tests Python rapides, 68 tests
  Vitest, builds FR/IT/DE, deux rebuilds FR octet-identiques et 487 tests ROM
  hors émulateur réussis (34 ignorés).
- Le probe mGBA italien non lié n’a pas atteint son premier combat sur la map
  4.10 ; il n’a détecté ni gel ni résidu anglais. Les gardes déterministes de ce
  ticket sont toutes vertes.
