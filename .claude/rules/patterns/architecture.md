# Architecture & disposition

## Dossiers (règle stricte, voir `project-rules.md`)

```
input/roms/     SOURCES en LECTURE SEULE (englishrom.gba, spanishrom.gba) — JAMAIS modifiées
output/         TOUT artefact généré (roms/, extracted/, differences/, analysis/, reports/, translation/)
src/core/       Classes réutilisables (ROMReader, TextCodec, PaddingDetector, SmartReinserter…)
src/extractors/ Scripts d'extraction (NN_*.py)
src/analyzers/  Scripts de diff/analyse (NN_*.py)
src/translators/Scripts de build/traduction (NN_*.py)
src/validators/ Scripts de validation
scripts/        Outils auxiliaires + patchs post-build (patch_*.py, repair_*.py, sync_charmap.py)
scripts/legacy/ Scripts archivés
docs/           Documentation TOUJOURS numérotée NN_NOM.md (recaps/ exemptés)
tests/          unit/, e2e/, e2e-playwright/, benchmarks/, stress/
emulator-web/   Backend émulateur TypeScript (Vitest)
```

### Racine : rien d'autre que l'autorisé
À la racine, **uniquement** : `README.md`, `Makefile`, `pyproject.toml`, `pytest.ini`,
`package.json`/`tsconfig*.json`/`playwright.config.ts` (couche E2E), `.gitignore`,
`combined_fr.txt` (corpus FR). **Aucun** script `.py` ni markdown de travail à la racine.

## DRY — code commun dans `src/core/`

- Interdit : copier-coller de fonctions, code procédural long, fonctions monolithiques.
- Obligatoire : factoriser dans une classe `src/core/`, importer partout.

```python
# src/extractors/01_extract_text.py
from src.core.rom_reader import ROMReader
from src.core.text_codec import TextDecoder
```

## Entrées / sorties

- `input/roms/*.gba` = lecture seule. Tout build écrit dans `output/roms/`
  (`GenedRom-fr.gba`, `GenedRom-es.gba`).
- Nommage des artefacts datés : `YYYY-MM-DD_description.extension`.
- Toujours créer un backup `.bak` avant d'écraser une ROM ; valider les offsets avant
  écriture ; vérifier la taille de la ROM.

## Flux pipeline (Makefile = source de vérité)

```
verify-roms → extract (EN+ES) → diff (offset map) → build-es → validate-es
```
Build FR : `make build-fr` consomme le dernier `output/translation/*_translation_ready.json`
puis enchaîne les patchs post-build `languages/<code>/patches/*.py` / `repair_*.py` /
`repoint_stale_text_pointers.py`. Voir `scripts-pipeline.md`.

## Performance

1. Charger la ROM une seule fois ; réutiliser `ROMReader`/encodeurs.
2. Cache pour les calculs répétitifs (scans de pointeurs).
3. Barres de progression sur les opérations longues.
4. Anti-patterns : recharger la ROM à chaque opération, recréer les encodeurs, scans
   complets multiples.
