# Variables et codes de controle des textes

Ce document explique les variables dynamiques (ex: `<0xFD><0x01>`) et les
codes de controle que l'on voit dans les CSV et dans `combined_fr.txt`.

## Notation

- `<0xNN>` = octet brut dans la ROM.
- Une sequence `<0xFD><0xNN>` represente une variable dynamique injectee par
  le moteur (nom, valeur, item, etc).
- Dans `combined_fr.txt`, on utilise souvent des placeholders lisibles
  (`{PLAYER}`, `{STR_VAR_1}`, ...). Les scripts remplacent ces placeholders
  par les bytes originaux dans le meme ordre.

## Regles a respecter

- Ne jamais supprimer un `<0x..>` ou un placeholder `{...}`.
- Conserver l'ordre des variables et des codes.
- Si vous deplacez un placeholder, faites-le de facon coherente avec la phrase.

## Sauts de ligne / pages

- `\\n` -> saut de ligne (0xFE, gere par l'encodeur).
- `\\l` -> `<0xFA>` (retour a la ligne dans la meme boite).
- `\\p` -> `<0xFB>` (nouvelle page dans une boite suivante).

## Couleurs

- `<0xFC><0x01><0xNN>` = changement de couleur.
- Dans `combined_fr.txt`, on utilise `{COLOR}X` (X = lettre/byte d'origine).
  Exemple: `{COLOR}ÉTexte{COLOR}Ç`.
- Garder la meme lettre/byte que dans l'original (ne pas l'inventer).

## Variables dynamiques `<0xFD><0xNN>`

### Generales / scenario

| Code | Placeholder | Signification |
| --- | --- | --- |
| `<0xFD><0x01>` | `{PLAYER}` | Nom du joueur |
| `<0xFD><0x02>` | `{STR_VAR_1}` | Variable de script 1 |
| `<0xFD><0x03>` | `{STR_VAR_2}` | Variable de script 2 |
| `<0xFD><0x04>` | `{STR_VAR_3}` | Variable de script 3 |
| `<0xFD><0x05>` | `{KUN}` | Suffixe/honorifique (ex: `{PLAYER}{KUN}`) |
| `<0xFD><0x06>` | `{RIVAL}` | Nom du rival |
| `<0xFD><0x07>` | `{VERSION}` | Version/edition du jeu |
| `<0xFD><0x08>` | `{EVIL_TEAM}` | Nom de l'equipe antagoniste |
| `<0xFD><0x09>` | `{GOOD_TEAM}` | Nom de l'equipe alliee |
| `<0xFD><0x0A>` | `{EVIL_LEADER}` | Chef de l'equipe antagoniste |
| `<0xFD><0x0B>` | `{GOOD_LEADER}` | Chef de l'equipe alliee |
| `<0xFD><0x0C>` | `{EVIL_LEGENDARY}` | Nom du legendaire associe |

### Combat (B_*)

| Code | Placeholder | Signification |
| --- | --- | --- |
| `<0xFD><0x0F>` | `{B_ATK_NAME_WITH_PREFIX}` | Nom du Pokemon attaquant (avec prefixe) |
| `<0xFD><0x10>` | `{B_DEF_NAME_WITH_PREFIX}` | Nom du Pokemon defenseur (avec prefixe) |
| `<0xFD><0x11>` | `{B_EFF_NAME_WITH_PREFIX}` | Nom du Pokemon affecte (poison, etc) |
| `<0xFD><0x12>` | `{B_ACTIVE_NAME_WITH_PREFIX}` | Pokemon actif (contexte combat) |
| `<0xFD><0x13>` | `{B_SCR_ACTIVE_NAME_WITH_PREFIX}` | Pokemon "script actif" |
| `<0xFD><0x14>` | `{B_CURRENT_MOVE}` | Capacite en cours |
| `<0xFD><0x16>` | `{B_LAST_ITEM}` | Dernier objet utilise |
| `<0xFD><0x18>` | `{B_ATK_ABILITY}` | Talent du Pokemon attaquant |
| `<0xFD><0x19>` | `{B_DEF_ABILITY}` | Talent du Pokemon defenseur |
| `<0xFD><0x1A>` | `{B_SCR_ACTIVE_ABILITY}` | Talent du Pokemon "script actif" |

### Dresseurs / liaison

| Code | Placeholder | Signification |
| --- | --- | --- |
| `<0xFD><0x1C>` | `{B_TRAINER1_CLASS}` | Classe du dresseur |
| `<0xFD><0x1D>` | `{B_TRAINER1_NAME}` | Nom du dresseur |
| `<0xFD><0x1F>` | `{B_LINK_PARTNER_NAME}` | Nom du partenaire (link) |
| `<0xFD><0x20>` | `{B_LINK_OPPONENT1_NAME}` | Nom de l'adversaire 1 (link) |
| `<0xFD><0x21>` | `{B_LINK_OPPONENT2_NAME}` | Nom de l'adversaire 2 (link) |
| `<0xFD><0x2E>` | `{B_TRAINER2_LOSE_TEXT}` | Texte de defaite d'un dresseur |
| `<0xFD><0x2F>` | `{B_TRAINER2_WIN_TEXT}` | Texte de victoire d'un dresseur |

### Tampons generiques / inconnus

- `<0xFD><0x35>` a `<0xFD><0x3D>`, `<0xFD><0x77>` -> `{STRING}` (tampons texte generiques).
- Codes rares observes mais non identifies: `0x22`, `0x28`, `0x30`, `0x32`,
  `0x33`, `0x34`, `0x6B`, `0x80`, `0xAF`, `0xC6`, `0xF7`, `0xFA`.
  Garder ces codes tels quels.
- Si vous voyez `{UNKNOWN_STR}` ou `{FDxx}`, c'est une variable non identifiee.
  Ne la modifiez pas.

## Autres codes de controle frequents

- `<0xF7>` : variable dynamique contextuelle (ex: PC, resume, menus).
- `<0xF8><0xNN>` / `<0xF9><0xNN>` : icones de boutons/UX
  (A/B/Start/Select/DPAD, etc). Utiliser les placeholders `{A_BUTTON}`,
  `{B_BUTTON}`, `{START_BUTTON}`, `{DPAD_UP}`, ... si besoin.
- `<0xFC><0x08><0xNN>` : pause temporisee (payload = duree).
- `<0xFC><0x09>` : pause jusqu'a validation.
- Placeholders `{FONT_SMALL}`, `{FONT_NORMAL}`, `{FONT}`, `{HIGHLIGHT}`,
  `{SHADOW}`, `{CLEAR_TO}`, `{FILL_WINDOW}`, `{NAME_END}`, `{PLAY_SE}`,
  `{WAIT_SE}`, `{PLAY_BGM}`, `{PAUSE_MUSIC}`, `{RESUME_MUSIC}` sont des
  codes d'affichage ou audio. Ne pas les modifier.
