---
name: unbound-hall-of-fame-boards-english
description: "Les panneaux Hall of Fame d'Unbound (City Pokémon Gym Leader: Name / Winning Trainers) restent en anglais, injoignables par le scan de pointeurs"
metadata:
  node_type: memory
  type: project
  originSessionId: fb7fd2c4-263f-449c-b43c-b01ad094b062
---

Les panneaux Hall of Fame / cartes de Champions d'Unbound (~38 occurrences en ROM, ex.
offsets 0x74593B, 0x7E7128, 0x764E69, blocs 0x1F1Exxxx/0x1F70xxxx) affichent en jeu un
gabarit **anglais** : `<Ville> Pokémon Gym\nLeader: <Nom>\pWinning Trainers: ...` —
seul « Pokémon » est accentué, le reste (Gym, Leader, Winning Trainers, noms de villes
type « Dresco Town ») reste EN.

combined_fr.txt CONTIENT des versions FR pour certains (ex. 0x74593B « Champion d'Arène
de Dresco… Entraîneurs gagnants ») mais elles n'atteignent PAS la ROM : ces offsets sont
« missing in English extraction » dans le scan de pointeurs (`pointer_text_extractor.py
--scan-all-pointers`), donc `apply_combined_fr.py --extend` les saute (pas de padding/max
length) et ils n'entrent jamais dans le JSON ni la ROM. Famille des [[unbound-pipeline-unreachable-name-cells]].

Conséquence pour les tickets texte : corriger le combined_fr (source de vérité) est
correct mais ne suffit pas — ces panneaux nécessiteraient un patch table dédié type
[[unbound-pipeline-unreachable-name-cells]] (patch_fixed_table_names.py). Traduire le
Hall of Fame complet = chantier séparé, hors scope d'un fix « gym→arène » de dialogues.

LEÇON build : `make build-fr` exécute TOUTE la chaîne de patches post-build (gendered
buffers, font, pokedex, dates, **status badges**, type icons, shop…). Une sortie tronquée
par `tail` ≠ échec ; vérifier EXIT et la dernière ligne (`25 passed` du check
location_names). Un ROM buildé via `19_build...` SEUL (sans les patches) casse les tests
-m rom (ex. test badge KO).
