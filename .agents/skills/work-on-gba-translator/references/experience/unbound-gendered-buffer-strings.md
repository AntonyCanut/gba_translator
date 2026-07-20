---
name: unbound-gendered-buffer-strings
description: "Unbound insère son/daughter, he/she, boy/girl via des buffers script (opcode 85) ; le genre grammatical français impose des reformulations et le mapping placeholder est positionnel"
metadata:
  node_type: memory
  type: project
  originSessionId: 58c1883d-aa2f-4f05-92d5-ec158647bb30
---

Pokémon Unbound sélectionne le genre du joueur via des petites chaînes tampons insérées par bufferstring (opcode script `85 <id> <ptr>`, id 0→FD02/{STR_VAR_1}, 1→FD03, 2→FD04) ou par du code CFRU (pointeur en literal pool, ex. 0x0xCA748 → gStringVar1 0x02021CD0). Paires : son/daughter ×4 (0x417FCC/D0, 0x77F57B/7F, 0x7DE1E1/E5, 0x1F41B0E/12), grandson|son ×2 (quête tarte — non genrée, deux étapes), he/she, him/her, boy/girl. Traduites en juin 2026 : fils/fille, il/elle, le, petit-fils (commit gba_translator `1d1aa86`).

**Why:** Les 6 « son » étaient absents de la traduction (mot identique au possessif FR) → « Protège mon son » en jeu pour un joueur masculin (ticket « Traduction du jeu »).

**How to apply:**
- Le possessif FR s'accorde avec le nom : « mon {fille} » est faux. Dans les cadres avec mon/ton devant le buffer → « mon enfant » + genre porté par il/elle ; garder fils/fille seulement en apposition ou après préposition (« toi, fille d'Aros », « Bonjour, fils du légendaire Aros »). Jamais d'élision possible devant un buffer (« si il » → « si un jour il », « que il parte » → reformuler) ; attention aussi aux participes (« voulu(e) »).
- Les slots « son » (3+FF) n'ont AUCUN padding (daughter suit immédiatement) ; le PaddingDetector du CSV sur-estime (max=5) mais `text_reinserter.reinsert_text` re-clampe sur la ROM réelle et reloge via les pointeurs — sûr.
- PIÈGE : le mapping des placeholders `{...}` est POSITIONNEL deux fois : `apply_combined_fr._apply_placeholder_mapping` (seulement si nb {…} == nb tokens FD de l'anglais) puis `19_build…._replace_placeholders` (chaque {…} consomme la PROCHAINE séquence de contrôle EN, FB inclus !). Dès qu'on ajoute/supprime un placeholder, écrire des tokens BRUTS `<0xFD><0x03>`/`<0xFC><0x01><0x08>` dans combined_fr.txt au lieu de {STR_VAR_x}/{COLOR}.
- combined_fr.txt contient des DOUBLONS de casse (0x77F1E3 et 0x77f1e3) : la dernière ligne du fichier gagne (dict) — éditer les deux.
- Tracer un consommateur de buffer : chercher `85 <id> <ptr little-endian>` autour du pointer_offset, puis les `0F 00 <ptr>` (loadpointer) voisins donnent le texte du cadre.

**MàJ 2026-06-24 (ticket « Variable de genre ») — préférence user : retirer le buffer PARTOUT, même en apposition.** L'utilisateur a vu « Il est logique que son fille suive ses traces. » (Prof. Log) et demande de supprimer la variable et d'écrire « enfant » totalement. Ceci ANNULE la règle « garder fils/fille en apposition » de la ligne ci-dessus : on neutralise désormais aussi les cas Aros / reconnaissance d'enfant. 4 offsets corrigés cette fois (last-wins dans combined_fr.txt) : `0x1F2ECD5` (Prof. Log → « son enfant »), `0x1F012BD` (« Tu es son enfant ! », variante FD03 du précédent FD02 0x77F1E3 déjà « enfant »), `0x1F01267` (« Es-tu l'enfant du légendaire Dresseur Aros ? »), `0x1EEAD3D` (« mon enfant va adorer cette tarte »). Mécanisme exploité : `19_build…._replace_placeholders` consomme positionnellement les `{…}` non-`{COLOR}` sur les codes EN ; un code EN non consommé (le FD03) est SILENCIEUSEMENT droppé → retirer le `{STR_VAR_2}` (ou le `<0xFD><0x03>` brut de la variante minuscule) suffit à supprimer le buffer. Vérifié sur octets relocalisés (0x79135a, 0x17be19, 0x6e5983, 0x1c49a5 — tous FD02/03 absents). Garde : `tests/test_gender_neutral_child_fr.py` (modèle `test_gender_neutral_aklove_fr.py`).

Voir [[unbound-fr-build-lives-in-gba-translator]] pour la chaîne de build, [[unbound-gender-pronoun-variable-removal]] pour la variante pronom il/elle (Aklove).
