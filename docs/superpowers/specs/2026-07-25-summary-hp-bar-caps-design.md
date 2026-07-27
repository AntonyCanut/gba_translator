# Barre de vie de la page Capacités — conception

## Contexte

L’issue #84 signalait une barre de vie « effacée ». Les deux passes précédentes
ont travaillé sur le libellé « PV » du **menu Pokémon** (bloc LZ77 `0x008001D0`),
dont le cap gauche était déjà intact : les colonnes 14-15 n’ont jamais été
dessinées par le patch. Le rapporteur a ensuite précisé le symptôme — « la barre
de vie n’est toujours pas correcte dans le **deuxième onglet du statut** d’un
Pokémon […] tronquée sur les deux extrémités » — et joint une comparaison
anglais / français.

## Cause racine

La page « Capacités Pokémon » dessine sa barre avec la planche LZ77
`0x00E9B4B8` (12 tuiles) :

| tuiles | rôle |
| --- | --- |
| 0-8 | corps de barre, une tuile par niveau de remplissage (5 rangées) |
| 9-10 | libellé « HP » **et** cap gauche de la barre (tuile 10, colonne 7) |
| 11 | cap droit de la barre (colonne 0) |

`scripts/repair_localized_lz77_blocks.py` copie la planche **espagnole** entière
dans le build FR. Or la planche ES a un corps de 7 rangées et une tuile 11
entièrement vide : les deux caps disparaissent. `_draw_green_label` remettait
ensuite les tuiles 9-10 à zéro avant d’y écrire « PV », ce qui effaçait aussi le
cap gauche resté dans la tuile 10.

## Conception retenue

`languages/fr/patches/hp_labels.py` restaure la planche **anglaise** en entier,
puis repeint uniquement les lettres dans la boîte 6×14 qu’occupait « HP ». Les
colonnes 14-15 de cette boîte — le cap gauche — ne sont jamais écrites, et les
tuiles 0-8 et 11 redeviennent identiques à l’anglais.

Le glyphe « PV » adopte la géométrie anglaise (4 rangées de remplissage,
contour généré par `_outline`), au lieu de la géométrie espagnole à 7 rangées
qui ne rentre pas dans une barre de 5 rangées.

Le flux recompressé passe de 146 à 153 octets. Le bloc dispose d’un créneau de
192 octets (`0x08E9B578` est l’adresse pointée suivante et rien ne pointe à
l’intérieur du flux), donc `_recompress_in_place` accepte désormais une borne
de créneau explicite au lieu de la seule règle « tail de padding ».

## Vérification

Trois niveaux, du moins au plus probant :

1. **Unitaire** — l’art produit est comparé à l’art anglais tuile par tuile, et
   la ROM construite est comparée à `input/roms/englishrom.gba` sur les tuiles
   de barre et de caps.
2. **E2E de référence** — `tests/e2e-playwright/specs/hp-bar.spec.ts` pilote
   mGBA depuis la sauvegarde du rapporteur jusqu’à la page Capacités, dans la
   ROM anglaise **et dans les trois builds traduits** (FR, DE, IT), puis exige
   que la bande de la barre (x 81-131, y 29-35) soit identique au pixel près.
   Le menu Pokémon traversé en chemin est capturé aussi : ses six bandes de
   barre (planche `0x008001D0`) subissent la même comparaison. La référence
   n’est donc pas un golden issu d’un build traduit, qui ne prouverait que sa
   propre reproductibilité.
3. **Contrôle négatif** — `scripts/regress_summary_hp_bar.py` réinjecte la
   planche espagnole et efface le cap gauche du menu Pokémon dans une copie
   jetable, et le scénario exige que les mêmes comparaisons échouent, pour
   chacune des trois langues. Sans lui, les tests de parité pourraient passer
   par construction.

La page est reconnue par la colonne des libellés de stats (ATTACK, DEFENSE, …),
des word-images identiques dans toutes les langues et disjointes de la barre :
l’écran est donc identifié par des pixels que le correctif ne peut pas influencer.

### Ne comparer que ce qui tient en place

Le reste du menu Pokémon n’est pas comparable d’un build à l’autre : les noms
d’espèces sont traduits et les icônes de Pokémon s’animent. Un golden plein
écran de cette page est donc à la fois spécifique à une langue et instable
d’une exécution à l’autre — c’est ce qui a rendu rouge l’ancien scénario au
premier rebuild. Seules les six bandes de barre, des tuiles BG immobiles, sont
comparées.

### Attendre l’écran, pas un nombre de frames

Attendre un nombre fixe de frames après le chargement de la partie ne suffit
pas : le rappel de quête qui s’affiche par-dessus l’overworld n’apparaît pas à
la même frame selon le build, et un `START` avalé par cette boîte laisse le
probe appuyer sur `A` devant un panneau — c’est exactement ainsi que la ROM
allemande échouait. Chaque transition attend donc que le framebuffer cesse de
bouger.

« Cesser de bouger » ne peut pas vouloir dire « deux captures identiques » : le
menu principal affiche une horloge vivante et un curseur clignotant. Mesuré sur
les builds EN, FR et DE, ce bruit de fond reste sous 0,7 % de l’écran alors
qu’une vraie transition en déplace 1,5 % (ouverture du menu) à 7 % (apparition
du rappel de quête) — d’où le seuil à 1 %, et deux intervalles calmes
consécutifs exigés pour qu’un instant de calme fortuit pendant une transition
ne soit pas pris pour la fin de celle-ci.

## Erreurs et bornes

- L’exploration du menu principal s’arrête à quatre entrées : la cinquième est
  « Sauvegarder » et écrirait réellement la sauvegarde.
- La sauvegarde versionnée est copiée dans un sandbox supprimé en `finally`, et
  son SHA-256 est contrôlé avant et après la campagne.
- Si la page n’est jamais reconnue, le probe lève une erreur explicite plutôt
  que de comparer un écran arbitraire.

## Allemand et italien

Les builds DE et IT copient la même planche espagnole et souffraient du même
défaut. Le correctif a été porté par le ticket B-557 (commits `5d1fb2b3` et
`432fd9ed`), qui n'a pas dupliqué la validation E2E. Elle l'est ici : le même
scénario pilote les trois builds traduits, chacun avec son contrôle négatif.

La sauvegarde du rapporteur suffit pour les trois : les trois ROMs sont
construites depuis `input/roms/englishrom.gba`, donc la même sauvegarde batterie
se charge dans chacune — y compris dans la ROM anglaise de référence.

Les ROMs DE et IT sont des artefacts de build non versionnés : le scénario
échoue avec un message explicite (« lancer `make build-de` ») plutôt que de
sauter silencieusement le cas.

## Verrouillage — ce qui empêche le défaut de revenir

La correction elle-même tient en quelques dizaines de pixels ; ce qui la
protège, ce sont les endroits où une modification anodine la déferait. Chacun
a désormais son verrou dans `tests/test_hp_bar_locks.py`, et chaque verrou a
été éprouvé en cassant volontairement ce qu'il garde.

| Ce qui peut défaire le correctif | Verrou |
| --- | --- |
| `hp_labels` repasse avant `repair_localized_lz77` (Makefile ou `lang.yaml`) | ordre d'étapes comparé dans la recette `build-fr` et dans les listes `patches:` DE/IT |
| L'art anglais de référence est corrigé dans une seule langue | les trois `GREEN_EN_TILES` doivent rester identiques |
| Un tracé de libellé mord sur le cap | colonnes 14-15 du menu Pokémon et colonne 7 de la tuile 10 comparées avant/après tracé, dans les trois langues |
| La planche recompressée dépasse son créneau (patch ignoré en silence) | taille LZ77 vérifiée par langue |
| Une ROM livrée n'est plus celle qu'on croit | tuiles 0-8, 11 et cap gauche comparées à `englishrom.gba` dans les trois ROMs |
| `regress_summary_hp_bar.py` cesse d'abîmer quoi que ce soit | ROM synthétique : le script doit vider le cap droit, effacer le cap du menu, ne rien toucher d'autre, et le patch doit savoir réparer |
| Le scénario e2e est débranché (commande npm, config, ancre, sauvegarde) | commande, config, ancre 56×72 et SHA-256 de la sauvegarde contrôlés au tier rapide |

Deux angles morts du scénario e2e sont aussi refermés :

- une capture qui n'aurait jamais atteint la page serait noire, et deux zones
  noires sont pixel-identiques — chaque barre doit donc porter plusieurs
  couleurs distinctes avant qu'une comparaison de parité ne compte ;
- les lettres du libellé sont volontairement exclues des zones comparées, donc
  une ROM embarquant la planche anglaise entière (barre correcte, libellé
  « HP ») passerait tout le reste : la zone du libellé doit différer de la
  capture anglaise. Vérifié en pointant le cas français sur `englishrom.gba` —
  le test échoue bien.

Chaque build n'est piloté qu'une fois dans mGBA ; ses quatre cas partagent la
même capture, donc les nouveaux contrôles ne coûtent aucune exécution
supplémentaire.
