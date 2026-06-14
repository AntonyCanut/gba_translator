# Skill : debug-rom-failure

**Quand** : un test échoue, un texte s'affiche mal, ou un pointeur semble cassé.

## Méthode (cause racine, jamais contournement)
1. **Reproduire** : isoler le test/offset fautif, lancer le profil minimal.
2. **Inspecter les bytes réels** dans la ROM (`ROMReader`/`TextCodec`), pas seulement le
   message d'erreur. Pointeur = `offset + 0x08000000`, terminateur `0xFF`, control codes
   `FC/FD/F8/F9/F7`.
3. **Comparer à la référence** espagnole (`spanishrom.gba`) : structure, longueur,
   padding, repointage.
4. **Hypothèse → fix générique** dans `src/core/` ou le script d'étape concerné (résout
   la catégorie, pas un offset précis).
5. **Re-tester 100 %** du corpus + specs Playwright touchées.

## Interdits
- Skip/xfail pour masquer l'échec ; `if offset == 0x...: return True` ; « cas limite
  acceptable ». Sauvegarder en jeu pendant une sonde mGBA.
