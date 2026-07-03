# Tests — organisation par langue

Les tests **spécifiques à une langue** (ils vérifient le contenu traduit d'une
langue donnée, ou le patch dédié d'une langue) sont regroupés dans un
sous-dossier `<code>/` au sein de leur tier (`unit/`, `e2e/`). Le code langue
suit le registre `languages/` (`fr`, `it`, `de`, `es`, `en`, `indie`).

Les tests **génériques** (codec, pointeurs, pipeline d'injection, intégrité
ROM, qualité — indépendants de la langue cible) restent à la racine de leur
tier. Les suites `benchmarks/` et `stress/` sont génériques par nature.

But : rendre visible d'un coup d'œil quelle langue est couverte et **quelle
langue manque de tests** (dossier absent ⇒ tests à écrire).

## Arborescence

```
tests/
  unit/                 # tests unitaires génériques (codec, rom_reader, padding…)
    fr/                 # unitaires spécifiques FR
    it/                 # unitaires spécifiques IT
    de/                 # unitaires spécifiques DE (patch_font_de)
  e2e/                  # e2e génériques (pipeline, intégrité, qualité, codec)
    fr/                 # e2e spécifiques FR (contenu du jeu traduit en français)
    it/                 # e2e spécifiques IT
    de/                 # e2e spécifiques DE (glyphes ä/ö/ü, build, statuts)
  e2e-playwright/       # specs Playwright (TS) — flux de jeu, non spécifiques langue
  benchmarks/           # perf (générique)
  stress/               # fuzzing / soak (générique)
  fixtures/             # savestates & données partagées
```

Les `conftest.py` restent au niveau de leur tier (`tests/conftest.py`,
`tests/e2e/conftest.py`) et couvrent automatiquement les sous-dossiers langue.

## Matrice de couverture (tests spécifiques langue)

| Langue | unit | e2e | Statut |
|--------|-----:|----:|--------|
| fr     |    3 |  17 | ✅ couverte |
| it     |    1 |   2 | 🟡 partielle |
| de     |    1 |   2 | 🟡 partielle |
| es     |    0 |   0 | ❌ aucun test dédié |

> `de` dispose désormais de tests dédiés (`patch_font_de` en unit ; build ROM,
> glyphes ä/ö/ü/Ä/Ö/Ü et abréviations de statut en e2e) mais reste en cours de
> traduction (`languages/de/combined_de.txt`, batches en cours) — la ROM
> `GenedRom-de.gba` n'étant pas encore construite localement, les tests
> dépendant de la ROM/du rapport de build sautent (skip) jusqu'au premier
> `make build-de`. `es` dispose d'un build (`languages/es`) mais d'aucun test
> dédié.

## Ajouter des tests pour une nouvelle langue

1. Créer `tests/unit/<code>/` et/ou `tests/e2e/<code>/` avec un `__init__.py`.
2. Nommer les fichiers de façon **générique** (`test_ability_names.py`, pas
   `test_ability_names_<code>.py`) — le dossier porte déjà l'info de langue.
3. Attention à la profondeur : un test dans `tests/e2e/<code>/` est un niveau
   plus bas que la racine du projet — utiliser `parents[3]` /
   `parent.parent.parent.parent` pour remonter à la racine du dépôt.
