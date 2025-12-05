# Unbound – Traduction ROM GBA (guide)

## Prérequis rapides (débutant)

- Installer Python 3 et créer un venv (déjà présent ici en `.venv`).
- Activer le venv si besoin : `source .venv/bin/activate` (macOS/Linux).
- Avoir le ROM source `totranslate.gba` dans ce dossier.
- Les tables de caractères sont déjà fournies (`charmap_firered.txt`).
- Les scripts sont dans `scripts/`.

## Scripts disponibles (ceux à connaître)

- `extract_text.py` : extrait les textes du ROM GBA en utilisant une charmap.  
  Entrée par défaut : `totranslate.gba`, charmap `charmap_firered.txt`, sortie `extracted_text.txt`.

- `inject_translations.py` : réinjecte un fichier de texte (format `offset: texte`) dans le ROM.  
  Gère le relogement des textes trop longs en zones libres, met à jour les pointeurs. Options :
  - `--text <fichier>` : fichier de traduction (ex. `extracted_text_fr.txt` ou `partial_translated_fr.txt`).
  - `--out <rom>` : ROM de sortie (ex. `totranslate_fr.gba`).
  - `--use-holes` + `--free-map rom_usage.txt` : utilise uniquement les blocs libres (0xFF) listés par `dump_rom_usage.py`.
  - `--no-reuse-old-space` : ne réutilise pas les anciens emplacements (par défaut, ils sont réutilisés).

- `dump_rom_usage.py` : cartographie les zones libres/occupées du ROM (runs de 0xFF) et produit `rom_usage.txt`.

## Dépendances

Environnement Python (3.x) avec les libs standard. Les scripts ci-dessus n’ont pas de dépendances externes.

Pour la traduction automatique (non utilisée dans les étapes ci‑dessus) :  
`translate_chunks_batch.py` utilise `deep_translator` et `requests` (et télécharge des noms de Pokémon depuis le repo veekun).

## Commandes utiles

1) Extraction du texte du ROM (pour éditer/traduire) :
```
.venv/bin/python3 scripts/extract_text.py --rom totranslate.gba --charmap charmap_firered.txt --out extracted_text.txt
```

2) Cartographier les zones libres (à faire une fois) :
```
.venv/bin/python3 scripts/dump_rom_usage.py --rom totranslate.gba --out rom_usage.txt
```

3) Préparer un fichier de traduction :
   - Copier `extracted_text.txt` en `extracted_text_fr.txt`.
   - Traduire la partie droite de chaque ligne (après `: `) en gardant les marqueurs (`\n`, `\p`, `\l`, `{STR_VAR_x}`, `{COLOR}`, etc.).
   - Si certaines lignes doivent rester en anglais, conserver la ligne originale.

### Variante simple avec `make`

- `make extract` : extrait les textes, les découpe en chunks de 250 lignes dans `origin_chuncks/`, copie ces chunks dans `fr_chunks/` si ce dossier est vide, et génère `rom_usage.txt`.
- `make build-fr` : recolle les chunks de `fr_chunks/` dans `combined_fr.txt` puis injecte le résultat dans `totranslate_fr.gba` en utilisant les zones libres décrites dans `rom_usage.txt`.

4) Injection (ex. version partielle stable) :
```
.venv/bin/python3 scripts/inject_translations.py \
  --text partial_translated_fr.txt \
  --out totranslate_partial_fr.gba \
  --use-holes \
  --free-map rom_usage.txt
```

5) Injection complète (si besoin de tout reloger) :
```
.venv/bin/python3 scripts/inject_translations.py \
  --text extracted_text_fr.txt \
  --out totranslate_fr.gba \
  --use-holes \
  --free-map rom_usage.txt
```

6) Tester la ROM générée (`totranslate_fr.gba` ou `totranslate_partial_fr.gba`) dans un émulateur GBA.

## Format du fichier de texte

Chaque ligne est `offset_hex: texte` (ex. `0x1F11888: Bonjour...\p...`).  
Les marqueurs `\n`, `\p`, `\l`, `{STR_VAR_x}`, `{COLOR}` doivent rester intacts.  
L’injecteur reloge uniquement quand le texte encodé ne tient pas à l’offset d’origine.

## Conseils pour éviter les crashs

- Ne modifiez pas les offsets : seule la partie texte après `: ` doit changer.
- Gardez les blocs sensibles en place si une scène plante (laisser en anglais ou raccourcir pour tenir sans relogement).
- Utilisez `--use-holes` + `--free-map rom_usage.txt` pour éviter d’écrire dans des zones critiques.
- Si un texte est trop long, raccourcissez-le (abréviations) plutôt que de supprimer des marqueurs.
