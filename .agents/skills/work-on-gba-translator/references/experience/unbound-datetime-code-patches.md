---
name: unbound-datetime-code-patches
description: "Les formats date/heure d'Unbound sont du code Thumb + gabarits FD patchés post-build par patch_time_format_fr.py ; la sonde mGBA ne doit JAMAIS sauvegarder en jeu (écrase la fixture .sav)"
metadata:
  node_type: memory
  type: project
  originSessionId: 54b66bad-8c24-438d-b434-db04c763f7b9
---

Les affichages date/heure de Pokémon Unbound (écran de sauvegarde, horloge du menu START, plages horaires scriptées, carte dresseur) sont composés par du **code Thumb** + des gabarits texte à jetons FD, hors de portée du pipeline de traduction (voir [[unbound-fr-build-lives-in-gba-translator]]). `scripts/patch_time_format_fr.py` (étape `build-fr`, après `patch_fixed_table_names.py`) applique 22 patchs à octets attendus, idempotents : conversions 12 h neutralisées (`bls`→`b` à 0x1EB5F12, 0xA0B534+0xA0B52E, 0x1ECC16A/182), heures à zéros de tête (`movs r2,#2`), gabarit sauvegarde réécrit `JJ/MM/AAAA HH:MM` (région 0x1F11DAC ré-agencée car « Jamais » > « Never » d'un octet → pointeur du gabarit re-visé dans le pool 0x1EB6260), horloge `Jjj. HH:MM`, jours `Dim..Sam` (cellules 4 octets à 0xA4E554), mois iso-longueur (table 0x1F81E9E), « AM »/« PM » suffixes vidés.

**Why:** Demande utilisateur juin 2026 (T-62) : la sauvegarde affichait « 2026/06/12 5:00 PM » au format anglais. Vérifié en jeu : menu « Ven. 16:52 », boîte « Anc. Sav. 12/06/2026 17:00 ».

**How to apply:** (1) Pour toute chaîne système introuvable dans l'extraction, chercher ses pointeurs dans les pools littéraux (valeurs 0x09xxxxxx = base 0x08000000 + offset) puis désassembler avec capstone (`pip install capstone`, mode THUMB) — les fonctions CFRU vivent vers 0x1EB-0x1EC-0xA0B. (2) Si la traduction est plus longue que le slot ET que la chaîne n'a qu'un pointeur, ré-agencer la région et patcher le pointeur du pool. (3) PIÈGE sonde : sauvegarder EN JEU via probe_drive écrase `output/roms/GenedRom-fr.sav` (fixture trackée = intro du jeu) → les goldens visuels Playwright (continue/no-battle) divergent ; faire `git checkout -- output/roms/GenedRom-fr.sav` avant les e2e. (4) Les savestates mGBA restaurent la RAM : la date de dernière sauvegarde vient du saveblock RAM, donc après `load<slot>` elle affiche « Jamais » même si la flash contient une save. (5) Reste connu : la Carte Dresseur compose « Juin 11, 2026 » (mois+jour+virgule+année par StringAppend successifs avec loads pc-relatifs — réordonner = chirurgie risquée, laissé tel quel).
