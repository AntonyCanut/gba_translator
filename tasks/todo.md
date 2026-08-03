# Issue #159 — « Envoyer qui ? » → « Déplacer où ? »

## Diagnostic et conception

- Le prompt de réorganisation des capacités vient de l’entrée active
  `0x3FE7A0`, dont la source anglaise est « Switch which? ».
- La traduction actuelle « Envoyer\nqui ? » décrit un changement de Pokémon et
  ne correspond pas à l’action de déplacer une capacité.
- « Déplacer\noù ? » conserve les codes de contrôle, le saut de ligne et la
  longueur encodée de la cellule ; aucun repoint ni patch dédié n’est requis.

## Plan validé

- [x] Ajouter une régression rouge sur la source active et la ROM construite.
- [x] Corriger chirurgicalement l’entrée `0x3FE7A0` et la protéger dans le manifeste.
- [x] Committer les sources avant d’exécuter la chaîne de build FR.
- [x] Reconstruire la ROM et décoder le prompt réellement livré.
- [x] Exécuter les validations pertinentes et relire le diff.
- [x] Préparer l’intégration locale, le commentaire et la clôture de l’issue #159.

## Revue

- L’entrée active `0x3FE7A0` affiche désormais « Déplacer\noù ? » en conservant
  exactement les huit octets de contrôle et la longueur de la cellule d’origine.
- La ROM construite contient
  `FC 05 05 FC 04 0D 0E 0F BE 1B E4 E0 D5 D7 D9 E6 FE E3 26 00 AC FF`,
  qui se décode en « Déplacer\noù ? », terminateur compris.
- Le manifeste d’intégrité protège la nouvelle valeur et interdit explicitement
  le retour à « Envoyer\nqui ? » ; les deux tests de régression source/ROM sont
  verts.
- Deux builds FR successifs sont byte-identiques. `make test-rom` termine avec
  562 tests réussis et 35 ignorés ; la garde des 328 entrées FR protégées est
  également verte.

# Issue #156 — extraire les icônes de types

- [x] Lire l’issue et cartographier les deux planches graphiques vivantes.
- [x] Choisir l’export réversible des planches complètes pour préserver les tuiles partagées.
- [x] Ajouter une garde rouge sur le registre et les assets attendus.
- [x] Déclarer les planches brutes dans le registre graphique FR.
- [x] Extraire les deux PNG indexés depuis la ROM FR construite.
- [x] Prouver le round-trip, exécuter les validations et relire le diff.
- [x] Préparer le commit, l’intégration locale et le bilan de clôture.

## Revue

- Deux sprites bruts distincts évitent d’écraser les tuiles hors périmètre :
  résumé `0x00B1EC64` sur 16 × 19 tuiles, combat `0x00961A00` sur 16 × 13.
- Les PNG versionnés font 128 × 152 et 128 × 104 pixels, restent indexés sur
  16 couleurs et exposent séparément les indices 15 (lettres) et 14 (ombres).
- Les deux assets ont été réinjectés via le CLI générique dans des ROM
  synthétiques ; les grilles relues correspondent pixel pour pixel et les
  sauvegardes `.bak` sont créées.
- Cycle TDD observé : absence du registre, puis absence des PNG. Vérifications :
  39 tests graphiques ciblés, 1 615 tests Python rapides réussis avec un skip
  préexistant, `uvx ruff check` et `git diff --check` sans diagnostic.

# Issue #153 — Majuscule à « Précision » en combat

## Diagnostic et conception

- Le message de variation de statistique compose le nom depuis la table pointée
  à `0x3FD5E8`; dans la ROM FR actuelle, ce pointeur cible `0x904E37` et décode
  « précision ».
- La source active est l’entrée unique `0x3FD5B8` de
  `languages/fr/combined_fr.txt`.
- La correction minimale conserve le mécanisme existant et remplace uniquement
  cette valeur par « Précision », de même longueur encodée.

## Plan validé

- [x] Ajouter une régression rouge sur la casse du nom de statistique.
- [x] Corriger chirurgicalement l’entrée active et la protéger dans le manifeste.
- [x] Exécuter la garde ciblée puis committer les sources avant le build.
- [x] Régénérer la traduction et reconstruire la ROM française.
- [x] Suivre le pointeur vivant et décoder « Précision » dans la ROM produite.
- [x] Exécuter les validations pertinentes, relire le diff et intégrer localement.
- [x] Commenter puis clôturer l’issue GitHub avec l’état `completed`.

## Revue

- L’entrée active `0x3FD5B8` contient désormais « Précision » et le manifeste
  d’intégrité interdit explicitement le retour à la casse minuscule.
- Après reconstruction, le pointeur vivant `0x3FD5E8` cible `0x904D33` et la
  séquence `CA E6 1B D7 DD E7 DD E3 E2 FF` se décode exactement en
  « Précision », terminateur compris.
- Deux builds FR successifs sont byte-identiques ; les tests ciblés, les gardes
  de reconstruction et `make test-rom` sont verts (557 réussis, 35 ignorés).
- La revue finale ne relève aucun écart critique, important ou mineur, et
  l’issue GitHub #153 est clôturée avec l’état `COMPLETED`.

# Issue #152 — enseigne Boutique Pokémon « SHOP »

- [x] Lire l’issue et confirmer que « MART » est un graphisme de tileset.
- [x] Localiser le bloc LZ77 vivant et les tuiles exactes de l’enseigne.
- [x] Formaliser l’extraction partielle et la réinjection sûre.
- [x] Ajouter les tests rouges sur la fenêtre de tuiles, l’asset et le build.
- [x] Étendre le pipeline sprite et extraire le PNG éditable.
- [x] Redessiner « MART » en « SHOP » et brancher le bloc vivant au build FR.
- [x] Reconstruire la ROM et comparer les tuiles décompressées à l’asset.
- [x] Exécuter les validations, relire, committer et clôturer l’issue.

## Revue

- L’enseigne vivante occupe les tuiles 413–414 du bloc LZ77 `0x00CF91A0`,
  référencé par le descripteur de tileset `0x002D4A94`; la palette utilisée est
  la banque à `0x00EA1BC8`.
- Le PNG indexé 4 bpp de 16×8 pixels conserve le cadre et la palette existants,
  mais son masque de lettres forme désormais explicitement « SHOP ».
- La réinjection ne remplace que les 64 octets des deux tuiles ciblées. Le bloc
  recompressé tient dans son emplacement d’origine (11 520 octets contre
  11 604) et les tuiles voisines restent inchangées.
- Le build release a inséré `pokemon_mart_sign`, puis construit avec succès les
  ROMs FR, IT et DE. Les tests unitaires, Vitest et les contrôles ROM du crochet
  de commit sont verts.
- La vérification ciblée après build retrouve exactement l’asset « SHOP » dans
  `output/roms/GenedRom-fr.gba` : 22 tests passent.

## Réouverture — intégrer les retouches fournies

- [x] Lire le nouveau commentaire et télécharger les deux BMP joints.
- [x] Vérifier dimensions, profondeur 4 bpp, indices et différences avec les PNG exportés.
- [x] Ajouter une garde rouge prouvant que `build-fr` consomme les deux assets.
- [x] Remplacer les PNG par une conversion indexée fidèle des BMP fournis.
- [x] Injecter les deux planches dans la recette FR après le patch procédural existant.
- [x] Reconstruire la ROM et comparer ses deux grilles aux assets versionnés.
- [x] Exécuter les validations, relire le diff et intégrer le correctif localement.

### Conception retenue

Les deux BMP du commentaire deviennent, après conversion sans perte d’indices,
les PNG canoniques déjà exposés par le registre. La recette `build-fr` les
réinjecte après `type_icons.py` : ce dernier conserve sa couverture unitaire et
son rôle de repli, tandis que les retouches manuelles approuvées gagnent en
dernier et atteignent effectivement la ROM livrée.

## Revue de la réouverture

- Les BMP 4 bpp fournis conservent les dimensions, la palette et les indices
  0–15 des assets : `128×152` pour le résumé et `128×104` pour le combat.
- La planche de résumé traduit aussi `POWER`, `ACCURACY` et `EFFECT` en
  `POUVOIR`, `PRECIS.` et `EFFET`; les deux planches corrigent les ombres.
- `build-fr` applique les PNG après le rendu procédural, puis les deux gardes
  ROM comparent chaque indice extrait aux fichiers versionnés.
- Vérifications : 42 tests graphiques ciblés, 1 616 tests Python rapides
  (1 ignoré), build FR déterministe et 554 tests ROM (40 ignorés). Le premier
  passage ROM a rencontré un scénario italien intermittent; son rerun ciblé
  puis la relance complète ont réussi sans changement de code.
- Relecture indépendante : aucun constat critique, important ou mineur; les
  644 octets modifiés de la ROM sont tous contenus dans les deux planches.

## Suivi — intégrer le BMP officiel et couvrir les copies restantes

- [x] Lire le nouveau commentaire et récupérer le BMP fourni.
- [x] Comparer sa grille au PNG versionné et reproduire les deux « MART » restants.
- [x] Identifier la cause racine : deux blocs actifs n’étaient pas enregistrés.
- [x] Ajouter les gardes rouges des trois copies et de la référence utilisateur.
- [x] Intégrer le BMP exact et la variante adaptée aux anciens cadres.
- [x] Brancher les trois insertions après les réparations LZ77.
- [x] Reconstruire la ROM et comparer les trois fenêtres décompressées.
- [x] Exécuter les validations graphiques et multilingues.
- [x] Relire, committer et intégrer localement sans push.

### Revue du suivi

- La cause du faux positif initial était une couverture incomplète :
  `0x00CF91A0` affichait bien SHOP, mais `0x007559B8` et `0x00B89D5C`
  conservaient encore les 64 octets de MART aux tuiles 225–226.
- Le BMP fourni est versionné octet pour octet
  (`SHA-256 93407be53e035fbeb…`) et sa grille indexée est aussi conservée dans
  le PNG éditable. La variante des deux anciens tilesets reprend le même
  masque SHOP avec leur cadre et leur dégradé natifs.
- La sonde d’insertion a recompressé les trois blocs à 10 333, 10 410 et
  11 522 octets, sous leurs capacités respectives, sans modifier aucune
  tuile voisine.
- La ROM FR reconstruite contient les trois grilles attendues. Le crochet a
  validé 1 633 tests Python (1 ignoré), 68 tests Vitest et les builds FR, IT
  et DE avec zéro collision ; 45 gardes graphiques ciblées et le lint sont
  également verts.

# Issue #149 — réouverture : corriger le vrai libellé de montée de niveau

## Diagnostic et conception

- Le correctif initial visait `0x3FE7C7`, référencé par `0x3FE7F4`.
- La table réellement lue par la fenêtre de montée de niveau commence à
  `0x459B48`; son premier pointeur cible `0x41B2A9`.
- `0x41B2A9` contient encore
  `{FONT_SMALL}MAX.{FONT_NORMAL} PV` dans la source et dans la ROM distante.
- La correction minimale consiste à modifier la dernière entrée active de
  `0x41B2A9`, à la protéger, puis à vérifier le pointeur vivant dans la ROM
  reconstruite. Le correctif initial reste intact pour son autre consommateur.

## Plan de reprise

- [x] Lire le commentaire de réouverture et reproduire l’ancien libellé.
- [x] Tracer le pointeur réellement consommé par l’écran de montée de niveau.
- [x] Ajouter une régression rouge sur `0x459B48` et protéger `0x41B2A9`.
- [x] Corriger chirurgicalement la dernière entrée active de `0x41B2A9`.
- [x] Reconstruire la ROM FR avec la chaîne release canonique.
- [x] Vérifier les octets, le rendu mGBA et les tests ciblés puis complets.
- [x] Relire le diff et préparer l’intégration locale du correctif.

## Revue de la réouverture

- La première résolution avait corrigé une table secondaire
  (`0x3FE7F4 → 0x3FE7C7`), pas celle lue par la fenêtre de montée de niveau.
- Les deux sites du code de montée de niveau (`0x11E930` et `0x11EA40`)
  chargent la table `0x459B48`, dont le premier pointeur cible `0x41B2A9`.
- La chaîne release actuelle (`make prepare-fr && make build-fr`) produit
  `CA D0 00 FC 06 00 C7 D5 EC AD FF`, soit « PV Max. » avec « Max. » en
  petite police, au pointeur vivant.
- Une sonde mGBA déterministe avec la sauvegarde Rattata a atteint le niveau 16
  et affiché visuellement « PV Max. » dans le panneau des statistiques.
- Le garde source, les tests ROM ciblés et la chaîne de build FR sont verts.

# Issue #149 — « Max. PV » → « PV Max. »

- [x] Lire l’issue, ses commentaires et identifier la chaîne active.
- [x] Ajouter une garde rouge sur la valeur attendue.
- [x] Corriger uniquement la dernière valeur active à l’offset `0x3FE7C7`.
- [x] Reconstruire la ROM FR et décoder la chaîne réellement utilisée.
- [x] Exécuter les validations, relire le diff, committer et clôturer l’issue.

## Revue

- L’entrée active `0x3FE7C7` porte désormais les codes CFRU explicites pour
  afficher « PV » en police normale puis « Max. » en petite police.
- Le pointeur vivant `0x3FE7F4` cible `0x3FE7C7`; les 11 octets lus sont
  `CA D0 00 FC 06 00 C7 D5 EC AD FF`, terminateur compris.
- Le contrôle initial de police normale, redondant, a été retiré : la chaîne
  tient dans sa cellule et la cellule « Attaque » voisine reste intacte.
- Le convertisseur CSV réserve désormais l’octet de terminaison dans son budget,
  ce qui évite les fusions de cellules à longueur limite lors d’un build release.
- La chaîne release complète et ses régressions ROM sont vertes.

# Issue #148 — graphismes de la carte de Dresseur

- [x] Lire l’issue, son commentaire et identifier les ressources graphiques vivantes.
- [x] Formaliser une extraction tilemap → PNG réversible et sûre.
- [x] Ajouter les tests rouges de composition, round-trip et conflit de tuile partagée.
- [x] Étendre le registre et les CLI d’extraction/réinjection.
- [x] Extraire les PNG éditables du recto et du verso.
- [x] Prouver le round-trip sur une copie de ROM et exécuter les validations.
- [x] Relire, committer, intégrer localement et clôturer l’issue.

## Suivi — intégrer le verso fourni

- [x] Récupérer `trainer_card_back.bmp` dans le commentaire de réouverture.
- [x] Reproduire et localiser le conflit des tuiles partagées.
- [x] Ajouter les gardes rouges pour la traduction et la réinjection remappée.
- [x] Intégrer uniquement le dessin « BADGES DE LIGUE » dans l’asset versionné.
- [x] Brancher le verso sur `make build-fr`.
- [x] Reconstruire la ROM FR et comparer l’écran mappé aux pixels attendus.
- [x] Exécuter les validations, relire, committer et intégrer sans push.

## Revue

- Le code de la carte charge deux paires planche/tilemap :
  `0x01FDA2BC`/`0x01FDA820` au recto et
  `0x01FDAA4C`/`0x01FDB2AC` au verso.
- `extract_sprite.py` reconstruit maintenant les écrans mappés en PNG indexés
  4 bpp de 256 × 160 ; `insert_sprite.py` annule les flips de tilemap et refuse
  une édition incohérente de deux occurrences d’une même tuile.
- Les assets `trainer_card_front.png` et `trainer_card_back.png` montrent
  lisiblement « TRAINER CARD » et « LEAGUE BADGES » et ne sont volontairement
  pas encore branchés dans `build-fr`, puisqu’ils restent à redessiner.
- Le round-trip sur une copie de `englishrom.gba` restitue exactement les
  4 416 et 6 688 octets des deux planches décompressées ; les deux tilemaps
  restent inchangées.
- Vérifications : 34 tests sprites ciblés, puis 1 557 tests Python rapides
  réussis (1 scénario optionnel préexistant ignoré), compilation Python,
  lint ciblé et `git diff --check`.
- Le BMP joint au commentaire a été récupéré et contrôlé comme image indexée
  4 bpp de 256 × 160 ; seule sa zone « BADGES DE LIGUE » a été importée afin
  de préserver les pixels décoratifs que la contribution modifiait aussi.
- La réinjection déduplique désormais les tuiles équivalentes par flips et
  remappe deux cellules de la tilemap ; la planche conserve ses 6 688 octets.
  Le rendu extrait de la ROM construite correspond pixel pour pixel au PNG.
- Le hook a validé 1 563 tests Python (1 ignoré), 68 tests Vitest et les builds
  FR/IT/DE sans collision. `make test-rom` a confirmé le rebuild déterministe,
  12 gardes de reconstruction et 533 tests ROM ; 35 scénarios optionnels ont
  été ignorés.

## Reprise — respecter les pixels décoratifs fournis

- [x] Relire le nouveau commentaire et confirmer le périmètre graphique complet.
- [x] Comparer le BMP d’origine à l’asset injecté et localiser les pixels omis.
- [x] Ajouter une garde rouge sur la fidélité de l’intégralité du rendu.
- [x] Versionner le BMP original et régénérer le PNG depuis sa grille 4 bpp.
- [x] Committer les sources avant de reconstruire la ROM FR.
- [x] Réextraire le verso depuis la ROM et comparer tous les pixels au BMP.
- [x] Exécuter les validations élargies, rebaser et publier le bilan GitHub.

### Revue

- Le PNG précédent différait du BMP sur 122 pixels, tous situés dans l’ornement
  à droite du titre (`x=105..121`, `y=4..16`) qui avait été conservé à tort.
- La référence attendue est désormais le BMP complet fourni dans l’issue, texte
  et ornements compris ; son SHA-256 est
  `fdce7fafb925b87c339f58e26d6ca3e713669bf1197d62a1b4930e10842a8eb4`.
- Le rendu requiert 211 tuiles canoniques contre 209 auparavant : la planche
  passe à 6 752 octets décompressés et reste dans son emplacement compressé
  (2 107 octets). La tilemap, devenue trop grande pour sa cellule adjacente,
  est relocalisée via son unique pointeur déclaré `0x01ED8AB8`, sans balayage
  aveugle de la ROM.
- Dans la ROM reconstruite, ce pointeur cible `0x002FE490` et la grille extraite
  a le SHA-256 `a429790465cf2bd715136a955d85f7ee52b251c99d5310ee78c95a33c2403435` :
  elle est pixel pour pixel identique au BMP complet.
- Le hook du commit source a validé 1 615 tests Python (1 ignoré), 68 tests
  Vitest, les builds FR/IT/DE et les trois audits de collisions à zéro.
  `make test-rom` a ensuite confirmé le rebuild FR déterministe, 12 gardes de
  reconstruction et 547 tests ROM ; 43 scénarios optionnels ont été ignorés.

## Reprise — intégrer le recto fourni

- [x] Versionner le nouveau `trainer_card_front.bmp` comme référence complète.
- [x] Ajouter les gardes rouges sur sa grille, la recette FR et la relocalisation.
- [x] Relocaliser atomiquement la planche via le pointeur vérifié `0x01ED8AA4`.
- [x] Régénérer le PNG depuis la grille 4 bpp exacte et l’insérer dans `build-fr`.
- [x] Reconstruire la ROM FR et comparer le rendu vivant pixel par pixel au BMP.
- [x] Exécuter les validations élargies, relire, committer et intégrer sans push.
- [x] Publier le bilan sur l’issue #148 et la conserver clôturée en `completed`.

### Conception retenue

- Le BMP complet est la source de vérité ; aucun recadrage ni redessin procédural.
- La planche recompressée mesure 1 402 octets contre un slot vivant de 1 378 :
  tenter de modifier le compresseur ou de raccourcir le dessin serait fragile.
- La réinjection étend donc le mécanisme générique de relocalisation sûre déjà
  utilisé par les tilemaps, avec écriture atomique et uniquement le pointeur
  moteur exact `0x01ED8AA4`. La tilemap reste gérée indépendamment par son
  pointeur connu `0x01ED8AA8` si sa recompression devait aussi déborder.
- La preuve finale suit les pointeurs vivants de la ROM reconstruite puis compare
  la grille 256 × 160 complète au BMP, pas seulement le libellé français.

### Revue

- Le BMP fourni est versionné sans altération (SHA-256
  `64afede2c86875bbba38fbb0dce0c632b3ee1d8a668a8458e17984603173f47c`) ;
  sa grille diffère de l’ancien recto sur 868 pixels.
- La planche vivante contient 141 tuiles, soit 4 512 octets décompressés et
  1 402 octets compressés. Elle est relocalisée à `0x002FE490` par le seul
  pointeur validé `0x01ED8AA4` ; la tilemap reste à `0x01FDA820` et occupe
  521 octets compressés.
- L’extraction suit ces deux pointeurs et retrouve exactement le BMP complet ;
  l’empreinte de la grille est
  `3b019d70cf28bfbb51a2d83e862e1272cade731e4889be604f06f0ebea9cd8d1`.
  La tilemap relocalisée du verso reste indépendante à `0x002BC87C`.
- Le hook de commit a validé 1 643 tests Python (1 scénario ignoré), 68 tests
  Vitest, les builds FR/IT/DE et trois audits de collisions à zéro.
  `make test-rom` a confirmé le rebuild FR byte-identique, 12 gardes de
  reconstruction, 559 tests ROM réussis et 39 scénarios optionnels ignorés.

# Issue #150 — description CT108

- [x] Lire l’issue, sa capture et décoder le pointeur vivant de la CT108.
- [x] Identifier la cause racine dans le garde des descriptions CT/CS.
- [x] Ajouter un test rouge pour un fragment court mais terminé.
- [x] Corriger génériquement la comparaison au texte FR canonique.
- [x] Reconstruire la ROM et décoder la description vivante de CT108.
- [x] Exécuter les validations, relire, committer et clôturer l’issue.

## Revue

- Le garde prenait tout terminateur proche pour preuve d’une chaîne saine :
  CT108 conservait donc un fragment court terminé provenant de sa voisine.
- Les descriptions CT/CS de la zone fusionnée ne restent désormais en place
  que si leurs octets égalent exactement la source FR canonique ; tout fragment
  ou débordement est relocalisé sans traitement spécial pour CT108.
- La revue indépendante a aussi protégé l’objet cadeau CT112 : son pointeur
  spécial reste sous le garde de structure existant, et une seconde application
  du patch ne relocalise rien et laisse la ROM strictement byte-identique.
- La ROM reconstruite pointe CT108 vers `0x1FF385A` et décode exactement
  « Aboie menaçant.\nBaisse aussi\nl’Att. Spé\nennemie. », suivi de `0xFF`.
- Vérifications : 6 gardes ciblées réussies ; hook de commit avec 1 551 tests
  Python réussis (1 ignoré), 68 tests Vitest et builds FR/IT/DE réussis ;
  suite ROM avec 531 réussites et 36 scénarios ignorés. L’unique échec initial,
  la sonde mGBA du premier combat italien, a réussi seule au second passage et
  ne touche ni le patch ni la ROM FR.

# Issue #146 — accords masculins du Chenal Aubrun

- [x] Lire l’issue, ses commentaires et recenser les occurrences actives.
- [x] Ajouter une garde systématique et protéger les quatre dialogues concernés.
- [x] Corriger uniquement les dernières valeurs actives dans la source FR.
- [x] Régénérer la traduction, reconstruire la ROM et décoder les textes vivants.
- [x] Exécuter les validations, relire le diff, committer et clôturer l’issue.

## Revue

- Les 18 offsets actifs mentionnant le Chenal Aubrun ont été audités : 14
  étaient déjà neutres ou masculins et les 4 accords féminins ont été corrigés.
- La garde source balaie toutes les valeurs actives selon la règle
  « dernière occurrence gagnante » ; les 4 dialogues sont aussi protégés
  individuellement dans le manifeste FR.
- La ROM reconstruite décode les quatre formes attendues : « le Chenal
  Aubrun », « au Chenal Aubrun » (deux occurrences) et « du Chenal Aubrun ».
- Vérifications du hook : 1 525 tests Python réussis (1 ignoré préexistant),
  68 tests Vitest réussis, puis builds FR/IT/DE et audits de collisions réussis.

# B-543 — Reprise du bandeau « (START) Tri »

- [x] Relire le dernier commentaire de l’issue et récupérer le BMP de référence fourni.
- [x] Comparer sa grille indexée au sprite actuellement injecté.
- [x] Remplacer le BMP, régénérer le PNG éditable à indices identiques et adapter les gardes.
- [x] Committer les sources avant reconstruction de la ROM.
- [x] Reconstruire la ROM FR et réextraire le bloc LZ77 vivant.
- [x] Exécuter les validations ciblées et rapides, rebaser puis revalider.
- [x] Publier le bilan sur l’issue GitHub et clôturer le suivi.

## Revue

- Le BMP est octet pour octet celui joint au dernier commentaire de l’issue ;
  il redessine ensemble le contour complet de START et le libellé « Tri ».
- Le PNG indexé 4 bits a été régénéré depuis cette grille et lui correspond
  intégralement.
- La réextraction de `GenedRom-fr.gba` à `0x00EF1B68` reproduit les 104×32
  pixels du BMP source.
- Vérifications avant rebase : 5 tests ciblés, 1 524 tests Python réussis
  (1 ignoré), 68 tests Vitest et builds FR/IT/DE réussis.

## Reprise — ombre corrigée du bouton START

- [x] Récupérer le dernier BMP joint à l’issue et comparer sa grille à l’asset versionné.
- [x] Mettre à jour les gardes de référence et observer leur échec sur l’ancien BMP.
- [x] Remplacer le BMP à l’identique et régénérer le PNG indexé 4 bits.
- [x] Valider les pixels de l’asset et la parité PNG/BMP.
- [x] Reconstruire la ROM FR et réextraire le bloc LZ77 vivant.
- [x] Exécuter les validations finales et documenter le résultat.

### Revue

- Le BMP versionné est octet pour octet le dernier fichier joint à l’issue
  (`SHA-256 3055f7b76ba0c890…`) ; sa grille diffère de la référence précédente
  sur 80 pixels, dont l’ombre complète du bouton START.
- Le PNG éditable est un fichier indexé 4 bits dont les 104×32 indices
  correspondent exactement au BMP.
- Le bloc LZ77 réextrait de la ROM FR reconstruite à `0x00EF1B68` correspond
  pixel par pixel à la nouvelle grille.
- Vérifications : cycles RED observés sur les gardes de référence, 8 tests
  Cube réussis, 1 527 tests Python réussis (1 ignoré), 68 tests Vitest et
  builds FR/IT/DE réussis.

## Reprise — version définitive centrée

- [x] Relire tous les commentaires et identifier le dernier BMP non intégré.
- [x] Télécharger la référence centrée et comparer ses pixels à l’asset versionné.
- [x] Mettre à jour les gardes puis confirmer leur échec sur l’ancien BMP.
- [x] Remplacer le BMP et régénérer le PNG indexé éditable.
- [x] Reconstruire la ROM FR et comparer le bloc LZ77 vivant à la référence.
- [x] Exécuter les validations élargies et relire les changements.
- [x] Publier le bilan GitHub et conserver l’issue clôturée en `completed`.

### Revue

- Le BMP versionné correspond octet pour octet au dernier fichier joint,
  centré dans sa case (`SHA-256 7697b037c547ec79…`) ; 213 pixels diffèrent
  de la version précédente.
- Le PNG compagnon est régénéré en indexé 4 bits et sa grille 104×32 est
  strictement identique au BMP.
- Le bloc LZ77 vivant `0x00EF1B68` de la ROM FR reconstruite se décompresse
  en la grille attendue (`SHA-256 75a8d2c51c692763…`).
- Cycle RED : 4 échecs attendus sur l’ancien asset ; cycle GREEN : 8 gardes
  Cube réussies, y compris la décompression de la ROM.
- Hook du commit source : 1 566 tests Python réussis (1 ignoré), 68 tests
  Vitest réussis et builds FR/IT/DE réussis. `make test-rom` : 533 tests
  réussis et 36 scénarios optionnels ignorés.

# Sonde mGBA — premier combat italien

- [x] Reproduire l’échec sur la carte 4.10 et figer la cause racine.
- [x] Ajouter un garde rouge sur la fixture et la route déterministe.
- [x] Remplacer l’exploration cyclique par un trajet reproductible.
- [x] Versionner une savestate courte à l’entrée du premier combat.
- [x] Rejouer le combat jusqu’à la victoire avec détection texte/hash écran.
- [x] Exécuter les validations ciblées et rapides, relire puis committer.

## Revue

- La marche cyclique ne rejoignait pas le déclencheur derrière le labyrinthe
  de la map 4.10. La fixture versionnée démarre désormais au garde avec un
  starter valide ; sa route déclarative de 60 pressions A est bornée et vérifie
  d’abord la map `(4,10)` et la position `(21,22)`.
- La sonde garde les deux oracles fiables : texte CFRU décodé pour reconnaître
  le combat et la victoire, hash MD5 des captures pour les freezes. Les textes
  propres à ce combat (« Mi arrendo », « Gible! Torna! ») empêchent de prendre
  l’overworld post-victoire pour un freeze.
- Vérifications : garde TDD 2/2, E2E IT 2/2 en 10,88 s, typecheck ciblé,
  1 518 tests Python réussis (1 skip préexistant) et 68 tests Vitest réussis.

# B-552 — Fix mail move-to-bag label mapping

- [x] Trace the rebuilt ROM mismatch to the dedicated patch preimage guard.
- [x] Add a regression for the generic « Dépl au sac » build output.
- [x] Normalize supported source/build preimages to « Vers le sac ».
- [x] Run focused tests, the fast suite, and decoded-ROM verification.
- [x] Review the diff and commit the focused generation-path fix.

## Review

- Root cause: the generic build could leave the older 11-byte « Dépl au sac »
  preimage, while `pc_move_labels.py` accepted only the English bytes and
  skipped the canonical in-place rewrite.
- The dedicated patch now accepts only the two known upstream preimages
  (English and the legacy French abbreviation) and normalizes both to
  « Vers le sac »; its existing unknown-byte safety guard and idempotence stay
  intact.
- Verification: 15 focused patch tests passed; the guarded commit passed
  1,511 Python tests (1 skipped), 68 Vitest tests, and full FR/IT/DE builds.
  The rebuilt FR ROM test passed and bytes at `0x4177DD` decoded exactly to
  « Vers le sac ».
- The rebuilt ROM artifact was restored after verification because the parent
  ticket still tracks four unrelated rebuild regressions; this slice does not
  ship those changes.

# Issue #143 — icônes de statut FR

- [x] Lire l’issue et confirmer l’absence de commentaires.
- [x] Identifier les quatre blocs LZ77 utilisés en combat et dans l’équipe.
- [x] Ajouter l’extraction/réinjection en PNG indexé sans perdre les indices palette.
- [x] Fournir l’asset PNG rééditable des badges FR.
- [x] Tester le round-trip PNG et tous les badges dans les quatre blocs ROM.
- [x] Reconstruire la ROM FR et vérifier les pixels décodés.
- [x] Relire le diff, committer et clôturer l’issue GitHub.

## Suivi du 28 juillet — BMP fourni par l’utilisateur

- [x] Lire le nouveau commentaire et récupérer le BMP 4 bpp joint.
- [x] Comparer ses pixels à l’asset et aux quatre blocs actuels.
- [x] Choisir un asset canonique unique avec adaptation de bordure par bloc.
- [x] Ajouter un test rouge sur l’empreinte visuelle fournie.
- [x] Remplacer la génération de glyphes par l’injection fidèle du BMP.
- [x] Reconstruire et valider les quatre blocs combat/menu.
- [x] Relire, committer, commenter et refermer l’issue.

## Revue

- La couture de bordure venait d’un indice palette `9` forcé dans les tuiles
  centrales, alors que deux copies utilisent l’indice `1`. Le patch lit
  désormais l’indice de la tuile de fermeture propre à chaque bloc.
- `extract_sprite.py --all-blocks` produit quatre PNG indexés numérotés ;
  `insert_sprite.py --all-blocks` les réinjecte séparément pour conserver les
  palettes de combat et du menu.
- Le registre autorise le LZ77 compact uniquement pour ces badges : le flux
  VRAM-safe dépassait de trois octets et rendait la réinjection impossible.
- Vérifications : build FR complet réussi, 25 tests ciblés, round-trip PNG
  réel 4/4 blocs, puis 1 508 tests Python rapides réussis (1 ignoré).
- Suivi BMP : le fichier fourni est injecté pixel pour pixel, y compris le
  badge `PKRS`; les quatre blocs ont l’empreinte normalisée
  `9ab29c8b025c697e…76ae8d41` malgré leurs bordures palette `9`/`1`.
- Validation du suivi : 30 tests ciblés réussis, `make test-rom` avec 500 tests
  réussis, hook avec 1 508 tests Python et 68 tests Vitest, builds FR/IT/DE.

# Issue #142 — « Annul » → « Annul. » dans la liste Pokédex

- [x] Ajouter un test rouge sur la valeur active de l’entrée `0x415F51`.
- [x] Corriger chirurgicalement la source FR et protéger la valeur attendue.
- [x] Regénérer la chaîne FR et reconstruire la ROM jouable.
- [x] Vérifier les octets décodés depuis le pointeur vivant du Pokédex.
- [x] Exécuter les tests ciblés, ROM et rapides.
- [x] Relire le diff et committer le correctif.

## Revue

- La valeur active `0x415F51` est désormais
  `{DPAD_UPDOWN}Choix {SE_SHOP}OK {B_BUTTON}Annul.` et est protégée par le
  manifeste FR.
- Les trois pointeurs vivants `0x103234`, `0x103514` et `0x1423A8` ciblent la
  même chaîne CFRU terminée, décodée en `Choix / OK / Annul.`.
- Le build FR est byte-identique sur deux reconstructions consécutives.
- Vérifications : 4 tests ciblés, 1 498 tests Python rapides, 68 tests Vitest,
  puis 497 tests ROM/E2E réussis (37 scénarios optionnels ignorés).

# Pipeline de release — reprise d’upload d’artefact

- [x] Lire les journaux du run #81 et isoler la cause racine.
- [x] Vérifier l’historique autour de `e064865d`.
- [x] Écrire un test de régression pour l’échec transitoire d’upload.
- [x] Ajouter une seconde tentative sûre dans `release.yml`.
- [x] Brancher le garde ciblé dans le hook pré-commit.
- [x] Exécuter les validations, relire le diff et committer.
- [x] Relancer la pipeline et confirmer son résultat.

## Revue

- Le build et la vérification FR du run #81 étaient réussis ; seul
  `FinalizeArtifact` a reçu un `403 Forbidden`, après l’envoi complet des octets.
- `e064865d` ne modifie pas la CI. La dépendance à l’artefact sans reprise vient
  de la parallélisation introduite par `94acdd8a`.
- Le premier upload est toléré uniquement pour déclencher une seconde tentative
  non tolérée, avec `overwrite: true` pour nettoyer un éventuel artefact partiel.
- Le test ciblé, la syntaxe YAML/shell, `actionlint`, `git diff --check` et les
  1 501 tests Python rapides passent (`1 500 passed`, `1 skipped`).
- La tentative 2 du run #81 est verte : builds FR/IT/DE, trois artefacts et
  publication de la release réussis.

# Carte mondiale — libellé court « Annul. » après rebuild

- [x] Comparer les pointeurs vivants de la ROM commitée et du rebuild régressé.
- [x] Ajouter un test rouge reproduisant le repoint vers « Annuler ».
- [x] Restaurer les deux cellules courtes et les trois vrais pointeurs carte.
- [x] Reconstruire la ROM FR et vérifier les octets pointés.
- [x] Exécuter les tests ciblés et la validation rapide pertinente.
- [x] Relire le diff, committer et documenter les résultats.

## Revue

- Le rebuild régressé envoyait `0xC06FC`, `0xC1B28` et `0xC50C0` vers une
  relocalisation de la chaîne générique « Annuler ». Le patch post-build
  restaure désormais les cibles carte `0x418E95`, `0x418E9E`, `0x418E95`.
- Les deux cellules reçoivent `{SE_SHOP}Annul.` sur exactement 9 octets,
  terminateur compris, soit la largeur de `{SE_SHOP}Cancel`.
- La chaîne générique « Annuler » et les pointeurs du menu Équipe restent
  inchangés ; une seconde application du patch est sans effet.
- Vérifications : 1 512 tests Python rapides et 68 tests Vitest réussis,
  builds FR/IT/DE réussis, puis 3 assertions ROM ciblées réussies.

# P-548 — Validation intégrée des cinq régressions `build-fr`

- [x] Régénérer les traductions FR depuis la source canonique.
- [x] Reconstruire deux fois la ROM et confirmer son déterminisme.
- [x] Exécuter ensemble les cinq régressions du ticket parent.
- [x] Vérifier les octets/pointeurs vivants des quatre zones fonctionnelles.
- [x] Exécuter la validation ROM complète et les gardes rapides pertinentes.
- [x] Intégrer la ROM reconstruite, relire le diff et revalider après rebase.

## Revue

- `build-fr` exécute désormais `test-fr-build-regressions`, qui regroupe les
  cinq sélecteurs exacts de P-548 et bloque le build si l'un d'eux revient.
- Le rebuild produit le même SHA-256 `5aa088192ec9ab30…` que la ROM déjà
  versionnée ; deux reconstructions consécutives sont byte-identiques.
- Le hook a validé 1 517 tests Python (1 ignoré), 68 tests Vitest et les builds
  FR/IT/DE sans collision. La suite ROM statique a validé 497 tests
  supplémentaires (34 scénarios optionnels ignorés).
- `make test-rom` a confirmé 505 tests et toutes les gardes FR, mais a aussi
  exposé une sonde mGBA italienne indépendante qui ne trouve pas le premier
  combat sur la map 4.10 malgré l'absence de freeze et de texte anglais ; son
  traitement est isolé dans le ticket T-554.
- Rebase final sur `unbound` sans avancement concurrent ; arbre relu propre.

# Issue #144 — Couleurs du choix de sortie du menu Options

- [x] Ajouter un test rouge exigeant vert, rouge puis noir sur les trois choix.
- [x] Corriger chirurgicalement l'entrée FR active `0x1F4E230`.
- [x] Protéger la valeur contre les réécritures de `combined_fr.txt`.
- [x] Régénérer la chaîne FR et vérifier les octets du pointeur vivant.
- [x] Exécuter les validations ROM et rapides pertinentes.
- [x] Relire le diff, committer et documenter les résultats.

## Revue

- L'entrée active `0x1F4E230` préfixe désormais « Sauver » par
  `FC 01 06` (vert), « Ignorer » par `FC 01 04` (rouge) et « Annuler » par
  `FC 01 02` (noir), ce qui empêche aussi la dernière couleur de déborder.
- Le manifeste protégé rejette explicitement l'ancienne version sans couleur.
  Le test de régression lit le pointeur vivant `0x1EBD77C` et exige les octets
  exacts des trois choix dans la ROM construite.
- `make prepare-fr && make build-fr` a produit 21 595 traductions et une ROM
  byte-identique sur deux reconstructions consécutives.
- Le hook a validé 1 524 tests Python (1 ignoré), 68 tests Vitest et les builds
  FR/IT/DE. La suite ROM a validé 507 tests et 39 scénarios optionnels ont été
  ignorés ; l'unique sonde mGBA IT perturbée par un autre `pytest` a ensuite
  réussi isolément en 7,14 s.

# B-557 — Caps de la barre de vie du résumé DE/IT

- [x] Lire la spec FR #84 et confirmer la cause racine commune.
- [x] Formaliser le port minimal et la stratégie de preuve ROM.
- [x] Ajouter les gardes rouges DE/IT sur le corps et les deux caps.
- [x] Restaurer la planche anglaise puis repeindre « KP » / « PS » sur 4 rangées.
- [x] Reconstruire les ROMs DE/IT et comparer le bloc LZ77 décodé à l’anglais.
- [x] Exécuter les validations, relire, committer et intégrer sans push.

## Revue

- Les patches DE/IT restaurent les 12 tuiles anglaises avant de repeindre
  uniquement « KP » / « PS » dans la boîte 6×14 ; les deux glyphes ont quatre
  rangées de remplissage et leur contour est produit par `_outline`.
- Les ROMs reconstruites décodent chacune 384 octets à `0x00E9B4B8`. Les
  tuiles 0–8 et 11 sont identiques à EN, comme la colonne 7 de la tuile 10 ;
  seuls les pixels des lettres diffèrent. Les flux occupent 149 octets (DE) et
  146 octets (IT) dans le créneau de 192 octets.
- Le cycle TDD a produit 4 échecs attendus avant correction, puis 24 tests
  ciblés et 8 tests ROM réussis. Le hook a validé 1 528 tests Python
  (1 ignoré), 68 tests Vitest et les builds FR/IT/DE sans collision.
- Aucun E2E DE/IT n’a été ajouté : seule une sauvegarde FR est disponible. La
  preuve demandée est assurée par les comparaisons unitaires et ROM réelles.
- L’issue #84 reste ouverte jusqu’à une release publique contenant le correctif
  FR `1a533b3e` et ce port DE/IT, conformément à son dernier commentaire.

# B-558 — Audit des chaînes anglaises encore vivantes en FR

- [x] Ajouter les tests rouges du scanner sur ROM synthétique.
- [x] Implémenter l’audit extraction EN → sites plausibles → cibles FR vivantes.
- [x] Ajouter le rapport CLI et le manifeste explicite des exceptions volontaires.
- [x] Ajouter la garde `rom` qui refuse toute chaîne anglaise livrée non classée.
- [x] Traduire les quatre entrées du cluster CT et protéger leur valeur active.
- [x] Vérifier la largeur et les trois pointeurs du titre « Toutes les bonnes CT ».
- [x] Reconstruire la ROM FR et trier toutes les détections résiduelles.
- [x] Exécuter les validations ciblées, rapides et ROM, puis relire le diff.

## Revue

- Le titre « Toutes les bonnes CT » mesure 113 px pour une limite conservatrice
  de 176 px ; ses trois pointeurs vivants convergent vers la même chaîne FR.
- Le balayage CFRU classe 218 chaînes exactes : 131 livrées encore à traduire,
  60 anglaises volontaires et 27 reliquats sans preuve de livraison espagnole.
- Chaque revue est liée à l'offset source et au SHA-256 du texte : ajout,
  suppression ou modification rend la garde ROM rouge.
- Vérifications ciblées : 9 tests unitaires du scanner, 2 tests source du
  cluster CT et 2 tests ROM (inventaire + quatre traductions via pointeurs).

# Issue #147 — Intitulé de quête du Mont Givre

- [x] Lire l’issue et confirmer l’absence de commentaires antérieurs.
- [x] Localiser la dernière entrée active de l’intitulé.
- [x] Ajouter une garde rouge protégeant la formulation demandée.
- [x] Corriger chirurgicalement la source FR.
- [x] Régénérer la chaîne FR et reconstruire la ROM jouable.
- [x] Vérifier le texte décodé dans la ROM construite.
- [x] Exécuter les validations, relire, committer et clôturer l’issue.

## Revue

- L’entrée active `0x1F56313` emploie désormais « Gravis le Mont Givre » ;
  le manifeste FR protège cette formulation et interdit le retour de « Monte ».
- La ROM reconstruite décode exactement « Gravis le Mont Givre et dirige-toi
  vers Cimistral ! » à `0x1F56313`, avec terminateur `0xFF`, et ne contient
  plus l’ancienne chaîne encodée.
- Le cycle TDD a produit l’échec attendu sur l’ancienne formulation, puis
  24 tests ciblés réussis. Le hook a validé 1 547 tests Python (1 ignoré),
  68 tests Vitest et les builds FR/IT/DE ; `make test-rom` a ensuite validé
  le rebuild déterministe, 12 gardes de reconstruction et 531 tests ROM
  (35 scénarios optionnels ignorés).

# B-446 — Verrouillage de la barre de vie (#84)

- [x] Verrouiller l'ordre des étapes de build (FR Makefile, DE/IT `lang.yaml`).
- [x] Verrouiller les invariants d'art partagés par les trois langues.
- [x] Verrouiller le contrôle négatif sur une ROM synthétique.
- [x] Comparer les trois ROMs livrées à `englishrom.gba` (barre + caps du menu).
- [x] Verrouiller le branchement du scénario e2e (commande, config, ancre, save).
- [x] Fermer les deux angles morts e2e : captures vides et libellé non traduit.
- [x] Éprouver chaque verrou en cassant volontairement ce qu'il garde.

## Revue

- 25 verrous Python (`tests/test_hp_bar_locks.py`) et 13 cas e2e ; les captures
  mGBA sont mutualisées par build, donc les 7 nouveaux cas e2e ne coûtent
  aucune exécution d'émulateur supplémentaire.
- Mutations vérifiées : ordre DE inversé → échec ; restauration de la planche
  anglaise retirée → échec ; ROM régressée → les 4 contrôles ROM échouent ;
  cas français pointé sur `englishrom.gba` → le contrôle de libellé échoue.
- Aucune modification du correctif lui-même : ce ticket n'ajoute que des tests,
  la documentation de conception et le suivi.

# Issue #151 — Titre de mission « The Food Thief »

- [x] Lire l’issue et confirmer la formulation « Voleur de vivres ».
- [x] Identifier l’offset réellement visé par les trois pointeurs du moteur.
- [x] Ajouter et exécuter la garde ROM rouge.
- [x] Ajouter l’entrée active `0x1fa4e10`.
- [x] Régénérer la chaîne FR et reconstruire la ROM jouable.
- [x] Vérifier les trois motifs, le diff binaire et les validations.
- [x] Relire le diff et préparer le commit de résolution.

## Revue

- Le titre actif est désormais « Voleur de vivres » à `0x1FA4E10`.
- Le JSON générique et le passe inline ignorent cet offset ; le patch
  `mission_titles.py` l'écrit en place avant de restaurer la description
  voisine via `mission_descriptions.py`.
- La ROM finale ne diffère de la ROM témoin que sur les 15 octets du titre.
  Les 18 tests ciblés, 1 574 gardes rapides et 530 tests ROM hors émulateur
  passent ; le rebuild est byte-identique et les trois motifs restent inchangés.
- Le replay de capture est intrinsèquement instable dans cet environnement :
  il a produit à la fois OK et RESET sur la ROM finale, et RESET trois fois sur
  la ROM témoin byte-identique hors titre. Aucun octet de code n'est modifié.

# Issue #144 — Suivi des couleurs dans l’aide du menu Options

- [x] Lire le commentaire de suivi et identifier la seconde chaîne `0x1F4E4E2`.
- [x] Ajouter une régression rouge sur le pointeur vivant `0x1EBD064`.
- [x] Colorer uniquement « Sauver » en vert et « ignorer » en rouge.
- [x] Protéger la nouvelle valeur contre les réécritures.
- [x] Reconstruire la ROM FR et vérifier les octets pointés.
- [x] Exécuter les validations post-build et intégrer le commit.

## Revue

- La phrase d’aide est une chaîne distincte de la liste des trois choix :
  l’entrée `0x1F4E4E2` est désormais verte sur « Sauver », rouge sur
  « ignorer » et restaure le noir autour de chaque mot.
- Le build relocalise la chaîne à `0x185D26` et repointe le consommateur vivant
  `0x1EBD064`. Le test compare les octets CFRU exacts, y compris le saut de
  ligne avant « sélectionnées » déjà visible sur la capture.
- Le cycle TDD a reproduit l’absence de couleurs avant le changement, puis les
  28 tests ciblés ont réussi. Le hook a validé 1 608 tests Python
  (1 ignoré), 68 tests Vitest et les builds FR/IT/DE.
- `make test-rom` a confirmé deux rebuilds FR byte-identiques, 12 gardes de
  reconstruction et 554 tests ROM réussis (35 scénarios optionnels ignorés).
# Issue #155 — graphisme éditable de l’écran titre

- [x] Étendre le pipeline PNG et tuiles GBA au 8 bpp par cycles TDD.
- [x] Enregistrer la planche, la tilemap et la palette de l’écran titre.
- [x] Extraire `title_screen.png` et prouver son round-trip sur une copie de ROM.
- [x] Exécuter les validations ciblées et élargies.
- [x] Préparer le bilan GitHub et la clôture de l’issue en `completed`.

## Revue

- « PRESS START » est un graphisme BG1 8 bpp, pas une chaîne CFRU. Le registre
  expose désormais la planche `0x01FD4854`, la tilemap `0x01FD6514` et la
  palette 256 couleurs `0x01FD699C` sous le nom `title_screen`.
- `languages/fr/sprites/title_screen.png` est un écran indexé éditable de
  256 × 160. « APPUYEZ SUR START » tient dans la zone visible ; l’asset anglais
  reste volontairement hors de `build-fr` jusqu’à validation du nouveau dessin.
- Le pipeline PNG/tuiles accepte maintenant le 4 et le 8 bpp sans changer les
  appels historiques. Les BMP restent strictement 4 bpp et rejettent les
  indices qui auraient auparavant été tronqués silencieusement.
- Le round-trip réel compare les tuiles et la tilemap décompressées, la palette
  et les octets hors flux. Les validations finales comptent 1 619 tests Python
  réussis (1 ignoré), 2 415 tests collectés et 68 tests Vitest réussis.

# Issue #157 — Majuscule à Esquive

- [x] Ajouter les gardes source et ROM pour le nom de statistique `Esquive`.
- [x] Constater l’échec des gardes sur la valeur actuelle `esquive`.
- [x] Corriger chirurgicalement la dernière entrée `0x3FD5C1`.
- [x] Protéger la valeur attendue dans `protected_entries.yaml`.
- [x] Reconstruire la ROM FR et vérifier le pointeur vivant `0x3FD5EC`.
- [x] Exécuter les validations ciblées et globales.
- [x] Relire et committer uniquement les fichiers de l’issue.

## Revue

- La source active `0x3FD5C1` contient désormais `Esquive` et le manifeste
  interdit explicitement le retour de `esquive` pour l’issue #157.
- Le pointeur de combat `0x3FD5EC` résout `0x3FD5C1` et décode `Esquive` dans
  `output/roms/GenedRom-fr.gba`.
- Le cycle rouge a échoué sur les deux anciennes valeurs minuscules ; après le
  rebuild, les 12 tests ciblés passent et la garde d’intégrité FR est verte.
- Le hook complet a validé 1 637 tests Python (1 ignoré), 68 tests Vitest et les
  builds FR/IT/DE. Le diff ROM final est limité à l’octet de casse attendu :
  `0x3FD5C1`, `0xD9` (`e`) vers `0xBF` (`E`).

# Issue #158 — Statistiques d’une capacité en combat

- [x] Lire l’issue et tracer les cinq chaînes jusqu’aux pointeurs consommés.
- [x] Comparer correction directe, patch post-build et surcharge last-wins ; retenir la
  surcharge last-wins, mécanisme natif le plus petit et entièrement repointable.
- [x] Ajouter et exécuter la garde rouge sur les libellés source et ROM.
- [x] Ajouter les cinq traductions actives et leurs protections anti-régression.
- [x] Régénérer la traduction, reconstruire la ROM et suivre les six pointeurs vivants.
- [x] Exécuter les validations ciblées puis élargies.
- [x] Relire le diff, committer et clôturer l’issue GitHub.

## Décision

Les cinq valeurs sont des chaînes CFRU pointées. Elles doivent rester dans le pipeline de
traduction : une surcharge en fin de `combined_fr.txt` laisse le moteur relocaliser les
formes plus longues (`Précis. :`) sans introduire de patch binaire spécifique. Le test ROM
suit les deux consommateurs de `Power` et les quatre pointeurs de catégorie/précision.

## Revue

- Les deux pointeurs de puissance convergent vers « Pouvoir : » ; les quatre autres
  rendent respectivement « Précis. : », « - », « Physique » et « Spécial ».
- Le build a relocalisé les deux libellés allongés à `0x904D32` et `0x904D46`, puis a
  repointé leurs consommateurs sans modifier les adresses de code.
- Le cycle TDD a échoué sur les cinq anciennes valeurs, puis réussi sur la source et la
  ROM reconstruite. Le hook a validé 1 637 tests Python (1 ignoré), 68 tests Vitest et les
  builds complets FR/IT/DE ; les 2 gardes ciblées, dont le suivi ROM, réussissent.

# Issue #160 — Envoyer un autre Pokémon ?

- [x] Lire l’issue et localiser la dernière entrée active.
- [x] Tracer l’offset source jusqu’au pointeur vivant du combat.
- [x] Ajouter et exécuter les gardes source et ROM rouges.
- [x] Corriger chirurgicalement la source FR.
- [x] Régénérer la chaîne FR et reconstruire la ROM jouable.
- [x] Vérifier le texte décodé au pointeur vivant.
- [x] Exécuter les validations, relire, committer et clôturer l’issue.

## Revue

- La source active `0x3FB359` affiche désormais « Envoyer un autre Pokémon ? »
  et interdit explicitement l’ancienne formulation dans le manifeste protégé.
- Le pointeur de combat `0x3FE450` vise `0x1937C0` dans la ROM construite ; la
  chaîne décodée est exacte, terminée par `0xFF`, et l’ancienne forme encodée
  n’est plus présente.
- Le pipeline CSV `--extend` a produit 19 383 traductions sans erreur ; le build
  en a remplacé 18 665 sans aucun échec et deux rebuilds sont byte-identiques.
- Le test ROM complet compte 560 réussites et 35 scénarios optionnels ignorés.
  Son unique échec est le replay de capture mGBA déjà documenté comme instable
  dans l’issue #151 ; rejoué isolément sur cette même ROM, il réussit.
- La validation a aussi révélé l’ancien offset erroné `0x1F58E33` de Rougebois.
  Il est aligné sur son pointeur vivant `0x1F58E34` et protégé pour éviter que
  le pipeline CSV ne réintroduise « Redwood Village ».

# Issue #46 — distinguer « Active » et « Actives » dans le menu Missions

## Diagnostic et conception

- La chaîne source `0x1F5605C` est consommée par deux pointeurs distincts après le
  build : `0x1EBFFC8` pour l’onglet blanc en haut à gauche et `0x1FB40B8` pour le
  statut bleu affiché au bout de chaque ligne de mission.
- Le correctif précédent a relocalisé « Actives » puis repointé les deux sites vers
  cette même copie, ce qui a rendu le statut individuel incorrectement pluriel.
- Remettre `combined_fr.txt` à « Active » corrigerait le statut mais ferait régresser
  l’onglet. Allouer une seconde chaîne en espace libre est inutile : la cellule
  originale de sept octets contient déjà exactement « Active » avec son terminateur.
- La solution minimale étend le patch post-build Missions : l’onglet conserve la
  cible relocalisée « Actives », tandis que le seul pointeur de statut est ramené vers
  la cellule originale, validée défensivement comme « Active ». Le suffixe partagé reste
  vide comme aujourd’hui.

## Plan validé

- [x] Distinguer dans le garde ROM le pointeur d’onglet pluriel et le pointeur de
  statut singulier, puis constater l’échec sur la ROM actuelle.
- [x] Ajouter un test synthétique rouge qui exige la séparation des deux pointeurs.
- [x] Étendre `languages/fr/patches/mission_tab_labels.py` avec la séparation minimale,
  bornée et idempotente.
- [x] Valider les tests ciblés, puis committer les sources avant tout build ROM.
- [x] Reconstruire la ROM FR et décoder les deux pointeurs vivants dans l’artefact.
- [x] Exécuter les gardes de build et la suite rapide, relire le diff et rebaser.
- [ ] Publier le résultat sur l’issue #46 et la clôturer en `completed`.

## Auto-revue de la conception

- Le périmètre reste limité au menu Missions et ne modifie ni le pipeline partagé ni
  les autres langues.
- Chaque contexte possède une attente observable indépendante : « Actives » pour
  `0x1EBFFC8`, « Active » pour `0x1FB40B8`.
- La mutation réaliste « repointer de nouveau les deux sites vers Actives » est captée
  par le garde ROM et par le test unitaire du patch.

## Revue de réalisation

- Le patch post-build laisse `0x1EBFFC8` pointer vers la copie relocalisée
  « Actives » et repointe uniquement `0x1FB40B8` vers la cellule source
  `0x1F5605C`, qui décode « Active ».
- Les tests du patch passent 8/8, dont la sauvegarde `.bak` exacte et la lecture
  de la ROM versionnée ; les tests ciblés patch/intégrité passent 34/34 et les
  13 gardes de régression du build FR passent.
- La suite rapide exécutée par le hook passe 1 642 tests Python (1 skip), puis les
  68 tests Vitest ; les builds FR, IT et DE réussissent sans collision.
- `make test-rom` confirme deux builds FR byte-identiques et sort à zéro :
  566 tests réussis, 38 scénarios optionnels ignorés et 1 854 exclus par le profil
  après rebase sur la dernière tête de `unbound`.
- Le mot français « Active », identique à sa source anglaise, est désormais classé
  explicitement dans l’audit des chaînes anglaises vivantes.
# Issue #162 — Panneau Astuces de Dresseurs

## Décision

L’offset pointé `0x1F732BD` utilise le pipeline de traduction standard et ne possède
qu’une ancienne occurrence majuscule. La correction minimale consiste à ajouter une
occurrence vivante dans le bloc hexadécimal minuscule, puis à laisser le rewrap et la
relocalisation existants produire la ROM. Un patch post-build serait redondant ; modifier
l’occurrence majuscule seule serait fragile dès qu’une surcharge last-wins apparaît.

## Plan TDD

- [x] Lire l’issue, ses commentaires et les captures, puis tracer le pointeur `0x1E9368B`.
- [x] Ajouter les gardes source et ROM pour le titre, la formulation et le saut avant L.
- [x] Exécuter les gardes en rouge sur la traduction actuelle.
- [x] Ajouter chirurgicalement la traduction vivante et sa protection anti-régression.
- [x] Régénérer le CSV et le JSON, puis reconstruire la ROM FR.
- [x] Vérifier le texte décodé au pointeur vivant et exécuter les validations élargies.
- [x] Relire le diff, committer, intégrer et clôturer l’issue GitHub.

## Revue

- La dernière occurrence active `0x1F732BD` porte « Astuces de Dresseurs »,
  supprime « vite » et place un saut de page `\\p` juste avant le second bouton L.
- Le pointeur du panneau `0x1E9368B` atteint bien cette traduction dans la ROM
  reconstruite ; le test décode les contrôles CFRU et vérifie le texte affiché complet.
- Le test ciblé et la garde des manifestes réussissent (2 tests), puis `make test-rom`
  valide 567 tests ROM, avec 36 scénarios optionnels ignorés. Deux reconstructions FR
  consécutives sont byte-identiques.
- Le hook de commit valide en plus 1 648 tests Python, 68 tests Vitest et les builds
  complets FR, IT et DE.

# Issue #161 — Dresseurs Nageur/nageuse

## Diagnostic et conception

- Les classes adultes `Swimmer♂` et `Swimmer♀` disposent déjà de deux cellules
  distinctes traduites par « Nageur♂ » et « Nageuse♀ ».
- La classe `Tuber` utilise une seule cellule fixe de 13 octets pour sept
  dresseurs, dont Lola ; changer leurs identifiants de classe modifierait aussi
  des paramètres de combat tels que les gains.
- La correction minimale et sans effet de bord remplace donc « Baigneur » par
  « Nageur » dans la cellule partagée `0x23EA6C`.

## Plan validé

- [x] Ajouter une régression rouge sur le patch et la ROM construite.
- [x] Corriger chirurgicalement l’entrée active et la protéger dans le manifeste.
- [ ] Committer les sources avant de reconstruire la ROM FR.
- [ ] Décoder les trois cellules Nageur/Nageuse dans la ROM livrée.
- [ ] Exécuter les validations ciblées et globales, puis relire le diff.
- [ ] Intégrer localement, commenter et clôturer l’issue GitHub.
