---
description: Lance la suite de tests (rapide par défaut ; "all" pour python+vitest+playwright)
---

Exécute les tests du projet.

- Sans argument ou `fast` : `make test-python-fast`.
- `standard` : `make test-python`.
- `vitest` : `make test-vitest`. `playwright` : `make test-playwright`.
- `all` : `make test-all`.

Règle 100 % de réussite : si un test échoue, n'le contourne pas — investigue la cause
racine (bytes réels, structure, comparaison ROM espagnole), propose un fix générique,
re-lance toute la suite. Jamais de skip ni de fix hardcodé sur un offset.

Argument: $ARGUMENTS
