---
name: unbound-item-pickup-present-tense-fixed-silent-overflow
description: "Passage \"a rangé\"→\"range\" (présent) du message de ramassage d'objet (#64) a aussi réparé un overflow silencieux du template générique"
metadata:
  node_type: memory
  type: project
  originSessionId: bba74b78-06da-46aa-b8ba-5d5000cefe90
---

Le template générique de ramassage d'objet (`{PLAYER} a rangé {STR_VAR_2}\ndans la {STR_VAR_3}.`,
vivant à l'offset relogé `0x1A5218`, référencé par 8 pointeurs stables dont les slots
`0x1A6752/0x1A681A/0x1A689F/0x1A8D75/0x1A8E68/0x9A483E/0x9A48AB/0x9A4910`) était **trop long
pour tenir en place** avec « a rangé » : `apply_combined_fr.py`/le build engine retombait
silencieusement sur le texte anglais (« put the … in the … ») malgré une entrée FR valide dans
`combined_fr.txt` — piège identique à [[unbound-trace-live-pointer-not-original-offset]] et
[[unbound-item-name-putaway-message-width]] (deux contraintes de largeur, jamais visible en
lisant juste le fichier source).

Le fix demandé par l'issue #64 (passer au présent, comme les jeux officiels : « range » au lieu
de « a rangé ») a raccourci la chaîne de 2 caractères, ce qui l'a fait rentrer dans le budget —
corrigeant à la fois la formulation ET un bug latent d'affichage anglais. Trois offsets touchés
dans `combined_fr.txt` (bloc haut, pas de doublon) : `0x183387` (démo Potion, no-pointer
in-place), `0x1A5218` (template générique), `0x1A526C` (Boîte Jetons, vivant via slots
`0x1A690C`/`0x1E6F4A0`).

Méthode de vérification utilisée (généralisable) : décoder l'octet réellement injecté à l'ancien
ROM committé (`git show <sha>:output/roms/GenedRom-fr.gba`) ET au nouveau build, PUIS scanner le
ROM pour les 4 octets LE de l'adresse GBA (`offset+0x08000000`) afin de retrouver les slots de
pointeur vivants — une chaîne peut apparaître à plusieurs offsets identiques dans le fichier
(copie morte + copie active relogée), seul le comptage de pointeurs qui la référencent tranche.
Test de régression ajouté : `tests/test_regression_texts.py::test_item_pickup_message_uses_present_tense`
(lit les pointeurs vivants, pas les offsets bruts).

Rebuild FR change ~380k octets malgré 3 lignes modifiées : normal, la cascade de relocalisation
repack tout le ROM en aval dès qu'une longueur change (voir [[unbound-build-determinism-relocation-order]]).
Pas un signal d'alerte tant que `make test-rom` (144) + suite rapide (1432) + `check_translation_integrity.py`
restent verts.
