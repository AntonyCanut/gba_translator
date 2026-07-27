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
- [ ] Relire, committer, intégrer localement et clôturer l’issue.

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
- [ ] Relire le diff, committer et clôturer l’issue GitHub.

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
- [ ] Reconstruire la ROM FR et vérifier les octets pointés.
- [ ] Exécuter les validations post-build et intégrer le commit.

## Revue

- À compléter après la reconstruction et les validations finales.
