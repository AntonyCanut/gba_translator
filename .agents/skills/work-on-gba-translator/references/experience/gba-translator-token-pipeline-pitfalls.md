---
name: gba-translator-token-pipeline-pitfalls
description: "Pièges du pipeline de placeholders gba_translator — remplacement positionnel, {LV}=glyphe 0x34, lettres {COLOR}, vérification consciente des relocations"
metadata:
  node_type: memory
  type: project
  originSessionId: ae6829c2-326b-4519-9899-a2195bf89066
---

Pipeline gba_translator (branche `unbound`), appris le 2026-06-11 (T-58) :

- Les `{tokens}` des traductions sont remplacés **positionnellement** par les séquences de contrôle de la chaîne anglaise (les noms comme `{B_DEF_ABILITY}` sont décoratifs). Une phrase française qui réordonne les buffers (possessif inversé) rend un texte faux : reformuler pour suivre l'ordre ROM.
- `0xFA`/`0xFB` (sauts) ne doivent jamais entrer dans la file de remplacement — corrigé dans `19_build_translated_rom_generic.py` et `apply_inline_overrides_fr.py`. Un token excédentaire reste littéral et s'encode en garbage `?TOKEN?`.
- `{LV}` = glyphe imprimable `<0x34>` (ligature « Lv. »), pas une séquence.
- Lettre après `{COLOR}` = glyphe du charmap FRLG international à l'octet d'argument : À=01 Á=02 Â=03 Ç=04 È=05 É=06 Ê=07 Ë=08. Les marqueurs excédentaires (colorisation purement française) doivent être des codes explicites `<0xFC><0x01><0xNN>`.
- **Vérifier une chaîne « encore anglaise » via ses pointeurs**, pas ses octets : `--allow-relocate` laisse l'original anglais mort sur place et repointe ailleurs (ex. Oui/Non relogé, 6/6 sites repointés). Le critère vivant = un pointeur FR pointe encore vers l'offset.
- Certaines entrées d'extraction englobent du bytecode de script décodé comme texte (préfixe `<0x5C>…` = trainerbattle) ; le rewrap collapse leurs « espaces » (octets 00/FE) et décale le script. Ré-ancrer l'entrée au vrai début du texte (un pointeur de script le vise directement).
- Élision pronom : buffer précédé d'apostrophe (`qu'<0xFD><0xNN>`) = toujours il/elle → largeur 22px (« elle ») dans [[unbound-fr-build-lives-in-gba-translator]] `dialogue_linewrap.py`, éligible au glouton.
- Tables à pas fixe (capacités MAJUSCULES, easy-chat, types) volontairement non traduites (`in_fixed_table`) ; cris Pokémon gardés en onomatopées.
- **`09_csv_to_json_v2.py` exige le CSV en argument explicite** (vérifié 2026-06-17) : son auto-détection cherche `*_translation_*.csv`, or `apply_combined_fr.py --extend` écrit `*_trilingual_translation.csv` (ne matche PAS le glob). Sans l'argument, il prend un CSV périmé et produit **0 traductions sans erreur** (`make build-fr` affiche alors « Traductions: 0 » puis échoue). Toujours lancer `python3 src/translators/09_csv_to_json_v2.py output/translation/<date>_trilingual_translation.csv --allow-too-long`.
- **Auto-commit concurrent** : un autre process commit le worktree gba_translator pendant le travail — mes fichiers se sont retrouvés empaquetés dans le commit d'un autre agent. Vérifier `git log` à la fin (le HEAD peut bouger) ; les changements sont committés même si le message ne décrit pas votre tâche.
- **Architecture à deux couches d'écriture (compris T-60, juin 2026)** : la passe inline (`apply_inline_overrides_fr.py` + combined_fr.txt) MIROITE le layout de la ROM espagnole — ~1 600 entrées combined ont pour offset une adresse de relocalisation ES (espace libre 0xFF dans la ROM EN !), et certains pointeurs FR sont copiés de l'ES. Le FreeSpaceAllocator du builder doit donc réserver tout octet peuplé dans la ROM ES (paramètre `reserved_rom`, commit a90e47b) — sinon il reloge des chaînes dans ces zones et la passe inline les écrase (la porte de la Base Ombre affichait la fin d'une description d'attaque « nche l'ennemi »). Corollaire : un pointeur copié d'ES vers une adresse ES non couverte par combined affiche du vide → ajouter une ligne combined à l'adresse ES (cas du mur fragile 0x199BB3). Détection : scanner les sites u32 EN≠FR dont la cible FR atterrit au milieu d'une chaîne (4 faux positifs binaires résiduels attendus).
