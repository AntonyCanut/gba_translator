---
name: unbound-battle-defeat-end-strings
description: "Messages de fin de combat en DÉFAITE (0xA4C689 whiteout, 0xA4C6FD perte vs dresseur) restaient anglais — trop longs → droppés (région moteur non repointée) ; fix = recadrer en place dans le budget du slot EN + pause <0xFC><0x09>"
metadata:
  node_type: memory
  type: project
  originSessionId: 52ba7b9f-68ca-4e74-9adb-e3b95b881bd8
---

Save « POKEMON FIRE_BPRE-48.sav » (map 3,77) = combat dresseur auto au reload
contre **Karatéka Mike** (Black Belt, Férosinge/Mankey + Machoc). En PERDANT, la
« phrase de fin » s'affichait en anglais et filait sans pause → bug user
« rien ne correspond / pas le temps de lire / traduction pas la bonne ».

Deux strings de la table gBattleStringsTable (région moteur, **non repointée** par
la pipeline → un FR trop long est droppé et le slot garde les octets ANGLAIS) :
- **0xA4C689** whiteout « You have no more Pokémon\nthat can fight!{PAGE} » — slot 42 o
- **0xA4C6FD** perte dresseur « ...{PAGE}You lost against\n<FD1C> <FD1D>!<FC09> » — slot 67 o

Le win-path était déjà OK (0xA4C670 « Tu gagnes ¥X !<FC09> », cf
[[unbound-brace-control-token-relocation-literal]]). SEULES ces 2 strings défaite
restaient anglaises (scan EN-vs-FR built rom).

Fix = injection **en place**, FR recadré dans le budget (comme Méga-Cuff
[[unbound-mega-cuff-reaction-strings]]) :
- 0xA4C689 → « Plus de Pokémon en état\nde combattre !\p » (39 o ≤ 41)
- 0xA4C6FD → « Plus de Pokémon en état\nde combattre !\pTu perds face à\n<0xFD><0x1C> <0xFD><0x1D> !<0xFC><0x09> » (64 o ≤ 66)
Tokens BRUTS obligatoires : `<0xFD><0x1C>`/`<0xFD><0x1D>` (classe/nom), `<0xFC><0x09>`
(pause) — les formes accolade {B_TRAINER1_CLASS}/{PAUSE_UNTIL_PRESS} ne sont PAS
développées → écrites littéralement + débordent.

PIÈGE build rencontré : `09_csv_to_json_v2.py` SANS l'arg CSV explicite auto-détecte
le mauvais `*_template.csv` → JSON vide (205 o) → build « Traductions: 0 ». TOUJOURS
`python3 src/translators/09_csv_to_json_v2.py output/translation/2026-01-15_trilingual_translation.csv --allow-too-long`.
Aussi : `apply_combined_fr.py --extend` plante si `englishrom_texts.json` absent du
worktree (`return 1` jette l'update CSV en mémoire) ; pour des offsets DÉJÀ dans le
CSV, lancer sans `--extend` suffit.

Tests : `tests/test_battle_defeat_pause_fr.py` (source) +
`tests/e2e/test_battle_defeat_messages_fr.py` (ROM bâtie : EN reste anglais, FR en
place, ≤ slot, finit FC09). Sondé en jeu via cooker EmulatorBridge + gDisplayedStringBattle
0x0202298C (le combat EST bien Karatéka Mike). Commits 50c9ee0/15f1a25/dc9262c.
