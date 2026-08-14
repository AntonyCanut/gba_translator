# Parité DE des graphismes de menus et du monde

Ce groupe porte les extractions FR hors combat vers le build allemand. Les
images allemandes restent des PNG indexés 4 bpp sous
`languages/de/sprites/`; les indices de palette sont les octets réellement
réinjectés. La palette ROM, les tilemaps et les tuiles voisines ne sont pas
modifiées.

| Asset FR de référence | Équivalent DE | Bloc(s) / budget | Livraison |
|---|---|---|---|
| `cube_sort_hint` — « START Tri » | « START Sort. » | LZ77 `0xEF1B68`, 13×4 tuiles, 647 octets recompressés maximum | `menu_sprites`, après les deux réparations LZ77 |
| `pc_box_labels` | `PKMN DATEN`, `TEAM PKMN`, `ZURUECK`, `BOX ZU` | LZ77 `0xE9C438`, pointeur connu `0x8F034`, 16×9 tuiles | insertion avec relocalisation limitée au pointeur déclaré |
| `pokemon_mart_sign` | `SHOP` | `0x7559B8`, `0xB89D5C`, `0xCF91A0`; fenêtres 16×8; capacités 10 452 / 10 531 / 11 604 | trois PNG/copies indépendants |
| `selection` | `ZUR.`, `B TASTE`, `GROSS`, `KLEIN`, `ANDERE` | brut `0xE985D8`, 5×13 tuiles | indices écrits directement, sans compression |
| `start_menu_move_hint` — « SELECT Dépl. » | « SELECT BEW. » | LZ77 `0xB1BBE0`, 15×1 tuiles, 263 octets maximum | compression VRAM-safe |
| Labels fixes carte | noms propres EN originaux | `0xB500A0`, `0xB535C8` | copie tardive depuis la ROM source immuable |
| Actions carte | `Bew.`, `OK`, `Zurück` | `0x418E77`, `0x418E95`, `0x418E9E` + 4 pointeurs connus | patch CFRU idempotent, vrai glyphe `ü` |
| Panneaux de jonction | texte DE, noms propres fournis par `combined_de.txt` | 10 cibles `0x1F70E41`–`0x1F72808` | wrapper DE existant, relocalisation/repointage tardifs |
| En-têtes DexNav | `SUCHLEVEL`, `METHODE`, `VERST. FAEH.`, `ITEMS` | LZ77 `0xB14FA0`, plafond strict 1 176 octets | patch DE existant + effacement conditionnel `GHOST_TILES` |

## Ordre du build

`repair_lz77` puis `repair_localized_lz77` précèdent obligatoirement
`menu_sprites`, la police DE et les autres patches graphiques. Les labels et
actions de carte passent après les relocalisations générales, juste avant les
deux allocateurs finaux des missions et panneaux de jonction. Ainsi, aucune
réparation ne peut remettre l'art anglais et aucun repoint tardif ne peut
réactiver une cellule périmée.

## Vérification

`tests/unit/de/test_menu_graphics_assets.py` contrôle dimensions, indices,
absence des grilles françaises, insertion réelle, compression et idempotence.
Il extrait aussi chaque copie de `GenedRom-de.gba` pour la comparer au PNG
versionné. `tests/unit/de/test_world_map_graphics.py` verrouille octets CFRU,
pointeurs et noms propres. Les tests DexNav existants restent l'autorité pour
le plafond LZ77 et les pixels fantômes.
