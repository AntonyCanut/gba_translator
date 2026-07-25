# Caps de la barre de vie du résumé DE/IT — plan d’implémentation

> **Pour les agents :** sous-compétence requise : appliquer
> `superpowers:test-driven-development` tâche par tâche, puis
> `superpowers:verification-before-completion`.

**Objectif :** restaurer dans les ROM DE et IT le corps anglais à cinq rangées
et les deux caps de la barre de vie de la page « Capacités Pokémon », tout en
conservant les libellés localisés « KP » et « PS ».

**Architecture :** chaque patch localisé restaure les 12 tuiles anglaises du
bloc LZ77 `0x00E9B4B8`, puis repeint seulement les 6×14 pixels réservés aux
lettres. Les tuiles 0–8 et 11 restent identiques à l’anglais ; la colonne 7 de
la tuile 10, qui contient le cap gauche, n’est jamais écrite.

**Stack :** Python 3.11, pytest, art 4bpp GBA, compression LZ77, builders
génériques `make build-de` et `make build-it`.

## Contraintes globales

- Ne jamais modifier `input/roms/englishrom.gba`.
- Écrire les tests avant le code et observer leur échec attendu.
- Redessiner « KP » et « PS » avec quatre rangées de remplissage et `_outline`.
- Accepter les états connus EN, ES et déjà localisés sans caps.
- Le flux recompressé doit tenir dans le créneau de 192 octets.
- Ne pas créer de scénario Playwright sans sauvegarde DE/IT compatible.

---

### Tâche 1 : Gardes unitaires DE sur le corps et les caps

**Fichiers :**

- Modifier : `tests/test_patch_hp_labels_de.py`

**Interface :**

- Consomme : `GREEN_EN_TILES`, `GREEN_NROWS`, `GREEN_NCOLS`,
  `_draw_green_label`.
- Produit : gardes sur la géométrie quatre rangées, les tuiles 0–8 et 11, le
  cap gauche de la tuile 10 et la parité de la ROM DE face à la ROM anglaise.

- [x] Ajouter les assertions littérales sur les rangées de remplissage et la
  boîte 6×14.
- [x] Comparer les tuiles du corps et le cap droit à l’art anglais.
- [x] Comparer la demi-octet de la colonne 7 de la tuile 10 à l’art anglais.
- [x] Lancer `python3 -m pytest tests/test_patch_hp_labels_de.py -q` et
  constater l’échec causé par l’ancien art espagnol.

### Tâche 2 : Port DE minimal

**Fichiers :**

- Modifier : `languages/de/patches/hp_labels.py`

**Interface :**

- Consomme : une planche connue EN/ES/KP sans caps.
- Produit : une planche anglaise complète avec « KP » dans la boîte 6×14.

- [x] Définir la planche anglaise/espagnole complète, le créneau de 192 octets
  et la géométrie quatre rangées de « KP ».
- [x] Restaurer la planche anglaise avant d’appliquer remplissage et contour.
- [x] Valider les 12 tuiles et transmettre `slot_len=192` à la recompression.
- [x] Relancer le test DE et obtenir 100 % de réussite.

### Tâche 3 : Gardes unitaires et port IT

**Fichiers :**

- Modifier : `tests/unit/it/test_patch_hp_labels_it.py`
- Modifier : `languages/it/patches/hp_labels.py`

**Interface :**

- Consomme : la même géométrie de planche que DE.
- Produit : une planche anglaise complète avec « PS » dans la boîte 6×14.

- [x] Ajouter les gardes IT équivalentes et observer leur échec.
- [x] Redessiner « PS » sur quatre rangées, sans écrire les colonnes 14–15.
- [x] Restaurer les 12 tuiles anglaises et utiliser le créneau de 192 octets.
- [x] Relancer les deux fichiers de tests ciblés et obtenir 100 % de réussite.

### Tâche 4 : Builds et preuve ROM

**Fichiers :**

- Générer : `output/roms/GenedRom-de.gba`
- Générer : `output/roms/GenedRom-it.gba`

**Interface :**

- Consomme : builders génériques et ROM anglaise de référence.
- Produit : ROMs DE/IT dont le bloc décodé possède le corps et les deux caps
  anglais, avec les seuls pixels de lettres localisés.

- [x] Exécuter le détecteur de tests/processus puis les validations ciblées,
  `make test-python-fast` et `ruff check` sur les fichiers modifiés.
- [x] Exécuter `make build-de` puis `make build-it`, sans parallélisme.
- [x] Décompresser `0x00E9B4B8` dans EN/DE/IT et comparer tuiles 0–8, tuile 11
  et colonne 7 de la tuile 10.
- [x] Relire le diff, compléter `tasks/todo.md`, committer les chemins précis,
  rebaser via l’orchestrateur et revalider si la base a avancé.
