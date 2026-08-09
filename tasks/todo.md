# Issue #170 — description « Retirer Pokémon » du PC

## Diagnostic et conception

- La description affichée vient de l’entrée pointée active `0x4185AD` dans
  `languages/fr/combined_fr.txt` ; elle relève du pipeline de traduction.
- Le ticket fournit le libellé cible exact : « Intégrer dans l'équipe des
  Pokémon pris des boîtes. ».
- La correction minimale modifie cette seule valeur, la protège dans le
  manifeste d’intégrité, puis vérifie le pointeur vivant de la ROM reconstruite.

## Plan validé

- [x] Ajouter la garde rouge pour la valeur exacte demandée.
- [x] Corriger chirurgicalement l’entrée active `0x4185AD`.
- [x] Committer les sources avant d’exécuter la chaîne de build FR.
- [x] Reconstruire la ROM et décoder le texte réellement livré.
- [x] Exécuter les validations pertinentes, relire le diff et intégrer localement.
- [x] Commenter puis clôturer l’issue GitHub #170 avec l’état `completed`.

## Revue

- La source active `0x4185AD` livre désormais « Intégrer dans l'équipe des
  Pokémon pris des boîtes. » et le manifeste interdit explicitement l'ancien
  libellé.
- Dans la ROM FR reconstruite, le pointeur vivant `0x3CDA34` cible toujours
  `0x4185AD` et décode « Intégrer dans l'équipe des Pokémon\npris des boîtes. »
  sur deux lignes, avec un terminateur `0xFF` à `0x4185E0`.
- La validation ciblée post-rebase passe 31 tests ; le hook valide 1 672 tests
  Python, 68 tests Vitest et les builds complets FR, IT et DE.
- Deux builds FR consécutifs sont byte-identiques. Après rebase sur les issues
  #171 et #172, `make test-rom` valide 584 tests et en ignore 37, sans échec ;
  les probes mGBA IT et DE auparavant instables passent également.

# Issue #172 — Centre Pokémon de Dresco

## Diagnostic et conception

- Le dialogue est l'entrée active unique `0x1F02DD8` de
  `languages/fr/combined_fr.txt`.
- Le dernier paragraphe perd les couleurs sémantiques de la source EN et emploie
  une formulation imprécise ; le reste de la longue entrée est déjà correct.
- La correction minimale remplace seulement ce paragraphe, réutilise la paire
  verte `FC 01 06` / `FC 01 08` et fixe trois lignes sous 192 px.

## Plan validé

- [x] Ajouter une garde rouge sur le libellé, la couleur et les trois lignes.
- [x] Corriger chirurgicalement l'entrée et son manifeste de protection.
- [x] Committer la source avant la chaîne de build FR.
- [x] Reconstruire puis décoder la chaîne réellement injectée dans la ROM.
- [x] Exécuter les validations, relire le diff et préparer l'intégration locale.
- [x] Préparer le commentaire et la clôture de l'issue GitHub #172.

## Revue

- La dernière réplique est désormais « À la Route 2, Picassaut et Hoothoot ont
  Regard Vif. Attrape-les tous. », avec une coupure avant « Attrape-les tous. ».
- La ROM reconstruite décode cette entrée entre `0x1F02DD8` et `0x1F02EF7`,
  terminée par `0xFF`, et encadre « Regard Vif » par `FC 01 06` / `FC 01 08`.
- Les trois lignes mesurent 147, 135 et 94 px, sous la limite de 192 px.
- Les 31 tests ciblés passent, tout comme les 1 675 tests Python et 68 tests
  Vitest du hook ; les builds FR/IT/DE réussissent et `make test-rom` termine
  avec 583 succès et 36 skips. Deux builds FR consécutifs sont identiques.
- La ROM livrée est byte-identique à un build propre après rebase.

# Issue #169 — « Aucun courrier ici » → « Pas de lettre ici. »

## Diagnostic et conception

- La chaîne pointée active est l’entrée unique `0x4177EE` de
  `languages/fr/combined_fr.txt` ; elle conserve le contrôle
  `{PAUSE_UNTIL_PRESS}` présent dans la source.
- La correction minimale remplace uniquement le libellé par
  « Pas de lettre ici. », protège sa valeur exacte et laisse le pipeline
  reloger la chaîne si nécessaire.

## Plan validé

- [x] Ajouter une garde de régression rouge sur l’entrée active.
- [x] Corriger chirurgicalement l’entrée et committer les sources avant le build.
- [x] Régénérer la traduction et reconstruire la ROM française.
- [x] Suivre le pointeur vivant et décoder la phrase réellement livrée.
- [x] Exécuter les validations pertinentes, relire le diff et intégrer localement.
- [x] Préparer le commentaire et la clôture GitHub #169 avec l’état `completed`.

## Revue

- L’entrée active `0x4177EE` contient désormais « Pas de lettre ici. » et
  conserve l’attente `{PAUSE_UNTIL_PRESS}`.
- Les pointeurs `0xEB938` et `0xEB9B0` atteignent tous deux `0x4177EE` dans
  la ROM reconstruite ; les octets finissent par `FC 09 FF`.
- Le manifeste protège la nouvelle valeur et interdit les deux variantes de
  l’ancienne formulation « Aucun courrier ici. ».
- Le cycle rouge/vert de la garde d’intégrité a été observé. Le hook valide
  1 674 tests Python, 68 tests Vitest et les builds FR/IT/DE ; `make test-rom`
  valide 583 tests, avec 36 scénarios dépendants de fixtures ignorés.
- Deux builds FR consécutifs sont byte-identiques.
# Issue #155 — suivi : restaurer le dernier « T » de « PRESSEZ START »

## Diagnostic et conception

- Le PNG intégré diffère du BMP fourni uniquement aux pixels `(160,152)` et
  `(160,153)`, où l’indice animé 164 a été remplacé par le fond 31.
- Cette cellule utilise la tuile 99, partagée par 94 cellules ; la modifier en
  place corromprait 93 zones de fond.
- La cellule reçoit une 460e tuile dédiée ; la planche grandit de 64 octets
  décompressés mais se compacte à 7 319 octets, sous son slot de 7 360 octets.
- La tilemap remappée occupe 1 161 octets compressés dans un slot de 1 160.
- La planche et la tilemap ont chacune deux pointeurs ROM vérifiés. La solution
  sûre garde la planche en place et relocalise uniquement la tilemap via ses
  deux références connues.

## Plan de reprise

- [x] Ajouter la régression rouge sur le BMP complet et les flux repointés.
- [x] Déclarer les pointeurs connus et restaurer les deux pixels dans le PNG.
- [x] Prouver le round-trip pixel par pixel depuis une ROM réelle.
- [x] Reconstruire la ROM FR et vérifier les pointeurs, la palette et le rendu.
- [x] Revalider le clignotement dans mGBA sans sauvegarde en jeu.
- [x] Exécuter les tests ciblés puis complets, relire et committer.
- [ ] Rebaser localement, commenter l’issue #155 et terminer sans push.

## Revue du suivi

- Le PNG versionné correspond au BMP du commentaire sur ses 40 960 indices et
  ses 256 couleurs ; les pixels `(160,152)` et `(160,153)` valent désormais
  tous deux 164.
- La planche gagne une tuile dédiée sans bouger (`0x01FD4854`). La tilemap est
  relocalisée et ses deux pointeurs convergent vers le même flux ; l’extracteur
  suit désormais ces pointeurs connus et réexporte la grille complète exacte.
- La palette à `0x01FD699C` et tous les octets hors planche, pointeurs et nouveau
  flux tilemap restent inchangés. Deux builds FR successifs sont byte-identiques.
- Une sonde mGBA sur 360 frames confirme que les deux pixels restaurés passent
  par au moins deux couleurs et continuent donc de clignoter ensemble.
- Vérifications : 35 tests sprite ciblés, `make test-rom` avec 583 réussites et
  36 skips, plus le hook source avec 1 674 tests Python, 68 tests Vitest et les
  builds FR/IT/DE. La première revue indépendante a trouvé deux lacunes
  (extraction post-relocalisation et empreinte partielle), toutes deux corrigées.

# Issue #167 — libellés des options du PC

## Diagnostic et conception

- Les trois options sont des chaînes pointées par la table du menu PC :
  `0x3CDA20`, `0x3CDA28` et `0x3CDA40`.
- Les traductions actives viennent de `0x41858D`, `0x41859A` et `0x4185A5` ;
  l'injection sait les reloger lorsqu'elles dépassent leur cellule anglaise.
- L'injection générique de nouveaux libellés modifie l'empreinte de l'allocateur
  et rend des savestates existants incompatibles. Les valeurs canoniques doivent
  donc être relogées par le patch dédié après une injection à empreinte stable.

## Plan validé

- [x] Ajouter les gardes rouges source/ROM pour les trois libellés exacts.
- [x] Corriger chirurgicalement les trois entrées et leur manifeste de protection.
- [x] Retirer l'override abrégé du patch PC sans toucher aux autres menus compacts.
- [x] Committer les sources avant d'exécuter la chaîne de build FR.
- [x] Reconstruire la ROM et décoder les trois pointeurs réellement livrés.
- [x] Exécuter les validations pertinentes, relire le diff et intégrer localement.
- [x] Commenter puis clôturer l'issue GitHub #167 avec l'état `completed`.

## Revue

- La source active livre désormais « Déplacer Pokémon », « Déplacer objet » et
  « Salut ! » ; les anciennes formes sont interdites par le manifeste FR.
- Les pointeurs `0x3CDA20`, `0x3CDA28` et `0x3CDA40` décodent ces trois libellés
  dans la ROM reconstruite, aux emplacements stables `0x15FBCD0`, `0x15FBCF0`
  et `0x15FBD10`, tous terminés par `0xFF`.
- Le patch post-build conserve les libellés compacts « Dépl. », mais ne remplace
  plus l'option principale par l'ancienne abréviation « Dépl Pokémon ».
- Deux builds FR consécutifs sont byte-identiques ; `make test-rom` termine avec
  575 tests réussis, 36 ignorés et 1 862 désélectionnés.
- Le hook du commit source valide en plus 1 655 tests Python, 68 tests Vitest et
  les trois builds complets FR, IT et DE.
- Après rebase sur l'ajout concurrent du préfixe « Boîte », sa relocation a été
  isolée à `0x15FBCB0` afin de préserver l'ordre de l'allocateur générique.

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

## Réouverture du 4 août 2026

- [x] Relire le nouveau commentaire et sa capture : le correctif précédent a
  inversé les deux contextes visuels.
- [x] Faire échouer les gardes avec la cartographie observée : statut bleu
  `0x1EBFFC8` → « Active », onglet blanc `0x1FB40B8` → « Actives ».
- [x] Corriger le patch post-build sans modifier les chaînes de traduction.
- [x] Reconstruire la ROM, décoder les deux pointeurs et lancer `make test-rom`.
- [ ] Rebaser, revalider et publier le résultat sur l'issue #46.

## Diagnostic et conception

- La nouvelle capture identifie les deux pointeurs distincts après le build :
  `0x1EBFFC8` alimente le statut bleu affiché au bout de chaque ligne de mission,
  tandis que `0x1FB40B8` alimente l’onglet blanc en haut à gauche.
- Le correctif précédent avait attribué ces contextes à l’envers : il laissait
  `0x1EBFFC8` sur « Actives » et ramenait `0x1FB40B8` vers « Active », reproduisant
  exactement l’inversion visible sur la capture.
- Modifier `combined_fr.txt` ferait partager de nouveau une seule forme aux deux
  contextes. Allouer une seconde chaîne est inutile : la cellule originale de sept
  octets contient déjà exactement « Active » avec son terminateur.
- La solution minimale corrige la cartographie du patch post-build Missions : l’onglet
  `0x1FB40B8` conserve la cible relocalisée « Actives », tandis que le statut
  `0x1EBFFC8` revient vers la cellule originale « Active ». Le suffixe partagé reste
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
- Chaque contexte possède une attente observable indépendante : « Active » pour
  `0x1EBFFC8`, « Actives » pour `0x1FB40B8`.
- La mutation réaliste « repointer de nouveau les deux sites vers Actives » est captée
  par le garde ROM et par le test unitaire du patch.

## Revue de réalisation

- Le patch post-build laisse `0x1FB40B8` pointer vers la copie relocalisée
  « Actives » et repointe uniquement `0x1EBFFC8` vers la cellule source
  `0x1F5605C`, qui décode « Active ».
- Les tests synthétiques du patch passent 7/7 et les gardes ciblés sur la ROM
  construite passent 14/14, dont la sauvegarde `.bak` exacte, l’idempotence et la
  séparation explicite des deux contextes.
- La suite rapide exécutée par le hook passe 1 666 tests Python (1 skip), puis les
  68 tests Vitest ; les builds FR, IT et DE réussissent sans collision.
- La première exécution de `make test-rom` a validé 575 tests et ignoré 38 scénarios
  optionnels ; son seul échec, le replay du premier combat italien, n’a signalé ni
  gel ni texte anglais et a réussi immédiatement en isolation. Une exécution finale
  sans contention est conservée comme preuve avant livraison.
- La ROM reconstruite résout `0x1EBFFC8` vers `0x1F5605C` (« Active ») et
  `0x1FB40B8` vers `0xE58DAA` (« Actives ») ; son SHA-256 est
  `4364276e526961f7c4a8edbb08c8cfed29d2c424a77253f629611d7f02ffba16`.
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
- [x] Committer les sources avant de reconstruire la ROM FR.
- [x] Décoder les trois cellules Nageur/Nageuse dans la ROM livrée.
- [x] Exécuter les validations ciblées et globales, puis relire le diff.
- [ ] Intégrer localement, commenter et clôturer l’issue GitHub.

## Revue

- La ROM construite décode `Nageur♂` à `0x23E8E6`, `Nageuse♀` à
  `0x23E91A` et `Nageur` à `0x23EA6C`, chacune terminée par `0xFF`.
- La source active est protégée contre le retour de « Baigneur » et le test
  couvre à la fois le patch synthétique et les octets réellement livrés.
- La double reconstruction FR est identique octet pour octet ; les 12 tests de
  reconstruction et 564 tests ROM passent. Le seul échec global est le probe
  italien préexistant qui n’atteint pas son premier combat (`froze: false`) ;
  tous les contrôles FR passent.
- La classe `Tuber` restant une cellule partagée par sept dresseurs, une
  différenciation par prénom ou sprite demanderait de modifier les classes des
  données dresseur et leurs effets de gameplay ; elle est volontairement hors
  de cette correction textuelle sûre.

# Issue #143 — Suivi du badge adverse `BRN`

- [x] Lire le nouveau commentaire et isoler le chemin graphique adverse.
- [x] Comparer la table brute du healthbox aux quatre blocs LZ77 déjà corrigés.
- [x] Ajouter une garde rouge sur les quatre copies par battler.
- [x] Dériver les tuiles brutes du même BMP canonique en préservant palettes et caps.
- [x] Reconstruire la ROM FR et vérifier `POI/PAR/SOM/GEL/BRU` dans chaque copie.
- [x] Exécuter les validations ciblées puis élargies.
- [x] Relire, committer et préparer le rebase et la clôture de l’issue GitHub.

## Décision

Le moteur n’utilise pas un cinquième bloc LZ77 pour le statut adverse :
`UpdateStatusIconInHealthbox` indexe une table brute de trois tuiles par statut et par
battler. L’approche retenue étend donc `status_badges.py` à ces quatre groupes bruts,
en réutilisant les deux tuiles centrales du BMP fourni et en laissant byte-identique
la troisième tuile de cap. Un script séparé ou un repointage du moteur ajouterait une
seconde source graphique sans bénéfice et augmenterait inutilement le risque ROM.

## Revue du suivi adverse

- Les quatre groupes bruts utilisés par `UpdateStatusIconInHealthbox` sont désormais
  alimentés depuis `status_badges.bmp`, avec leur indice de palette propre aux battlers.
- Les deux tuiles de contenu sont remplacées ; la troisième tuile de fermeture est
  vérifiée contre le BMP puis laissée byte-identique afin de préserver la healthbox.
- Le groupe adverse gauche `0x00D124A4` et le groupe adverse droit `0x00D12864`
  affichent notamment `BRU` au lieu de `BRN`, comme les deux groupes du joueur.
- La ROM FR a été reconstruite deux fois à l’identique. Les 8 tests ciblés passent ;
  `make test-rom` termine avec 567 tests réussis et 36 ignorés.

# Issue #166 — PC : sélection des boîtes

## Diagnostic et conception

- L’anglais vivant à `0x4184A9` est « Jump » ; sa traduction actuelle « Aller »
  conserve le verbe mais ne nomme pas correctement l’action du menu.
- Cette chaîne compacte possède un pointeur source et reste relogeable par le pipeline
  standard. La correction minimale consiste donc à modifier l’entrée FR active en
  « Boîtes », sans patch binaire dédié ni changement partagé aux autres langues.

## Plan TDD

- [x] Lire l’issue et confirmer l’offset, la source anglaise et la valeur FR actuelle.
- [x] Ajouter les gardes source et ROM, puis observer leur échec attendu.
- [x] Corriger chirurgicalement la dernière occurrence active.
- [x] Committer les sources avant le build, puis reconstruire la ROM FR.
- [x] Suivre le pointeur vivant et décoder « Boîtes » dans la ROM construite.
- [x] Exécuter les validations ciblées et globales, relire le diff et intégrer.

## Revue

- Le slot vivant `0x3D3560` pointe vers `0xD10E23`, où les octets
  `BC E3 20 E8 D9 E7 FF` se décodent exactement en « Boîtes ».
- Le test TDD a d’abord échoué sur « Aller », puis les 4 tests du menu PC et les
  27 tests de la garde d’intégrité passent après la correction.
- Le hook de commit passe avec 1 654 tests Python, 68 tests Vitest et les builds
  FR/IT/DE sans collision ; deux reconstructions FR sont identiques octet pour octet.
- `make test-rom` valide 572 tests et en ignore 36. Son unique échec est le probe
  mGBA italien du premier combat, sans gel ni anglais détecté ; ce test hors périmètre
  passe deux fois de suite lorsqu’il est rejoué isolément.

# Issue #163 — extraire les dessins des boîtes PC

- [x] Lire l’issue et confirmer que les trois libellés sont des tuiles graphiques.
- [x] Localiser la planche LZ77, son pointeur et sa palette de prévisualisation.
- [x] Formaliser l’extraction unique, éditable et non injectée dans le build FR.
- [x] Ajouter les gardes rouges du registre et de l’asset.
- [x] Enregistrer la planche et extraire le PNG depuis la ROM anglaise.
- [x] Prouver le round-trip et exécuter les validations élargies.
- [x] Propager les pointeurs connus au chemin générique des blocs non mappés.
- [x] Automatiser le round-trip CLI sur une copie de la ROM et vérifier le backup.
- [x] Marquer `rom` uniquement les tests qui lisent `englishrom.gba`.
- [ ] Relire, committer, intégrer et clôturer l’issue GitHub.

## Revue

- Le registre expose `pc_box_labels` : bloc LZ77 `0x00E9C438`, pointeur
  vérifié `0x0008F034`, palette `0x003CE5DC` et grille 16 × 9 tuiles.
- Le PNG indexé extrait de `englishrom.gba` mesure 128 × 72 ; ses indices sont
  identiques aux 4 608 octets décompressés de la planche source.
- Si le flux recompressé dépasse son slot, `insert_block` réutilise la
  relocalisation commune et ne repointe que `block_pointers`; sans pointeur
  déclaré, le refus de débordement reste inchangé.
- Le round-trip est désormais un test subprocess du CLI : copie temporaire de
  la ROM anglaise, réinjection du PNG, égalité des 4 608 octets et backup
  byte-identique. Les gardes registre/asset/build restent dans le profil rapide.
# Issue #143 — suivi : tous les statuts alliés et adverses en combat

## Diagnostic et plan

- Le commentaire demande d’appliquer la correction à tous les statuts affichables en
  combat, pour les battlers alliés comme adverses.
- `UpdateStatusIconInHealthbox` sélectionne cinq groupes graphiques dans l’ordre
  `POI`, `PAR`, `SOM`, `GEL`, `BRU`; les battlers 0/2 sont alliés et 1/3 adverses.
- Le patch livré au suivi précédent écrit déjà ces cinq statuts dans les quatre groupes
  bruts. Le risque restant est une preuve trop agrégée, qui ne nomme pas explicitement
  chaque couple statut/camp.

- [x] Exécuter la garde ROM actuelle et confirmer les 20 combinaisons.
- [x] Ajouter une régression explicite par statut et par camp si la couverture manque.
- [x] Reconstruire la ROM FR par la chaîne canonique et vérifier les octets consommés.
- [x] Exécuter les validations ciblées puis la validation ROM requise.
- [x] Relire le diff, intégrer localement et répondre sur l’issue #143 sans push.

## Revue

- La garde existante compare déjà les cinq badges de chaque groupe brut au BMP canonique;
  aucune combinaison n’était absente et aucun nouveau patch de production n’est requis.
- Une vérification nominative indépendante confirme `POI`, `PAR`, `SOM`, `GEL` et `BRU`
  pour les battlers alliés 0/2 et adverses 1/3, soit 20 rendus sur 20.
- `make build-fr` réinjecte les quatre groupes healthbox et reproduit exactement la ROM
  versionnée : SHA-256 avant/après
  `183d95ad6ce204c3d28e87fede4f3d7d302814d35dfb03128c6783e6d396864e`.
- Les statuts empoisonné et gravement empoisonné partagent le même badge `POI` dans le
  moteur; `KO` et `PKRS` ne sont pas des statuts affichés par la healthbox de combat.
- `python3 -m pytest tests/test_patch_status_badges_fr.py -q` réussit ses 7 tests;
  `make test-rom` réussit 572 tests et en ignore 36 après deux rebuilds byte-identiques.

## Réouverture — terme exact « Flotteur »

- [x] Faire échouer la régression avec `Flotteur` attendu pour `Tuber`.
- [x] Remplacer l’entrée active et la garde protégée par `Flotteur`.
- [x] Reconstruire la ROM FR et décoder la cellule `0x23EA6C`.
- [x] Exécuter les validations ciblées et globales.
- [x] Committer l’artefact et préparer le bilan GitHub pour intégration.

## Revue de la réouverture

- Le test RED a échoué sur `Nageur != Flotteur`, puis les deux tests ciblés
  sont passés après la correction et la reconstruction.
- La ROM décode `Flotteur` à `0x23EA6C` et contient le terminateur `0xFF` ;
  `Nageur♂` et `Nageuse♀` restent inchangés dans leurs cellules distinctes.
- Le manifeste protège désormais contre les deux anciennes valeurs erronées,
  `Baigneur` et `Nageur`.
- `make test-rom` valide 571 tests et en ignore 35 ; la double reconstruction
  FR est identique octet pour octet.
- Le diff binaire de la ROM contient seulement neuf octets modifiés dans la
  cellule fixe de 13 octets ciblée.

## Suivi — intégrer « PRESSEZ START » et préserver le clignotement

- [x] Lire les nouveaux commentaires et récupérer le BMP 8 bpp fourni.
- [x] Comparer sa palette et ses pixels au PNG anglais versionné.
- [x] Ajouter les gardes rouges du dessin français et de son intégration au build.
- [x] Convertir fidèlement le BMP en PNG indexé et brancher `title_screen` dans `build-fr`.
- [x] Reconstruire la ROM et vérifier les pixels, la palette et le clignotement.
- [x] Exécuter les validations, relire, committer et intégrer localement sans push.

### Diagnostic

- Le BMP et le PNG anglais ont la même palette de 256 couleurs.
- Les 197 pixels différents sont limités à `x=80..160`, `y=149..153` : seul le
  libellé devient « PRESSEZ START ».
- Le dessin français conserve les indices 163/164 du prompt anglais ; le code
  et la palette qui pilotent l’animation ne nécessitent aucune modification.
- La dernière lettre déborde de deux pixels dans la tuile de fond 99, partagée
  ailleurs ; ces deux pixels sont ramenés à l’index de fond pour préserver les
  tailles LZ77 et les gardes de conflit existantes.

### Revue du suivi

- Le PNG extrait de `GenedRom-fr.gba` est byte-identique à l’asset versionné
  (SHA-256 `61e783278689a00278933c6acfeea0e8ce2c391705df70e21eca525892951eda`).
- Douze captures mGBA espacées de dix images donnent deux empreintes alternées
  pour la zone du prompt (`d59f23e1b2e7de65` et `b694f91426c93632`) :
  « PRESSEZ START » passe bien de l’état sombre à l’état lumineux.
- Les 24 tests graphiques ciblés passent. Le hook a validé 1 626 tests Python
  (1 ignoré), 68 tests Vitest, puis les builds et contrôles FR/IT/DE ; la
  relecture ne relève aucun problème bloquant, important ou mineur.

# Issue #168 — « Annuler » → « Sortir » dans le stockage d’objets du PC

## Diagnostic et plan

- [x] Lire l’issue et tracer la chaîne affichée jusqu’à sa référence ROM active.
- [x] Ajouter une garde rouge ciblant l’entrée du sous-menu Stockage d’objets.
- [x] Repointer uniquement cette entrée vers la chaîne dédiée « Sortir ».
- [x] Reconstruire la ROM FR et décoder le libellé depuis son pointeur actif.
- [x] Exécuter les validations, relire, committer et intégrer sans push.

La table `sMenuActions_ItemPc` utilise le libellé partagé `gText_Cancel` à
`0x402218`. Le patch existant du menu Équipe possède déjà une chaîne « Sortir »
dédiée ; l’étendre à ce seul pointeur évite de renommer les véritables actions
d’annulation dans le reste du jeu.

## Revue

- Le pointeur `0x402218` du stockage d’objets et le littéral `0x1211E8` du menu
  Équipe ciblent tous deux `0x09FFFF80`, décodé en « Sortir » avec terminateur
  `0xFF` ; la chaîne partagée `gText_Cancel` décode toujours « Annuler ».
- Le diff du ROM livré contient exactement quatre octets, ceux du pointeur PC
  `0x402218` (`0x08E58DB2` → `0x09FFFF80`).
- La garde ciblée réussit ses 8 tests. Le hook a validé 1 674 tests Python
  (1 ignoré), 68 tests Vitest, puis les builds FR, IT et DE.

# Issue #163 — suivi : injecter le dessin français des boîtes PC

## Diagnostic et conception

- Le BMP fourni est une image indexée 4 bpp de 128 × 72 pixels.
- Ses 16 couleurs correspondent indice par indice à la palette ROM
  `0x003CE5DC`; aucune remap de palette n’est nécessaire.
- Le PNG canonique existant sera remplacé par une conversion sans perte, puis
  réinjecté dans `build-fr` via le descripteur et le pointeur déjà vérifiés.

## Plan validé

- [x] Lire le nouveau commentaire et télécharger le BMP joint.
- [x] Vérifier dimensions, profondeur, palette et différences d’indices.
- [x] Ajouter les gardes rouges de l’asset et du câblage `build-fr`.
- [x] Convertir le BMP vers le PNG canonique sans perte d’indices.
- [x] Activer l’insertion de `pc_box_labels` dans la recette FR.
- [x] Reconstruire la ROM et comparer la planche pointée au PNG.
- [x] Exécuter les validations, relire, committer et intégrer sans push.
- [x] Commenter puis clôturer l’issue GitHub avec l’état `completed`.

## Revue

- Le BMP fourni a été converti en PNG 4 bpp sans remapper ses indices ; son
  empreinte de grille est
  `3e8856cdfc9e605b732905e923ec42f950462a6156bef0a971db10b3dea28c9d`.
- `build-fr` réinjecte la planche via `SPRITES["pc_box_labels"]`. Le bloc reste
  à `0x00E9C438`, se décompresse en 4 608 octets et correspond pixel par pixel
  à l’asset versionné.
- Le cycle rouge a détecté l’ancien PNG et le câblage absent. Après build, une
  garde ROM obsolète qui exigeait encore les octets anglais a été corrigée pour
  comparer le résultat du CLI au dessin français et vérifier leur différence.
- Le hook de commit a validé 1 660 tests Python (1 ignoré), 68 tests Vitest et
  les builds FR, IT et DE. Les 43 tests graphiques ciblés, dont les gardes ROM,
  réussissent ; les 1 602 octets de diff ROM sont tous dans le bloc LZ77 visé.

# Issue #174 — « combat herbu » → « combat verdoyant »

## Diagnostic et conception

- La réplique active est l’entrée pointer-based `0x1F62FCC` de
  `languages/fr/combined_fr.txt`; aucune occurrence plus tardive ne l’écrase.
- L’option retenue est une correction chirurgicale de cette entrée, accompagnée
  de sa garde dans `protected_entries.yaml`. Un patch ROM dédié ou une édition
  directe de l’artefact seraient inutiles et non durables.

## Plan validé

- [x] Prouver que la valeur cible est absente avant la correction.
- [x] Remplacer la dernière entrée active et ajouter sa garde de régression.
- [x] Régénérer le JSON FR puis reconstruire la ROM complète.
- [x] Suivre le pointeur vivant et décoder la nouvelle réplique dans la ROM.
- [ ] Exécuter les validations, relire, committer et intégrer sans push.
- [ ] Commenter puis clôturer l’issue GitHub avec l’état `completed`.

## Revue

- Le JSON FR généré contient l’entrée `0x1F62FCC` avec la nouvelle formulation
  et le build ne signale aucun échec d’injection.
- Les pointeurs `0x1E876E0` et `0x1E876B9` visent tous deux `0x1A9D64` dans
  `GenedRom-fr.gba`; la chaîne se décode en « C'est l'heure d'un combat
  verdoyant\nsur le gazon ! » et se termine par `0xFF`.
- La garde ciblée réussit ses 27 tests. Le hook a validé 1 679 tests Python
  (1 ignoré), 68 tests Vitest, puis les builds FR, IT et DE.

# Issue #173 — texte PC

## Diagnostic et conception

- Le menu contextuel montré dans l’issue lit `Move` via les pointeurs
  `0x3D3548` et `0x9A41C4`. Le patch de l’issue #29 les regroupe actuellement
  avec le menu secondaire compact `0xA6CAAC` et traduit les trois par
  « Dépl. ».
- La correction minimale sépare ces contextes : les deux options de sélection
  deviennent « Déplacer », tandis que le menu secondaire et les aides compactes
  conservent « Dépl. ».
- La phrase sous le menu vient de l’entrée active unique `0x41825C` ; sa valeur
  devient `{DYNAMIC} sélectionné.` afin d’obtenir « Nodulithe sélectionné. ».

## Plan validé

- [x] Ajouter les gardes rouges source, patch et ROM pour les deux libellés.
- [x] Séparer les relocalisations du menu PC et corriger chirurgicalement
  l’entrée `0x41825C` ainsi que son manifeste de protection.
- [x] Committer les sources avant d’exécuter la chaîne de build FR.
- [x] Reconstruire la ROM et décoder les pointeurs réellement livrés.
- [x] Exécuter les validations pertinentes, relire le diff et intégrer localement.
- [x] Commenter puis clôturer l’issue GitHub #173 avec l’état `completed`.

## Revue

- La ROM FR encode « Déplacer » à `0x15FBC90`; les pointeurs `0x3D3548` et
  `0x9A41C4` y aboutissent. Le menu secondaire `0xA6CAAC` pointe séparément
  vers « Dépl. » à `0x15FBC99`.
- Les quatre consommateurs de la phrase de sélection pointent toujours vers
  `0x41825C`, décodé en `{DYNAMIC} sélectionné.` dans la ROM reconstruite.
- Le cycle TDD est passé de 4 échecs attendus à 28 tests ciblés réussis. Le
  hook de commit a validé 1 682 tests Python (1 ignoré), 68 tests Vitest et les
  builds FR, IT et DE.
- `make test-rom` a confirmé deux builds FR octet pour octet identiques, puis
  586 tests ROM réussis et 38 ignorés. Son unique échec initial, un replay
  émulateur italien n’ayant pas détecté le premier combat sans constater de
  gel, a réussi immédiatement lors de sa relance isolée.

# Issue #180 — « Anc. Sav. » → « Précéd. »

## Diagnostic et conception

- L’écran de sauvegarde lit l’entrée FR active unique `0x1F11DA3`, équivalente
  à l’anglais « Old Save » et immédiatement suivie de la région date/heure
  gérée par `languages/fr/patches/time_format.py`.
- La correction retenue remplace chirurgicalement la source par « Précéd. » et
  la protège dans `languages/fr/protected_entries.yaml`. Elle tient dans le
  slot anglais de huit glyphes et ne nécessite ni relocalisation ni patch
  binaire dédié.
- Les alternatives écartées sont un patch post-build, qui dupliquerait la
  source de vérité, et une modification du patch date/heure, qui toucherait une
  région voisine sans être responsable du libellé.

## Plan validé

- [x] Ajouter la garde de régression et constater son échec sur « Anc. Sav. ».
- [x] Remplacer uniquement la dernière entrée active `0x1F11DA3` par « Précéd. ».
- [ ] Vérifier la garde, committer les sources avant le build et relire le diff.
- [ ] Régénérer les données FR, reconstruire la ROM et décoder le slot livré.
- [ ] Exécuter les validations, compléter la revue et intégrer sans push.
- [ ] Commenter puis clôturer l’issue GitHub avec l’état `completed`.

## Revue

- À compléter après les preuves source, tests et ROM.
