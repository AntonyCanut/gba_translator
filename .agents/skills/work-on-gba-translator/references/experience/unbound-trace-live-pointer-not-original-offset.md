---
name: unbound-trace-live-pointer-not-original-offset
description: "Avant de classer un offset combined_fr.txt comme \"encore en anglais\", tracer la chaîne de pointeurs vivante, pas juste décoder l'offset original"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 7f67dcbb-f14b-4c00-a6c8-5042c1207b5d
---

Un offset signalé "too_long"/"reste en anglais" dans translation_ready.json peut déjà être corrigé : la passe générique (`--allow-relocate`) relocalise le texte FR ailleurs et repointe la cellule pointeur vivante, mais l'offset original (mort) continue de décoder en anglais puisque plus rien ne le référence. Décoder l'offset littéral donne donc un faux positif.

**Why:** Sur B-98 (3 dialogues Cube V3/Mission télévision), 2 des 3 offsets signalés (0x1F01074, 0x1FB052C) étaient déjà entièrement migrés — leur unique référent EN avait été repointé vers une copie FR en espace libre. Seul 0x1FB07FE avait un second référent (après un opcode non reconnu par `_plausible_pointer_sites` dans `src/core/text_reinserter.py`) resté sur l'original anglais. Diagnostiquer correctement a évité de retraduire/raccourcir du texte déjà bon et a ciblé le vrai bug (1 référent sur 2 non repointé).

**How to apply:** Pour tout offset suspect, chercher TOUS les référents 4 octets LE `0x08000000+offset` dans le ROM EN (référents légitimes) puis dans le ROM FR construit. Si zéro référent reste dans le FR vers l'offset original → déjà migré, ne rien faire (tracer plutôt le nouveau pointeur pour confirmer le texte FR). Si un référent EN n'apparaît plus dans la liste des référents du FR repointé alors qu'un autre référent EN existe toujours sur l'original → repointage partiel, c'est le vrai bug à corriger (cf. [[unbound-long-dialogue-extractor-cap]] pour le pattern de patch dédié reference-driven + idempotent).
