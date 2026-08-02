# Injection du BMP des badges de statut — plan d’implémentation

> **Pour les agents d’exécution :** utiliser `superpowers:executing-plans` et suivre chaque case dans l’ordre. L’exécution reste locale à cette session, sans sous-agent.

**Objectif :** Injecter fidèlement le BMP fourni dans les quatre blocs de badges FR utilisés par le combat et les écrans Pokémon.

**Architecture :** `languages/fr/sprites/status_badges.bmp` devient l’unique source visuelle. Le patch charge sa grille indexée, remappe seulement la bordure canonique `9` vers l’indice de bordure de chaque slot cible, puis remplace la planche complète avant recompression LZ77 compacte.

**Stack technique :** Python 3.11, BMP indexé 4 bpp, tuiles GBA 4 bpp, LZ77, pytest.

## Contraintes globales

- Ne jamais modifier `input/roms/englishrom.gba` ni `input/roms/spanishrom.gba`.
- Conserver un seul asset rééditable et les palettes propres à chaque bloc.
- Faire échouer le test avant toute modification de l’asset ou du patch.
- Reconstruire `output/roms/GenedRom-fr.gba` et lancer `make test-rom`.
- Ne jamais pousser la branche distante.

---

### Tâche 1 : protéger et injecter le dessin fourni

**Fichiers :**

- Créer : `languages/fr/sprites/status_badges.bmp`
- Modifier : `languages/fr/patches/status_badges.py`
- Modifier : `tests/test_patch_status_badges_fr.py`
- Modifier : `output/roms/GenedRom-fr.gba`
- Modifier : `tasks/todo.md`

**Interfaces :**

- Consomme : `read_indexed_image(Path) -> tuple[int, int, Grid]`, `grid_to_tiles(Grid, int, int) -> bytes` et le BMP 32 × 64 fourni.
- Produit : `load_badge_tiles() -> bytes` et quatre blocs LZ77 dont l’empreinte visuelle normalisée vaut `9ab29c8b025c697e84b864c64ed4f082f290b049bd7a047b1d2e146076ae8d41`.

- [x] **Étape 1 : écrire le test rouge**

Ajouter un test qui copie la ROM FR courante, exécute `apply_patches`, extrait chacun des quatre blocs, normalise les bordures `1` en `9` à partir des tuiles de fermeture et compare l’empreinte SHA-256 des 2 048 indices de pixels à la valeur littérale ci-dessus.

- [x] **Étape 2 : vérifier l’échec attendu**

Exécuter :

```bash
python3 -m pytest tests/test_patch_status_badges_fr.py -q
```

Résultat attendu : échec sur l’empreinte de la planche, car l’ancien générateur diffère de 54 pixels et ne remplace pas entièrement `PKRS`.

- [x] **Étape 3 : ajouter l’asset et l’implémentation minimale**

Copier byte pour byte le BMP fourni vers `languages/fr/sprites/status_badges.bmp`. Remplacer les tables de glyphes et le rendu par un chargement validé de l’asset, une conversion en tuiles et un remappage limité aux pixels de bordure de chaque slot.

- [x] **Étape 4 : vérifier le passage au vert ciblé**

Exécuter :

```bash
python3 -m pytest tests/test_patch_status_badges_fr.py tests/unit/test_sprite_bmp.py tests/unit/test_sprite_rom.py -q
```

Résultat attendu : tous les tests réussissent, y compris les quatre empreintes de blocs.

- [x] **Étape 5 : committer les sources avant le build**

Après la vérification ciblée, committer l’asset, le patch, le test et la
documentation avec des chemins explicites et le message :

```bash
git commit -m "fix(fr): injecter le BMP des icônes de statut (#143)"
```

Relire immédiatement le périmètre avec `git show --stat --oneline HEAD`.

- [x] **Étape 6 : reconstruire et vérifier la ROM**

Exécuter :

```bash
make build-fr
make test-rom
```

Puis extraire les quatre blocs et confirmer leur empreinte normalisée ainsi que leur égalité de formes. Committer séparément la ROM avec `build(rom): appliquer le BMP des icônes de statut (#143)`.

- [x] **Étape 7 : lancer les gardes globales**

Après `detect_test_processes`, exécuter `make test` et `make test-vitest`, contrôler `git diff --check` et relire les deux commits. Ne poursuivre que si leur périmètre est exact.
