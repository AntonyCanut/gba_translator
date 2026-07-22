# Issue #140 — « Sort » du Cube → « Tri »

- [x] Lire l’issue, ses commentaires, les règles du dépôt et la compétence de traduction.
- [x] Localiser le bloc graphique réellement affiché à côté de `START` dans le Cube (`0x00EF1B68`).
- [x] Ajouter un test de régression qui échoue tant que le bloc FR n’affiche pas `Tri`.
- [x] Ajouter l’asset FR et l’intégrer au pipeline `build-fr`.
- [x] Exécuter les tests ciblés, reconstruire la ROM et vérifier les octets du bloc actif.
- [x] Contrôler le diff et committer le correctif avec ses tests.

## Revue

- Le libellé est un bloc graphique LZ77 à `0x00EF1B68`, chargé dans le BG1 du Cube.
- `languages/fr/sprites/cube_sort_hint.bmp` remplace uniquement `Sort` par `Tri` ; les dix tuiles finales du bloc restent intactes.
- Le pipeline `build-fr` réinjecte désormais cet asset après les autres réparations graphiques.
- Validation : 30 tests ciblés, 1 471 tests Python, 68 tests Vitest, builds FR/IT/DE, puis `make test-rom` (492 réussis, 37 ignorés).
- Preuve finale : l’asset réextrait de `GenedRom-fr.gba` est identique au BMP source et le replay mGBA affiche `START Tri`.
