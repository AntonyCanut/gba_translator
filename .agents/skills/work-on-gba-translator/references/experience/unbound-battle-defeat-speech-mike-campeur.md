---
name: unbound-battle-defeat-speech-mike-campeur
description: Réplique de défaite dresseur en combat affichait « Mike Campeur » (nom+classe) — STRINGID 0 gBattleStringsTable corrompu par le pipeline
metadata:
  node_type: memory
  type: project
  originSessionId: 255f1731-9802-4b52-a458-c7388eaebbcd
---

B-78 : à la victoire d'un combat dresseur, le message in-combat « Tu as battu X »
était suivi d'un « **Mike Campeur** » (nom du dresseur + une classe sans rapport
« Campeur »), qui **flashait sans attente bouton**. Ce N'EST PAS la ligne de
victoire (0x3FD1C7, qui marche et attend via FC09 — voir [[unbound-battle-end-message-fc09-over-timed]]).

**Vrai bug** : c'est la *réplique de défaite en combat* = `gBattleStringsTable[0]`
(STRINGID 0), body à offset FIXE **0x3FB219** (pointeur table 0x3FDF3C = 0x083FB219,
jamais repointé). Body EN = template de code de contrôle **`{FD24}` = `fd24ff`**
(imprime la lose-text chargée → EN « I ran out of energy to fight! », FR « Plus
d'énergie pour me battre ! »). Le pipeline FR mis-encode ce token :
`09_csv_to_json_v2.py` sort `{FD24}`→`<0xFD><0x1D>` (FD1D = NOM dresseur) et
`{FD25}`→FD1D, laisse `{FD2E}`/`{FD2F}` en littéral. Injecté en place sur le
cluster compact 0x3FB219..0x3FB264 (templates + chaînes de rappel « come back! »),
ça déborde et décale tout → STRINGID 0 lit `{FD1D} {FD2E}` = nom+classe = « Mike
Campeur » (« Campeur » = cellule classe 0x23E871 de gTrainerClassNames). ES reste
byte-intact (« regresa. » tient) → preuve débordement FR en place.

**Fix** = class-3 post-build `patch_battle_string_templates_fr.py` (wired dans
`make build-fr` après patch_status_abbrevs) : restaure les octets EN du cluster
0x3FB219..0x3FB264 (templates neutres en langue). STRINGID 0 redevient `{FD24}`.
Test `tests/e2e/test_battle_defeat_speech_template_fr.py`. Commits c46bfab+6b09668.

**Méthodo qui a marché** (les 2 passes précédentes ont échoué en raisonnant
octets sans jouer) : driver le combat headless via la save fournie placée en
`<rom>.sav` + lire/décoder `gDisplayedStringBattle` **0x0202298C** image par image
(probe_b78_victory.mts). Comparer séquence EN vs FR de fin de combat. Tenir sans
input pour distinguer attente (FC09, reste) vs flash (auto-avance). Bug PRÉ-EXISTANT
(aussi dans data/frenchrom.gba Jun 22), pas une régression du rebuild.

**Reste à faire (R-10)** : corriger l'encodeur `{FDxx}` du pipeline + traduire les
rappels « {classe} {nom} : {Pokémon}, come back! » (0x3FB21F/35/48) revenus en
anglais, via relocate+repoint. Voir [[unbound-hooh-lugia-ritual-repointer-corruption]]
(même famille : pipeline qui corrompt des pointeurs/templates de combat).
