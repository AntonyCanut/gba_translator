---
name: unbound-naive-decode-control-code-artifact
description: "Décoder octet-par-octet sans respecter la taille des control codes FC/FD/F8/F9/F7 fabrique des lettres fantômes (ex. 'LLv.' au lieu de 'Lv.')"
metadata:
  node_type: memory
  type: project
  originSessionId: 76dbd478-f7f0-420f-abab-c822aa0d2372
---

En auditant l'issue #48 (« Lv » → « N. »), un décodage CFRU naïf (lookup CHARMAP octet par octet, sans consommer les octets d'argument des control codes) a fait apparaître un faux bug : la ligne d'en-tête de l'écran d'échange (Salle Union) semblait contenir `Nom{CLEAR_TO}Souhaité{CLEAR_TO}Offre{CLEAR_TO}LLv.` (double « L »).

**Cause** : `FC 13 XX` est une commande 3 octets (icône d'objet, voir `src/text/control_codes.py` `FC_SUBCOMMAND_SIZES`). Un décodeur qui ne connaît pas cette table lit `FC` comme marqueur isolé, puis décode l'octet suivant `0x13` normalement (charmap → `Û`), puis l'octet d'argument `0xC6` normalement aussi (charmap → `L`) — d'où le « L » fantôme collé devant le vrai « Lv. » qui suit.

**Comment appliquer** : pour tout script de vérification/décodage ad-hoc sur ce projet, utiliser `parse_control_code()` de `src/text/control_codes.py` (qui connaît `FC_SUBCOMMAND_SIZES`) plutôt qu'un lookup `CHARMAP` plat — sinon les diagnostics peuvent indiquer des bugs de traduction qui n'existent pas réellement dans le rendu en jeu. Le pipeline officiel (`src/core/text_codec.py` / extraction JSON) reproduit la même limitation dans ses champs `decoded_text` de debug — ne pas s'y fier pour juger si un octet est un vrai caractère affiché ou un argument de commande.

Voir aussi [[gba-translator-token-pipeline-pitfalls]], [[unbound-lv-level-abbreviation-fixes]].
