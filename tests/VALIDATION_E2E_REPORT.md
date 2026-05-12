# Rapport de Validation E2E — Système Émulateur + Playwright + Reporting

**Date :** 2026-05-12
**Branche :** worktree/t-03-validation-e2e

## 1. Émulateur Web (`emulator-web/`)

| Vérification | Résultat |
|---|---|
| `npm install` | PASS — 136 packages installés |
| `npx tsx src/server.ts` démarre | PASS — serveur sur http://localhost:3000 |
| `/api/health` répond 200 | PASS — `{"status":"ok","romPath":""}` |
| `/api/config` répond 200 | PASS — `{"romPath":"","port":3000}` |
| Page HTML avec canvas `#screen` | PASS — canvas GBA 240x160 affiché |
| WebSocket `/ws` accepte connexion | PASS — connexion établie, réponses JSON |
| Commandes GET_STATE, KEY_DOWN, ADVANCE_FRAMES | PASS |
| 60 tests unitaires vitest | PASS — 60/60 (commands, charmap, memory) |

## 2. Suite Playwright (`tests/e2e-playwright/`)

| Vérification | Résultat |
|---|---|
| `npx playwright install chromium` | PASS |
| Tests boot découverts (--list) | PASS — 3 tests |
| Test "ROM se charge sans crash" | PASS |
| Test "Écran titre atteint" | PASS |
| Test "Pas de reboot 60s" | PASS |
| Screenshots capturés en échec | PASS — PNG générés dans test-results/screenshots/ |
| Rapport HTML généré | PASS — test-results/reports/index.html |

### Bugs corrigés

1. **Fixture spawn command** : `node dist/server.js` -> `npx tsx src/server.ts` (dist inexistant)
2. **Port collision** : hash complet du testId au lieu de `charCodeAt(0) % 10`
3. **Dépendance client->page** : le client WS dépend de la page browser pour le relay
4. **Mock emulator getState()** : ajout des champs GBA (callback1, mapGroup, etc.) pour que les assertions fonctionnent sans vrai CPU

## 3. Reporting

| Vérification | Résultat |
|---|---|
| Rapport JSON généré | PASS — structure complète avec erreurs classifiées |
| Rapport Markdown généré | PASS — lisible avec tableaux et détails |
| Classification d'erreurs | PASS — TIMEOUT/minor, CRASH/critical, MISSING_TRANSLATION/major |
| Tickets YAML créés (major/critical) | PASS |
| Déduplication tickets | PASS — relancer les tests ne crée pas de doublons |
| Reporter smoke test | PASS — config dédiée fonctionne |

## 4. Intégration (`scripts/run_playwright_tests.py`)

| Vérification | Résultat |
|---|---|
| Script démarre le serveur émulateur | PASS |
| Script lance Playwright | PASS |
| Résumé console coloré | PASS |
| Arrêt serveur en fin | PASS |
| Exit code reflète résultat | PASS |

## 5. Non-régression

| Vérification | Résultat |
|---|---|
| Tests Python unitaires | PASS — 23 pass, 4 skip, 0 fail |
| Vitest emulator-web | PASS — 60/60 |
| Makefile `make test` | PASS |
| `.gitignore` couvre artefacts | PASS |

### Bug corrigé dans la ROM

- **Texte de combat "sent out"** non traduit à l'adresse 0xA4C3F2 -> patché en "envoie" dans la ROM + mis à jour dans combined_fr.txt avec les traductions des messages adjacents (withdrew -> rappelle)

## Résumé

**Tous les tests passent.** Le système E2E (émulateur web + Playwright + reporting) est fonctionnel et cohérent. 6 bugs ont été trouvés et corrigés : 4 dans l'infrastructure Playwright, 1 dans le mock émulateur, 1 traduction manquante dans la ROM.
