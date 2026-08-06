# Graphisme éditable de l’écran titre — conception

## But

Fournir un PNG indexé éditable de l’écran titre qui expose le dessin
« PRESS START », puis permettre sa réinjection sûre dans une copie de ROM.
L’asset versionné reste fidèle à la ROM source : le ticket livre le support
d’édition demandé, sans imposer un dessin français qui n’a pas encore été fourni.

## Diagnostic

« PRESS START » n’existe ni en encodage CFRU ni en ASCII dans les ROM EN/FR :
ce n’est pas une chaîne. Une sonde mGBA de l’écran titre l’a localisé sur BG1,
dans un écran 8 bpp complet :

- planche LZ77 : `0x01FD4854`, 29 376 octets décompressés ;
- tilemap LZ77 : `0x01FD6514`, 32 × 20 entrées ;
- palette BGR555 brute : `0x01FD699C`, 256 couleurs ;
- zone du libellé : rangée de tuiles 18, environ x=69..171.

La planche, la tilemap et la palette sont identiques dans `englishrom.gba`,
`patchedfrenchrom.gba` et la ROM FR actuellement construite. La phrase
« APPUYEZ SUR START » tient dans les 240 pixels visibles ; elle pourra donc être
dessinée dans l’asset, sous réserve de conserver les indices de palette et la
capacité LZ77.

## Approches considérées

1. Ajouter une traduction dans `combined_fr.txt`. Impossible : aucun texte
   encodé ni pointeur de chaîne ne porte le libellé.
2. Redessiner les lettres par un patch Python procédural. Cette voie masque le
   dessin aux graphistes et a déjà provoqué un glitch sur un autre libellé START.
3. Étendre le pipeline de sprites indexés au 8 bpp et exporter l’écran mappé.
   C’est l’option retenue : le PNG reste lisible, éditable et réversible.

## Architecture

`SpriteDef` reçoit `bits_per_pixel`, valant 4 par défaut et 8 pour
`title_screen`. Les opérations de `src.graphics.sprite_rom` utilisent ce champ
pour choisir une tuile GBA de 32 ou 64 octets et accepter des indices 0..15 ou
0..255. Les appels existants restent inchangés.

Le codec PNG choisit une profondeur indexée de 4 bits avec 16 couleurs ou de
8 bits avec 256 couleurs. BMP reste réservé au 4 bpp ; l’écran titre utilise
PNG. L’extracteur lit le nombre de couleurs correspondant dans la palette ROM,
et les deux CLI transmettent la profondeur au cœur graphique.

Le registre ajoute `title_screen` avec les trois offsets diagnostiqués. Le PNG
`languages/fr/sprites/title_screen.png` reconstruit les 256 × 160 pixels depuis
la planche et la tilemap. Aucune étape n’est ajoutée à `make build-fr` tant que
le dessin français n’est pas validé : une reconstruction ne doit pas réinjecter
automatiquement l’anglais.

## Mode d’emploi

Le fichier versionné peut être ouvert dans un éditeur qui préserve le mode
indexé et les indices de la palette. « APPUYEZ SUR START » peut remplacer le
prompt anglais dans la zone basse ; il faut conserver une largeur inférieure à
240 pixels et ne pas convertir l’image en couleurs RGB.

Pour repartir de la ROM source puis tester le dessin sur une copie :

```bash
python3 scripts/extract_sprite.py --rom input/roms/englishrom.gba \
  --lang fr --sprite title_screen \
  -o languages/fr/sprites/title_screen.png
cp input/roms/englishrom.gba output/title-screen-test.gba
python3 scripts/insert_sprite.py --rom output/title-screen-test.gba \
  --lang fr --sprite title_screen \
  --image languages/fr/sprites/title_screen.png
```

## Sécurité et erreurs

- Les ROM de `input/roms/` restent strictement en lecture seule.
- Seules les profondeurs 4 et 8 bpp sont acceptées.
- Une valeur de pixel hors plage est rejetée avant toute écriture.
- Les tuiles partagées contradictoires restent détectées avant réinjection.
- La recompression conserve la garde de capacité et les octets voisins.
- Une tentative d’exporter un sprite 8 bpp en BMP échoue explicitement.

## Validation

Le cycle TDD couvre le PNG 256 couleurs, le round-trip d’une planche mappée
8 bpp synthétique et la validation du registre. La preuve ROM extrait l’asset,
le réinjecte dans une copie temporaire, puis exige l’égalité des tuiles et de la
tilemap décompressées, de la palette et des octets hors des deux flux LZ77. Les
tests vérifient aussi les dimensions 256 × 160, la présence d’indices supérieurs
à 15 et la zone non vide du prompt.

## Suivi du 4 août 2026 — dessin français et clignotement

Le BMP 8 bpp fourni dans le commentaire de réouverture devient la référence du
dessin « PRESSEZ START ». Sa palette de 256 couleurs est strictement identique
à celle du PNG extrait et ses 197 pixels modifiés sont tous contenus dans la
zone du prompt (`x=80..160`, `y=149..153`). Il est converti mécaniquement vers
le PNG indexé déjà pris en charge, sans réordonner la palette ni modifier les
indices hors de cette zone.

`make build-fr` réinjecte désormais ce PNG après les autres assets manuels. Le
clignotement reste inchangé : le build ne touche ni au code de l’écran titre ni
à sa palette, et les pixels du nouveau libellé réutilisent les mêmes indices
animés 163/164 que le dessin anglais. La validation compare la grille extraite
de la ROM construite au PNG source et vérifie que les données de palette sont
restées identiques à la ROM anglaise.

Le BMP fourni ajoute deux pixels dans une cellule qui partage la tuile de fond
99 avec le reste de l’écran. Les 459 tuiles historiques sont toutes distinctes
et la tilemap recompressée avec une tuile supplémentaire dépasse son slot ROM.
La version intégrée ramène donc uniquement ces deux pixels de bord à l’index de
fond 31. Le dessin reste lisible, la planche et la tilemap gardent leur taille
historique, et les gardes de conflit du pipeline ne sont pas assouplies.

## Suivi du 6 août 2026 — restituer les deux pixels du dernier « T »

Le nouveau commentaire confirme que la suppression des pixels `(160,152)` et
`(160,153)` est visible et ne respecte pas le BMP de référence. Modifier la
tuile 99 en place est exclu : elle est utilisée par 94 cellules et ajouterait
les deux pixels aux 93 cellules de fond qui ne font pas partie du dernier « T ».
Conserver l’asset tronqué est également exclu puisque le dessin fourni est la
référence fonctionnelle demandée.

La planche `0x01FD4854` possède deux pointeurs vérifiés à `0x01ED7C7C` et
`0x01ED7EC0`; la tilemap `0x01FD6514` en possède deux à `0x01ED7C84` et
`0x01ED7EC8`. La cellule du dernier « T » reçoit une 460e tuile dédiée. Malgré
ses 64 octets décompressés supplémentaires, la planche se recompresse mieux
(7 319 octets contre 7 360) et tient dans son slot. La tilemap remappée, en
revanche, se recompresse sur 1 161 octets contre 1 160 disponibles et doit être
relocalisée via ses deux pointeurs connus. Aucun scan aveugle de pointeurs ni
écrasement de données adjacentes n’est nécessaire.

La validation suit les pointeurs après insertion, réextrait la grille depuis
la planche en place et la tilemap relocalisée, puis exige l’égalité pixel par
pixel avec le BMP, notamment les deux indices animés 164 restaurés. Elle
contrôle aussi que les deux pointeurs de planche restent inchangés, que les deux
pointeurs de tilemap ciblent le même nouveau flux, que la palette reste
inchangée et que l’écran conserve ses deux états de clignotement dans mGBA.
