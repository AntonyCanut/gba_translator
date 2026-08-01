# Enseigne Boutique Pokémon « SHOP » — conception

## But

Remplacer l’enseigne extérieure « MART » des Boutiques Pokémon par « SHOP »
dans la ROM française, tout en livrant le graphisme sous forme de PNG indexé
éditable et réinjectable.

## Diagnostic

L’enseigne n’est pas une chaîne CFRU. Elle occupe les tuiles 413 et 414 du
tileset primaire extérieur Unbound compressé en LZ77 à `0x00CF91A0`. Le
descripteur vivant `0x002D4A94` pointe vers ce bloc, sa table de palettes
`0x00EA1B68`, ses métatiles `0x0029F6C8` et ses attributs `0x00EC5360`.

Le bloc se décompresse en 20 480 octets. Le métatile 65 référence les deux
tuiles avec la banque de palette 3 et aucun flip ; aucune autre entrée de la
table ne réemploie ces tuiles. La banque utile commence à `0x00EA1BC8`.

## Approches considérées

1. Modifier directement les flux LZ77. Cette option est fragile, illisible et
   ne fournit aucun asset éditable.
2. Redessiner « SHOP » par Python à chaque build. Cette option reproduit le
   précédent risque de glitch des graphismes procéduraux et ne répond pas à la
   demande d’extraction.
3. Étendre le pipeline sprite avec un index de première tuile, extraire les
   deux tuiles en PNG, puis les réinjecter dans leur bloc vivant. Cette option
   est retenue : elle est générique, réversible et ne touche pas les 638 autres
   tuiles du tileset.

## Architecture

`SpriteDef` reçoit `start_tiles`, apparié à `blocks`, avec zéro implicite pour
les sprites existants. Les fonctions `extract_block` et `insert_block`
acceptent un `start_tile` optionnel afin de sélectionner une fenêtre contiguë
à l’intérieur d’un bloc compressé ou brut. Les CLI transmettent la valeur du
registre sans changer leur interface publique.

Le registre FR expose `pokemon_mart_sign`, composé du bloc `0x00CF91A0`, de
l’indice 413 et d’une grille de 2 × 1 tuiles. L’asset
`languages/fr/sprites/pokemon_mart_sign.png` mesure 16 × 8 px, reste indexé
4 bpp et dessine « SHOP » avec la même palette en dégradé que « MART ».
`make build-fr` réinjecte le PNG après les réparations LZ77.

## Sécurité et validation

- Les ROM source de `input/roms/` restent en lecture seule.
- La réinjection conserve tous les octets décompressés hors des deux tuiles.
- Toute fenêtre hors bloc est rejetée avant écriture.
- Le bloc suivant commence immédiatement après le slot compressé de 11 604
  octets : la recompression doit donc tenir dans cette taille exacte.
- Les tests couvrent la sélection partielle, le round-trip, le registre,
  l’asset, le câblage du build et le bloc de la ROM construite.
