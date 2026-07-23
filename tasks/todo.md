# Hook Git — test unitaire obligatoire pour les traductions

- [x] Inspecter le hook pré-commit et le garde des traductions déjà présents.
- [x] Ajouter des scénarios unitaires rouges pour l’absence et la présence d’un test.
- [x] Détecter les tests unitaires ajoutés ou modifiés dans l’index Git.
- [x] Rendre le message de blocage impératif et explicite pour un agent IA.
- [x] Exécuter les tests ciblés puis la suite rapide complète.
- [x] Relire le diff, documenter les résultats et committer.

## Revue

- Tout commit non vide est maintenant refusé s’il n’ajoute ou ne modifie aucun
  test unitaire Python, Vitest ou manifeste `protected_entries.yaml`.
- Une suppression de test ou un test E2E ne satisfait pas le garde.
- Le contrôle lit exclusivement l’index Git ; une simulation réelle retourne
  1 sans test et 0 dès que le test unitaire est ajouté à l’index.
- Le message de blocage interpelle explicitement l’agent IA et interdit
  `--no-verify` ainsi que la désactivation du hook.
- Vérifications : 15 tests ciblés, 1 496 tests Python rapides, syntaxe shell et
  contrôle du diff réussis ; le hook complet est exécuté au commit.
