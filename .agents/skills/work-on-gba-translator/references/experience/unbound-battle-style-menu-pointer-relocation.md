---
name: unbound-battle-style-menu-pointer-relocation
description: "Vanilla Options 'Battle Style' cells (0x419DCC region: Shift/Set/Mono/Stereo) sont collées sans slack, MAIS référencées par 2 pointeurs 4-octets alignés chacune — repointables via allow-relocate, contrairement à la table CFRU custom 0x1f4dxx"
metadata:
  node_type: memory
  type: project
  originSessionId: 59aaac03-8ca9-4bbe-bce0-a87e6769937e
---

Menu Options vanilla FireRed (Text Speed/Battle Scene/**Battle Style**/Sound/Button
Mode/Frame, offsets `0x419DCC`-`0x419E5C`) est une région DIFFÉRENTE de la table custom
CFRU "Options de combat" (`0x1f4da6c`-`0x1f4e244`, voir [[unbound-battle-options-fixed-width-descriptions]]).
Le libellé FR "Mode de combat" (offset `0x419DEB`, EN "Battle Style") est PARTAGÉ entre
l'écran Options vanilla et l'onglet CFRU "Options de combat" (même pointeur, une seule
copie en ROM) — d'où la confusion possible entre les deux tables lors d'un audit.

**Cellules Shift(`0x419E2C`,6o)/Set(`0x419E32`,4o)/Mono(`0x419E36`) sont collées bord à
bord, zéro slack** (vérifié par décodage brut : Set commence exactement où Shift finit).
`prepare_fr_json.py` calcule `too_long = fr_length > original_length` strictement (pas de
padding réel), donc une trad plus longue que l'EN est marquée trop longue.

**MAIS ce n'est PAS un cul-de-sac comme la table CFRU** : ces cellules ont chacune
2 pointeurs 4 octets 4-byte-aligned vers elles dans `output/extracted/extracted_texts/
patchedfrenchrom_texts.json` (`pointer_offsets`), retrouvés par `19_build_translated_rom_generic.py`
via `_normalize_translation_item` → fallback `self.english_texts.get(offset)['pointer_offsets']`
même si `prepare_fr_json.py` ne les recopie pas dans le JSON de traduction. Avec
`--allow-relocate` (flag déjà utilisé par `make build-fr`), `_plausible_pointer_sites`
accepte tout site 4-byte-aligned automatiquement → la trad plus longue est repointée
vers un nouveau bloc libre, l'ancien offset garde le texte EN mort (orphelin, jamais lu).

**Piège de vérification** : décoder directement à l'offset ROM d'origine (`0x419E32`)
montre TOUJOURS l'ancien texte anglais mort, que la relocalisation ait réussi ou non —
il faut suivre le POINTEUR vivant (ex. `0x003CC348`) pour voir le texte réellement affiché
en jeu. Confondre les deux fait croire à un échec alors que le repointage a fonctionné.

Fix #73 : "Changer"→"Choix" (in-place, 5o==5o), "Set"→"Défini" (relocalisé, 6o>3o).
Description "Semi-alterné" (`0x1f4e012`, table CFRU, budget strict 36o) réécrite courte
("Change gratuit après K.O. sans nom.", 36o pile) car cette cellule-là N'A PAS de
pointer_offsets (no-pointer in-place, voir [[unbound-nopointer-inplace-budget]]) —
vraiment aucune marge possible là.

Voir aussi [[unbound-battle-options-fixed-width-descriptions]], [[unbound-nopointer-inplace-budget]],
[[unbound-worktree-generic-build-artifact-reuse]] (symlink `output/extracted` requis en
worktree ; `make prepare-fr` bypass la CSV absente, voir [[unbound-prepare-fr-bypasses-csv-step]]).
