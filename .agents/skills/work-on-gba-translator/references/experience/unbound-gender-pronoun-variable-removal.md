---
name: unbound-gender-pronoun-variable-removal
description: "Comment supprimer une variable de genre (il/elle) d'un dialogue FR — mapping positionnel du build sur l'ordre des codes anglais"
metadata:
  node_type: memory
  type: project
  originSessionId: 6a3a34fc-a09a-4d7b-97b3-73e48d690b14
---

Pour retirer une **variable de genre joueur** (`{STR_VAR_2}` = `<0xFD><0x03>`, que le
moteur remplit par le pronom il/elle) d'un dialogue : on NE PEUT PAS juste renommer/effacer
le token, car le mapping est **positionnel sur l'ordre des codes de contrôle ANGLAIS**, pas
par nom. Voir [[gba-translator-token-pipeline-pitfalls]].

**Cas résolu (ticket « Cohérence dialogue ») :** discours Aklove/Hoopa, 2 variantes
`0x1F3A6F8` (« En réalité, Hoopa… ») et `0x7D4DD8` (« Aklove : En fait… »). Rendu fautif
« Une fois il parti, Hoopa devra m'accepter, MOI… ». `patch_gendered_buffers_fr.py` note
lui-même : « she/She → elle/Elle ne rentre pas ; laissé tel quel » → le buffer pronom sujet
est inrendable proprement en FR.

**Deux étages, deux comptages différents (piège) :**
- `scripts/apply_combined_fr.py` `_apply_placeholder_mapping` : ne se déclenche QUE si
  `nb {…} == nb <0xFD><0x..>` dans l'anglais (compte SEULEMENT les FD, pas les pauses FC ;
  compte `{COLOR}`/`{PAUSE}` comme slots). S'il se déclenche → zip positionnel BUGGÉ
  (transforme {PAUSE} en FD01, décale FD03). Donc garder `nb {…} ≠ nb FD` pour qu'il
  **no-op** (laisse les `{…}` littéraux).
- `src/translators/19_build_translated_rom_generic.py` `_apply_control_placeholders` : le
  vrai convertisseur. Extrait les séquences de contrôle de l'ANGLAIS dans l'ordre
  (FA/FB ignorés ; FC01xx=couleurs à part ; reste=`other_sequences`), puis remplace chaque
  `{…}` (sauf `{COLOR}`) en **popant** la séquence suivante. Le NOM du `{…}` est ignoré.
  Les séquences non consommées sont **droppées** (pas ajoutées).

**Recette pour faire disparaître un FD03 :** mettre MOINS de `{…}` que de codes anglais, et
placer le FD03 en position non consommée. Ex. `0x1F3A6F8` ordre anglais
`[FD01, pause, FD01, FD01, FD03]` (FD03 en dernier) → 3 placeholders `{PLAYER}{PAUSE}{PLAYER}`
mappent FD01/pause/FD01, droppent FD01#4 et FD03. `0x7D4DD8` ordre `[FD01, FD03, FD01, FD03]`
(FD03 en pos 2) → 1 seul `{PLAYER}` (+`{COLOR}`) mappe FD01, droppe le reste. Reformuler le
texte sans pronom : « je veux m'en débarrasser », « Une fois cela fait » (neutres).

**VÉRIFIER PAR OCTETS, pas par le JSON** (le JSON pré-build garde les `{…}` littéraux) :
build complet puis suivre la chaîne relocalisée (les 2 strings sont repointées en free space,
trouvées via recherche d'octets ex. « cela fait ») et compter `FD 03` = 0. Test source-level
ajouté : `tests/test_gender_neutral_aklove_fr.py`. Voir aussi [[unbound-gendered-buffer-strings]].

**Cas FD02 « him/her » en position OBJET (ticket « Dialogue Genre », 2026-06-22) :** table
des pronoms de genre joueur @ `0x789224` (`him`→`le`, `he`→`il`, `her/she`→`elle`,
`He/She`→`Il/Elle`). En anglais le script bufferise ce pronom comme objet 3e personne
(« finishing <FD02> off », « beat <FD02> »). **Discriminateur clé : seul l'OBJET est cassé**
— `him`→`le` orphelin après préposition/verbe (« en finir avec le », « battre le ») est
agrammatical ; mais le SUJET (`he/she`→`il/elle`) se rend correctement (« il/elle n'est pas
au courant ») → NE PAS toucher les sujets. L'ES neutralise (clitique « vencerle »). Détection
fiable : verbe/prép interpersonnel + buffer SANS article devant (sinon = nom d'objet/Pokémon —
NE PAS toucher, 253 faux positifs sinon). 4 corrigés : `0x1F329AE`/`0x1F3296E` (Zeph/Ivory,
le joueur présent → « toi »/« te battre »), `0x1FA6E9F` (sbire → « te frapper… tu vas
pleurer »), `0x1F45482` (possessif redondant : « son ami {STR_VAR_1} » → drop, « son ami »
suffit). **PIÈGE mapping : réduire une ligne à un SEUL `{COLOR}` quand l'anglais a 1 seul FD
fait DÉCLENCHER `_apply_placeholder_mapping` (nb placeholders == nb FD) → `{COLOR}` mappé sur
le buffer FD !** Parade : écrire la couleur en token brut `<0xFC><0x01><0x04>` (0 brace).
Test : `tests/test_gender_neutral_zeph_grunt_fr.py`.
