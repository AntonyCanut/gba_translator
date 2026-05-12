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
| Page HTML avec canvas `#screen` | PASS — canvas GBA 240×160 affiché |
| WebSocket `/ws` accepte connexion | PASS — connexion établie, réponses JSON |
| Commande GET_STATE | PASS — retourne état proxy |
| Commande KEY_DOWN | PASS — acceptée |
| Commande SCREENSHOT (sans browser) | FAIL attendu — "Browser emulator not connected" (architecture relay) |
| Commande ADVANCE_FRAMES | PASS (via browser relay) |
| 60 tests unitaires vitest | PASS — 60/60 (commands, charmap, memory) |

## 2. Suite Playwright (`tests/e2e-playwright/`)

| Vérification | Résultat |
|---|---|
| `npx playwright install chromium` | PASS |
| Tests boot découverts (--list) | PASS — 3 tests |
| Test "ROM se charge sans crash" | PASS |
| Test "Écran titre atteint" | PASS (après fix port) |
| Test "Pas de reboot 60s" | FAIL attendu — callback1=0 (émulateur mock, pas de vrai CPU) |
| Screenshots capturés en échec | PASS — PNG générés dans test-results/screenshots/ |
| Rapport HTML généré | PASS — test-results/reports/index.html |

### Bugs corrigés dans la fixture

1. **Spawn command** : `node dist/server.js` → `npx tsx src/server.ts` (dist n'existe pas, le TS n'était pas compilé)
2. **Port collision** : `testId.charCodeAt(0) % 10` → hash complet du testId (évite que tous les tests du même fichier partagent le même port)
3. **Dépendance client→page** : le client WS doit dépendre de la page browser pour que le relay WebSocket fonctionne

## 3. Reporting

| Vérification | Résultat |
|---|---|
| Rapport JSON généré | PASS — `test-results/reports/report-*.json` avec structure complète |
| Rapport Markdown généré | PASS — `test-results/reports/report-*.md` lisible |
| Classification d'erreurs | PASS — TIMEOUT/minor, CRASH/critical, MISSING_TRANSLATION/major |
| Tickets YAML créés (major/critical) | PASS — `tickets/auto-crash-err-002.yaml` |
| Tickets minor non créés | PASS — ERR-001 (TIMEOUT/minor) ignoré |
| Déduplication tickets | PASS — relancer les tests ne crée pas de doublons |
| Reporter smoke test | PASS — config dédiée, erreur intentionnelle classifiée correctement |

## 4. Intégration (`scripts/run_playwright_tests.py`)

| Vérification | Résultat |
|---|---|
| Script démarre le serveur émulateur | PASS — PID affiché |
| Script lance Playwright | PASS |
| Résumé console coloré | PASS — total, réussis, échoués, taux |
| Affichage erreurs avec sévérité | PASS |
| Comptage tickets | PASS — "1 total, 1 ouverts" |
| Arrêt serveur en fin | PASS |
| Exit code reflète résultat | PASS — exit 1 si échecs |

## 5. Non-régression

| Vérification | Résultat |
|---|---|
| Tests Python unitaires | 11 PASS, 1 FAIL préexistant (ROM), 1 SKIP |
| Makefile `make test` | PASS — cible fonctionne |
| `.gitignore` couvre artefacts | PASS — test-results/, node_modules/, tickets/auto-*.yaml, dist/ |
| Pas de conflit dépendances | PASS |

## Résumé

Le système de test E2E est **fonctionnel et cohérent**. Les trois couches (émulateur web, Playwright, reporting) s'intègrent correctement. Trois bugs ont été trouvés et corrigés dans la fixture Playwright. Les échecs de tests restants sont attendus (émulateur mock sans vrai CPU GBA / absence de ROM traduite).
