# Extraction éditable des icônes de types — conception

## Objectif

Rendre les icônes de types de Pokémon accessibles sous forme de PNG indexés
éditables, notamment pour corriger leurs ombres, tout en conservant une
réinjection sûre dans une copie de ROM.

## Choix retenu

Le registre de sprites FR exposera deux entrées brutes utilisées par le jeu :
`type_icons_summary` à `0x00B1EC64` sur 16 × 19 tuiles et
`type_icons_battle` à `0x00961A00` sur 16 × 13 tuiles. Les PNG indexés feront
respectivement 128 × 152 et 128 × 104 pixels. Ces rectangles sont les plus
petits qui couvrent tous les badges, y compris Fée à son offset propre.

L’export se fera avec deux appels à `scripts/extract_sprite.py`, qui produiront
`type_icons_summary.png` et `type_icons_battle.png`. La réinjection restera
disponible via `scripts/insert_sprite.py` sur une ROM de travail, avec création
automatique d’une sauvegarde `.bak`.

## Alternatives écartées

- Un nouveau script spécialisé répéterait la conversion tuiles/PNG et la
  sécurisation déjà présentes dans la couche `src/graphics`.
- Un PNG par badge masquerait le fait que les cellules partagent des tuiles et
  que Fée n’a pas le même offset dans les deux copies. Une réinjection naïve
  pourrait donc altérer un badge voisin.

## Données et erreurs

Les blocs sont bruts et non compressés. Les PNG embarquent 16 indices de
palette ; seuls ces indices sont réinjectés. Le CLI existant refuse les images
aux mauvaises dimensions, les indices supérieurs à 15 et toute écriture dans
`input/roms/`.

## Validation

Des tests vérifieront les offsets, le format brut et les dimensions du registre,
la présence des deux PNG indexés, puis leur réinjection sur des ROM synthétiques.
La suite graphique
ciblée, la suite Python rapide et le lint couvriront les régressions.
