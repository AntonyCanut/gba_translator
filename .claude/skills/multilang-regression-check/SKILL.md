---
name: multilang-regression-check
description: Use when fixing any bug or patch script in gba_translator — before closing the ticket, verify the fix does not break (or silently already affects) the other registered languages (FR/IT/DE/Indie). Covers deciding whether a change is shared or per-language, which test paths and rebuild targets to run, and how to check a base-ROM quirk against every language.
---

# Vérification de non-régression multilingue

## Pourquoi

`languages/<code>/lang.yaml` déclare FR (dédié, byte-perfect) + IT/DE/Indie
(driver générique `scripts/build_language.py`), mais **le code qui les sert est
partagé** : `src/core/`, `19_build_translated_rom_generic.py`,
`apply_combined_fr.py`, la plupart des scripts de patch. Corriger un bug pour
FR touche donc souvent IT/DE aussi — parfois en le corrigeant sans le savoir,
parfois en le cassant sans le voir (les tests scopés à `tests/unit/fr/` ne
peuvent pas détecter une régression IT/DE). Incidents connus : cellules
Poké Ball/Pokédex déjà en français dans `englishrom.gba` lui-même (IT/DE en
héritent silencieusement), tables de noms réputées « pipeline-only » qui
étaient en fait des tables figées nécessitant un patch miroir par langue.

Détails et checklist complète : `.claude/rules/patterns/multilang-regression.md`.

## Procédure

1. **Classer le fichier touché par le fix** :
   - `languages/fr/combined_fr.txt`, `patch_*_fr.py`, tout fichier `*_fr.py` /
     `*_fr.json` → **per-language FR**. Regarde immédiatement si l'équivalent
     `languages/it/combined_it.txt` / `languages/de/combined_de.txt` ou
     `patch_*_it.py` / `patch_*_de.py` a le même offset ou le même défaut.
   - `src/core/`, `scripts/build_language.py`,
     `19_build_translated_rom_generic.py`, un script de patch sans suffixe
     `_<code>` (reçoit `--language` en argument) → **partagé**. Toute langue
     buildable est concernée.
   - Un offset ROM précis découvert pendant l'investigation (table figée,
     cellule non atteignable par le pipeline) → **quirk de la ROM de base**,
     indépendant du code : vérifie-le langue par langue (§4).

2. **Fix per-language (FR seul)** : grep l'offset dans
   `languages/it/combined_it.txt` et `languages/de/combined_de.txt`. Présent →
   le même bug (ou son absence) peut exister côté IT/DE ; décide s'il faut un
   patch miroir ou un ticket dédié (scope large → follow-up ticket, correctif
   local → fixe-le tout de suite). Absent des deux → le fix reste FR-only,
   mais note-le dans le message de commit pour que ce soit traçable.

3. **Fix partagé** : lance la suite complète, jamais un sous-dossier —
   ```bash
   make test-python      # couvre déjà tests/unit/{fr,it,de,en} + tests/e2e/{fr,it,de,es}
   ```
   Si le changement touche la génération de ROM (pas seulement une donnée de
   traduction) :
   ```bash
   make build-it && make build-de
   python3 -m pytest tests/unit/it tests/unit/de tests/e2e/it tests/e2e/de -q
   ```
   Les tests unitaires utilisent des fixtures synthétiques ; un rebuild réel
   est le seul moyen de détecter une régression LZ77 / pointeur / table figée
   qui n'apparaîtrait qu'en ROM complète.

4. **Quirk de la ROM de base** : décoder l'offset dans les trois ROMs
   buildées pour comparer (`ROMReader` + `TextDecoder` — `src/core/`) :
   ```python
   from src.core.rom_reader import ROMReader
   from src.core.text_codec import TextDecoder
   for path in ["output/roms/GenedRom-fr.gba", "output/roms/GenedRom-it.gba",
                "output/roms/GenedRom-de.gba"]:
       rom = ROMReader(path); rom.load()
       print(path, TextDecoder.decode_pokemon(rom.read_bytes(0x<offset>, 40)))
   ```
   Si les trois langues partagent le défaut, corrige-les ensemble ou ouvre un
   ticket qui couvre les trois — ne ferme pas le ticket FR en laissant IT/DE
   avec le même bug non tracé.

5. **Code partagé qui se spécialise en dur pour FR** : si tu ajoutes ou
   modifies `src/core/` ou `scripts/build_language.py`, grep `_fr` / `"fr"`
   dans ton diff. Un `if language == "fr"` non documenté dans `lang.yaml` est
   presque toujours un bug latent pour IT/DE — généralise plutôt que de
   spécialiser.

## Sortie attendue

Avant de clore le ticket : indiquer explicitement dans le résumé quelles
langues ont été testées/rebuild (pas seulement FR), et si une langue a été
laissée de côté, pourquoi (ex: `combined_it.txt`/`combined_de.txt` n'ont pas
cet offset → aucun impact possible).
