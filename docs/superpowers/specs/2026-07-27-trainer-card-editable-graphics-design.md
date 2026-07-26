# Graphismes éditables de la carte de Dresseur — conception

## But

Extraire les écrans recto et verso de la carte de Dresseur sous forme de PNG
indexés éditables, puis permettre leur réinjection sans modifier les sources ROM
de `input/roms/`.

Les deux titres concernés sont bien des pixels dans deux planches 4 bpp
compressées LZ77 :

- recto : planche `0x01FDA2BC`, tilemap `0x01FDA820` ;
- verso : planche `0x01FDAA4C`, tilemap `0x01FDB2AC`.

Les paires de pointeurs sont chargées par le code de la carte autour de
`0x01ED8AA4`. Les tilemaps font chacune 32 × 20 entrées et utilisent toutes les
tuiles de leur planche ; elles reconstruisent respectivement les écrans
« TRAINER CARD » et « LEAGUE BADGES ».

## Approches considérées

1. Exporter la planche brute en rangées de tuiles. C'est compatible avec
   l'outil actuel, mais le titre du recto est désordonné et difficile à éditer.
2. Exporter une simple capture d'écran. L'image est lisible, mais elle perd le
   lien réversible avec les tuiles ROM et ne peut pas être réinjectée sûrement.
3. Reconstruire l'écran depuis sa tilemap et inverser cette transformation à
   l'insertion. C'est l'option retenue : l'image est lisible et chaque pixel
   reste rattaché à la tuile 4 bpp correspondante.

## Architecture

`SpriteDef` reçoit un champ optionnel `tilemaps`, apparié à `blocks`. Sans
tilemap, le comportement existant reste inchangé. Avec une tilemap, les
dimensions du sprite décrivent l'écran reconstruit en tuiles.

`src.graphics.sprite_rom` ajoute deux opérations génériques :

- extraction : décompresser planche et tilemap, appliquer indice de tuile et
  flips horizontal/vertical, produire une grille de pixels ;
- insertion : lire chaque cellule de la grille, annuler les flips et reconstruire
  les tuiles sources.

Une même tuile peut apparaître dans plusieurs cellules. L'insertion accepte ces
répétitions uniquement si elles reconstruisent exactement les mêmes pixels ;
sinon elle échoue avant toute écriture avec un message explicite. Le reste de la
planche, la tilemap et les octets voisins sont préservés. La recompression garde
les contrôles de capacité déjà utilisés par `insert_block`.

Les scripts `extract_sprite.py` et `insert_sprite.py` sélectionnent
automatiquement le chemin mappé quand le registre fournit une tilemap. Deux
entrées `trainer_card_front` et `trainer_card_back` sont ajoutées au registre FR,
avec deux PNG indexés 4 bpp dans `languages/fr/sprites/`.

## Sécurité et erreurs

- Les ROM d'entrée restent en lecture seule ; une réinjection cible une copie ou
  une ROM de build.
- Nombre de blocs et nombre de tilemaps doivent être identiques.
- Une tilemap trop courte, une entrée hors planche ou une édition contradictoire
  d'une tuile partagée est rejetée.
- La réinjection conserve la tilemap et tous les octets décompressés hors tuiles
  effectivement représentées.
- Aucun appel n'est ajouté à `make build-fr` tant que les titres n'ont pas été
  redessinés en français : ce ticket livre l'extraction éditable demandée, pas
  une traduction graphique encore non fournie.

## Validation

Les tests unitaires suivent le cycle rouge/vert et couvrent :

- reconstruction d'un écran synthétique avec flips ;
- round-trip mappé exact ;
- détection d'une édition contradictoire d'une tuile partagée ;
- garde d'appariement blocs/tilemaps dans le registre.

La preuve sur ROM extrait les deux PNG, les relit, les réinjecte dans une copie
temporaire, puis compare les planches LZ77 décompressées avant/après. Les PNG
doivent être indexés 4 bpp, mesurer 256 × 160 et contenir les deux titres
lisibles.
