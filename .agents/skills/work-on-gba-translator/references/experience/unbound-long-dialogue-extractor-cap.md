---
name: unbound-long-dialogue-extractor-cap
description: Dialogues >1000 octets sont muets dans la pipeline FR (cap extracteur) → restent anglais → patch relocate post-build
metadata:
  node_type: memory
  type: project
  originSessionId: 87018d99-4249-4fd0-a46a-44ab8e13e57b
---

Un dialogue long resté **entièrement en anglais** dans la ROM FR malgré une
traduction correcte dans `combined_fr.txt` au bon offset = piège du **plafond de
l'extracteur**.

`src/extractors/pointer_text_extractor.py` plafonne chaque chaîne à
`max_text_length = 1000` octets : `_read_text` renvoie `None` au-delà. La chaîne
n'entre donc jamais dans `englishrom_texts.json`. Conséquence en chaîne :
`apply_combined_fr.py --extend` n'ajoute QUE les offsets présents dans
l'extraction EN (sinon `missing_english`, skip) → absent de la CSV trilingue →
absent du `*_translation_ready.json` → le builder générique ne le
relocalise/repointe jamais. `apply_inline_overrides_fr.py` le rate aussi (cap
identique côté ES + écriture in-place rejetée `too_long`).

**Détection** : décoder la ROM FR à l'offset (ou via son pointeur). Si EN, vérifier
`len(chaîne EN)` : `rom.find(b'\xff', off) - off`. >1000 = c'est ça. L'offset
n'apparaît pas dans l'extraction ni le JSON (`grep <offset> output/translation/*.json`).

> ⚠️ **RÉGRESSION RÉCURRENTE (B-58 reopen)** : le nom du script a fait l'aller-retour
> `patch_meteorite_dialogue_fr.py` → `patch_long_dialogues_fr.py` (91f80fa, version généralisée 5 cibles)
> → **re-renommé** `patch_meteorite_dialogue_fr.py` par un commit « fix Makefile/CI » (7c3918b) qui
> a RÉIMPORTÉ l'ancienne mouture **mono-cible** (TARGETS={0x7A9A75}) → les 4 autres dialogues
> redevenus anglais à chaque build neuf (la ROM commitée gardait par hasard le FR = artefact périmé).
> Symptôme user : « la traduction n'est pas là » sur la météorite 20 ans. **Le nom canonique actuel
> est `patch_meteorite_dialogue_fr.py`** (référencé par le Makefile) mais il DOIT contenir les 5 cibles.
> En plus, un rewrite volatile de `combined_fr.txt` avait **droppé l'entrée Gardien `0x1f4c2ed`** →
> restaurée (insertion chirurgicale, bloc minuscule). Toujours vérifier `make build-fr` log =
> « Cibles relocalisées : 5 » + décoder les 5 pointeurs vivants.

**Fix généralisé (B-58)** : patch post-build `scripts/patch_meteorite_dialogue_fr.py`
(a porté un temps le nom `patch_long_dialogues_fr.py`), calqué
sur [[unbound-give-cs-object-gain-crash]] / patch_dup_move_descriptions : encode via
les helpers de `apply_inline_overrides_fr` (`_normalize_text` +
`_apply_control_placeholders` + `_read_raw_entry`, donc codes couleur FC01 et sauts
FA/FB corrects), relocalise une copie terminée 0xFF en espace libre
(`FreeSpaceAllocator`, reserved=ES), repointe tous les référents (scan toutes
alignements). Idempotent (skip si plus de pointeur vivant). Branché dans
`make build-fr`. Test `tests/test_patch_meteorite_dialogue.py` (garde CHAQUE cible).

`TARGETS` (offset→sonde FR contiguë) couvre les 5 longs dialogues encore anglais :
`0x7A9A75` météorite 30 ans (`@0x74B0AA`), `0x1EEE8BE` météorite 20 ans (légende
Aros — texte exact du ticket B-58), `0x1F0F004` briefing New Game+, `0x1F8E271`
règles Sables de Combat, `0x1F4C2ED` course aux portails du Gardien de Borrius
(traduit dans ce ticket ; buffer titre FD02 abandonné comme l'ES, nom joueur via
FD01 littéral `<0xFD><0x01>`). **Exclus** : Battle Circus `0x1F8ADD8` + Battle Tower
`0x1F8FBEF` — leur FR tient dans le slot, donc déjà écrits in-place par
apply_inline_overrides (plus de pointeur vers l'anglais à repointer).

**Outil de découverte** : `scripts/scan_long_dialogues.py` (énumère les chaînes-prose
>1000 o, dedup en chaînes maximales, indique si la ROM FR montre encore l'anglais) a
existé puis a été supprimé par 7c3918b ; le recréer si besoin de resynchroniser `TARGETS`.

Voir [[unbound-fr-build-lives-in-gba-translator]] et le skill translating-unbound.
Si d'autres longs dialogues sont signalés anglais : relancer le scan ; ajouter
offset+sonde à `TARGETS` (besoin d'un pointeur vivant repointable + FR dans
combined_fr.txt).
