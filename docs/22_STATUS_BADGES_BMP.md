# Badges de statut FR — suivi BMP de l’issue #143

## Objectif

Le BMP 4 bpp joint au nouveau commentaire GitHub devient la référence visuelle des
badges de statut FR. Ses 32 × 64 pixels doivent être reproduits dans les quatre
blocs LZ77 utilisés par le combat et les écrans Pokémon.

## Conception retenue

Le patch `languages/fr/patches/status_badges.py` charge un unique asset BMP indexé,
convertit sa grille en tuiles GBA, puis remplace la planche complète dans chaque
bloc. Avant le remplacement, il lit l’indice de bordure de chaque badge dans la
tuile de fermeture du bloc cible. Les pixels de bordure d’indice `9` du BMP sont
remappés vers cet indice cible (`9` ou `1`) ; les formes, fonds et lettres restent
sinon identiques au fichier fourni.

Cette approche conserve un seul dessin rééditable, applique aussi les pixels du
badge `PKRS` que l’ancien générateur ne modifiait pas et respecte les palettes
propres aux deux familles d’écrans.

## Validation

Un test de régression calcule, à partir des pixels réellement décompressés, une
empreinte indépendante de la planche fournie après normalisation de la bordure.
Il doit échouer avec l’ancien générateur, puis réussir pour chacun des quatre
blocs après application du patch. La ROM FR est ensuite reconstruite et soumise
aux tests ROM ainsi qu’aux suites Python et Vitest exigées par le dépôt.
