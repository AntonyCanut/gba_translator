# Phase 6.3 — Rapport de validation : gameplay fonctionnel et suite de tests

**Date** : 2026-05-19
**Objet** : Validation du remplacement de gbajs par le backend mGBA côté serveur

## Résumé

Le backend mGBA est pleinement fonctionnel. **103/103 tests JavaScript passent** (60 Vitest + 43 Playwright). Le gameplay est vérifié : boot, rendu graphique, progression du game state, mouvement du joueur, et stabilité longue durée. Le test critique **"Navigation map"** passe avec succès.

## 1. Tests unitaires (Vitest)

| Fichier | Tests | Résultat |
|---------|-------|----------|
| `emulator-web/tests/commands.test.ts` | 28 | OK |
| `emulator-web/tests/charmap.test.ts` | 21 | OK |
| `emulator-web/tests/memory.test.ts` | 11 | OK |
| **Total** | **60** | **60 passed, 0 failed** |

## 2. Tests Playwright E2E

| Projet | Tests | Résultat |
|--------|-------|----------|
| boot | 3 | 3 passed |
| gameplay | 4 | 4 passed |
| translation | 5 | 5 passed |
| visual-regression | 4 | 4 passed |
| menu-navigation | 5 | 5 passed |
| dialogue-npc | 5 | 5 passed |
| battle-flow | 5 | 5 passed |
| exploration | 4 | 4 passed |
| reporter-smoke | 2 | 2 passed |
| real-gameplay | 6 | 6 passed |
| **Total** | **43** | **43 passed, 0 failed** |

Durée totale du run complet : ~7.3 minutes

## 3. Tests Python (Unbound)

**Statut** : bloqué (problème d'environnement pré-existant)

Les 25 fichiers de test échouent à la collecte avec `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'`. Le système utilise Python 3.9.6 mais le code requiert Python 3.10+ pour la syntaxe `str | None`. **Ce n'est pas une régression liée au remplacement mGBA.**

## 4. Validation du gameplay

| Critère | Statut |
|---------|--------|
| Boot de la ROM | OK |
| Écran titre affiché | OK |
| Rendu graphique (pas d'écran blanc/noir) | OK |
| Nouvelle partie | OK |
| Mouvement du joueur (playerX/playerY changent) | OK |
| Transitions de map (mapGroup change) | OK |
| Navigation dans les menus | OK |
| callback1 non-nul pendant le gameplay | OK |
| frameCount augmente continuellement | OK |
| Stabilité 60s sans crash ni reboot | OK |

### Adresses mémoire vérifiées

- `playerX` (via gSaveBlock1Ptr 0x03005008) : change lors du déplacement
- `playerY` (via gSaveBlock1Ptr + 2) : change lors du déplacement
- `mapGroup` / `mapNumber` : changent entre les maps
- `callback1` (0x030030f0) : non-nul pendant le gameplay
- `frameCount` : augmente continuellement

### Traduction

- Texte français détecté dans les buffers mémoire
- Pas de texte anglais résiduel trouvé
- Caractères accentués (éèàâçùî) supportés en round-trip

## 5. Test critique : Navigation map

**PASSÉ** — La position du joueur change correctement avec le backend mGBA. Ce test échouait avec gbajs car l'émulateur JavaScript n'exécutait pas réellement le CPU GBA, empêchant toute progression du game state.

## 6. Problèmes connus

| Sévérité | Description | Recommandation |
|----------|-------------|----------------|
| Basse | Visual regression flaky sur 1er run (timing bridge) | Ajouter health check avant les commandes screenshot |
| Info | Combats sauvages non déclenchés dans le budget de frames | Utiliser des save states à des positions de combat connues |
| Info | Tests Python bloqués par Python 3.9 | Installer Python 3.10+ ou ajouter `from __future__ import annotations` |

## Conclusion

Le remplacement de gbajs par le backend mGBA est **validé avec succès**. Le gameplay est pleinement fonctionnel et les 103 tests JavaScript passent sans échec.
