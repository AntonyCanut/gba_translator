# Dessins éditables des boîtes PC — conception

## But

Extraire dans un unique PNG indexé les dessins anglais « PKMN DATA »,
« PARTY POKÉMON » et « CLOSE BOX » afin qu’ils puissent être redessinés en
français, sans modifier la ROM source ni injecter prématurément l’image anglaise
dans le build FR.

## Diagnostic

Les trois libellés ne sont pas des chaînes CFRU. Ils appartiennent à la même
planche 4 bpp compressée LZ77, longue de 4 608 octets une fois décompressée :

- planche : `0x00E9C438` ;
- pointeur vivant vérifié : `0x0008F034` ;
- palette de prévisualisation : `0x003CE5DC` ;
- dimensions : 16 × 9 tuiles, soit 128 × 72 pixels.

La planche décompressée est identique octet pour octet au tileset de référence
de Pokémon FireRed. Son agencement linéaire place déjà les trois libellés de
façon lisible, donc aucune nouvelle logique de tilemap n’est nécessaire.

## Approches considérées

1. Extraire trois captures séparées depuis les tilemaps d’écran. Cela dupliquerait
   une même planche et compliquerait la réinjection des tuiles partagées.
2. Ajouter une composition spécifique des quatre tilemaps du PC. Cette logique
   serait propre à un seul écran et inutile pour le besoin d’édition.
3. Enregistrer la planche commune dans le registre de sprites existant. Cette
   solution est retenue : un seul PNG contient tous les dessins, et les outils
   génériques assurent déjà l’extraction et la réinjection sûre.

## Livraison et sécurité

Le registre FR expose `pc_box_labels` avec son bloc, son pointeur et sa palette.
L’asset `languages/fr/sprites/pc_box_labels.png` est extrait directement de
`input/roms/englishrom.gba`. Un test compare ses indices aux octets réellement
décompressés et vérifie un round-trip exact.

L’image n’est pas ajoutée à `make build-fr` tant qu’un dessin français n’a pas
été fourni. Une future réinjection pourra relocaliser le bloc au moyen du pointeur
connu si le flux recompressé dépasse son emplacement d’origine.

## Suivi du 4 août 2026 — dessin français contribué

Le nouveau commentaire fournit un BMP indexé 4 bpp de 128 × 72 pixels. Sa
palette de 16 couleurs est strictement identique à la palette ROM
`0x003CE5DC`, et ses indices traduisent les quatre zones visibles en
« DONNÉES », « ÉQUIPE PKMN », « ANNULER » et « FERMER BOÎTE ».

Trois intégrations ont été comparées : conserver le BMP comme second asset,
reproduire les retouches dans un patch procédural, ou convertir sans perte le
BMP vers le PNG canonique déjà exposé. La troisième est retenue. Elle évite
deux sources graphiques concurrentes, préserve exactement les 9 216 indices
fournis et réutilise la commande générique d’insertion déjà protégée par les
tests de relocalisation.

`build-fr` réinjecte donc `pc_box_labels.png` après les patchs graphiques
procéduraux. Un test rapide fixe l’empreinte de la grille contribuée et le
câblage de la recette ; un test ROM suit le pointeur vivant et compare la
planche décompressée aux pixels du PNG versionné.
