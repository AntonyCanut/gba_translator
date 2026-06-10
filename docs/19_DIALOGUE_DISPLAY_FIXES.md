# 19 — Correctifs d'affichage des dialogues FR

Trois défauts d'affichage observés en jeu (captures du ticket « Traduction
du jeu ») et leurs correctifs dans le pipeline `make build-fr`.

## 1. Glyphe d'argument : une lettre mangée après `{PAUSE}`

**Symptôme** — `…tu veux… / entir ma propre colère.` (le « s » de
« sentir » manquait).

**Cause** — Les placeholders `{PAUSE}`, `{DPAD_…}` etc. sont remplacés
par la séquence de contrôle de l'anglais (ex. `FC 08 20`). L'extraction
décode l'octet d'argument (0x20) comme un glyphe (`î`) que le traducteur
recopie après le placeholder ; ce doublon doit être consommé. L'ancien
code sautait `len(seq) - 1` caractères alphanumériques — or l'octet de
commande (0x08) n'apparaît jamais comme glyphe, donc le saut débordait
d'un caractère et avalait la première lettre du mot suivant.

**Correctif** — `_argument_glyphs()` calcule les glyphes réellement
émis par le décodeur pour les octets d'argument (commande exclue) et
`_skip_argument_glyphs()` ne consomme que les caractères qui leur
correspondent (avec repli sans accent : `î` ↔ `i`). Implémenté à
l'identique dans `src/translators/19_build_translated_rom_generic.py`
et `scripts/apply_inline_overrides_fr.py`.

## 2. Sauts de ligne hérités de l'anglais

**Symptôme** — `Et` seul sur la première ligne, deuxième ligne
débordante ; nom du joueur coupé au bord de la boîte (« …l'équipe de
Fra▌», un nom peut faire 9 caractères).

**Cause** — Les positions de `\n` venaient du texte anglais, plus
court. Aucun re-wrap n'existait dans ce pipeline.

**Correctif** — `src/core/dialogue_linewrap.py` :

- métriques réelles de la police FRLG (`sFontNormalLatinGlyphWidths`
  de pret/pokefirered), indexées par octet charmap ;
- les buffers `<0xFD><0xNN>` (nom du joueur, espèce…) comptent 54 px
  (9 caractères) pour que les lignes à nom ne débordent pas ;
- répartition des mots par programmation dynamique sur le même nombre
  de lignes (boîte utile : 192 px), avec ajout de lignes seulement si
  le contenu ne peut pas tenir ;
- règle Gen III appliquée en sortie : un seul `\n` par fenêtre, puis
  `<0xFA>` (scroll) jusqu'au `<0xFB>` (page) qui vide la boîte.

Appliqué aux entrées de catégorie `dialogue` par le builder
(`_normalize_translation_item`) et par `apply_inline_overrides_fr.py`.
Déplacer un saut est neutre en octets ; un saut ajouté coûte 1 octet,
absorbé par la relocalisation.

## 3. Tables de noms à cellules fixes écrasées

**Symptôme** — En combat : `Terhal used hargeurPlaquage!` (deux noms
d'attaques fusionnés, première lettre perdue).

**Cause** — Les tables à pas fixe (noms d'attaques : cellules de
13 octets `nom + 0xFF + zéros`) sont vues par l'extracteur comme des
chaînes plates : le padding de la cellule précédente devient des
espaces de tête de l'entrée suivante. Réécrire une traduction à cet
offset supprime le padding, décale le nom hors de sa cellule et écrase
le terminateur voisin. De plus, ces tables sont **déjà en français**
dans la ROM source — le traducteur re-traduisait des noms français
(« Charge » → « Chargeur »).

**Correctif** — `src/core/fixed_tables.py` liste les plages protégées
(noms d'attaques 0x1B2980–0x1B56E6, structs espèces/catégories Pokédex
0x1A35800–0x1A3ABB0, noms d'espèces 0x166A981–0x166E126), vérifiées
structurellement contre la ROM source. Le builder
(`_prepare_translations`, stat `skipped_fixed_table`) et le passage
inline les ignorent : la ROM construite garde les octets source.

## Données corrigées

`combined_fr.txt` contenait aussi des traductions tronquées en plein
milieu de phrase (ex. `Le {STR_VAR_1} a rejoint l'équipe de` sans le
nom du joueur, « …veulent nous » sans « rejoindre ! »). Les lignes
identifiées (balayage mots-outils en fin de ligne / avant `\p`) ont été
complétées ; les fiches Pokédex dont la source était déjà en français
complet ont été remises au texte source. Voir
`worktask/truncation_candidates.json` / `worktask/truncation_fixes.json`.

## Vérification

- `tests/test_dialogue_linewrap.py`, `tests/test_fixed_table_protection.py`,
  `tests/test_control_placeholders.py` (cas de régression « sentir »).
- Après `make build-fr`, vérifié au niveau octets dans la ROM :
  table des attaques identique à la source, `FC 08 20` suivi de
  « sentir », lignes rééquilibrées, chaîne d'équipe avec les deux
  buffers, gabarit de combat « <0xFD><0x02> utilise <0xFD><0x03> ! »
  repointé.
