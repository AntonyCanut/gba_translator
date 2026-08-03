# Enseigne Boutique Pokémon « SHOP » — conception du suivi

## Contexte et cause racine

Le premier correctif remplace bien « MART » par « SHOP » dans les tuiles
413–414 du bloc LZ77 `0x00CF91A0`. La ROM construite contient exactement le
PNG versionné à cet emplacement.

Deux autres copies actives du graphisme restent toutefois inchangées dans la
ROM française : les tuiles 225–226 des blocs `0x007559B8` et `0x00B89D5C`.
Leurs 64 octets décompressés sont encore identiques à la source anglaise et
dessinent « MART ». Le correctif initial ne couvrait donc qu’une variante du
tileset extérieur.

Le commentaire de suivi fournit en outre un BMP indexé 4 bpp de 16 × 8 pixels,
`pokemon_mart_sign.bmp`, qui constitue la référence officielle du lettrage
« SHOP » à intégrer.

## Approches considérées

1. Remplacer seulement le PNG déjà injecté par le BMP fourni. Cette solution
   respecte le nouveau dessin, mais laisse les deux copies « MART » intactes.
2. Injecter le même BMP brut dans les trois blocs. Cette solution supprime
   « MART », mais écrase les indices de fond et le dégradé propres aux deux
   anciennes copies, ce qui crée des raccords de palette incorrects.
3. Étendre la définition existante aux trois blocs, injecter le BMP exact dans
   sa variante native et une adaptation pixel-identique du masque « SHOP »
   dans les deux copies au cadre différent. Cette solution est retenue : elle
   couvre la cause racine tout en préservant chaque graphisme environnant.

## Conception retenue

Le registre `pokemon_mart_sign` décrit les trois blocs dans l’ordre suivant :

- `0x007559B8`, tuile 225, capacité compressée 10 452 octets ;
- `0x00B89D5C`, tuile 225, capacité compressée 10 531 octets ;
- `0x00CF91A0`, tuile 413, capacité compressée 11 604 octets.

Le BMP fourni est versionné sans modification sous
`languages/fr/sprites/pokemon_mart_sign.bmp`. Le PNG existant est régénéré
avec la même grille d’indices pour rester une prévisualisation éditable. Un
second PNG, `pokemon_mart_sign_classic.png`, applique exactement le masque de
lettres du BMP aux indices de fond et de dégradé des deux copies classiques.

`make build-fr` appelle l’inserteur pour chaque index de bloc après les passes
de réparation LZ77 : le PNG classique pour les deux premiers blocs et le BMP
fourni pour le troisième. Aucun octet décompressé hors des six tuiles ciblées
n’est modifié.

## Validation

- Une garde fixe le SHA-256 et la grille complète du BMP fourni.
- Une garde vérifie la parité des pixels entre le BMP et le PNG éditable.
- Une garde interdit tout retour du masque « MART » dans les trois assets.
- Le registre et les trois commandes du build sont vérifiés explicitement.
- Après reconstruction, les trois fenêtres décompressées de la ROM sont
  comparées pixel par pixel à leur asset attendu.
- Les tests graphiques ciblés, la suite rapide multilingue, le lint et les
  contrôles de diff doivent rester verts.
