# Régression #111/#131 — résidu « Annul. » sur la carte mondiale

- [x] Reproduire le test ROM et relever les octets/pointeurs vivants.
- [x] Tracer l’historique #111/#131 et confirmer la suppression du patch post-build.
- [x] Ajouter des tests unitaires synthétiques pour le vrai littéral `0x9FB64`.
- [x] Créer un patch post-build idempotent qui restaure la cellule `0x418E77` et son pointeur.
- [x] Enchaîner le patch dans `make build-fr` après les autres libellés de menu.
- [ ] Exécuter les tests ciblés, le rebuild déterministe et les validations du dépôt.
- [ ] Contrôler le diff, committer et rebaser sur `unbound`.

## Revue

À compléter après les vérifications finales.
