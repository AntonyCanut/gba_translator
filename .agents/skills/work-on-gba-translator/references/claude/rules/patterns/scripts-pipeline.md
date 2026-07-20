# Scripts & pipeline

## Scripts numérotés `src/`

Les scripts d'étape sont **numérotés par ordre d'exécution** dans leur sous-dossier :

```
src/extractors/pointer_text_extractor.py   # extracteur principal
src/analyzers/11_pointer_text_diff.py
src/translators/19_build_translated_rom_generic.py
src/translators/28_export_trilingual_csv.py
src/validators/text_range_validator.py
```

- Un script = une étape. Il `import` les classes de `src/core/`, ne duplique pas la logique.
- Point d'entrée via `argparse` + `def main()` + `if __name__ == "__main__": main()`.
- Les chemins d'entrée/sortie sont des **arguments**, pas des constantes en dur
  (ex. `--source`, `--output`, `--offset-map`, `--translations`).

## `scripts/` — outils & patchs post-build

`scripts/` contient les outils auxiliaires et les **patchs post-build** appliqués après
le build générique (ordre imposé par `make build-fr`) :

```
patch_font_fr.py           # police FR
patch_fixed_table_names.py # noms de tables figés
patch_time_format_fr.py    # date/heure FR (code Thumb patché)
apply_inline_overrides_fr.py
repair_stable_lz77_blocks.py / repair_localized_lz77_blocks.py
repoint_stale_text_pointers.py
patch_pokedex_fr.py        # re-wrap + relocalise les fiches Pokédex
sync_charmap.py            # synchronise la charmap Python -> TypeScript
```

Chaque patch prend `--rom <cible>` (et souvent `--source`, `--translations`) et modifie
la ROM **de sortie** en place. Ajoute un nouveau patch en respectant cette signature et
insère-le au bon rang dans la recette `build-fr` du `Makefile`.

## Chaîne de traduction FR

```
combined_fr.txt  →  CSV trilingue  →  *_translation_ready.json  →  make build-fr
```
Les trois sources (combined / CSV / json) doivent rester synchronisées. Pour le CSV
trilingue : insertion chirurgicale ligne à ligne, **jamais** `csv.writer` (qui reformate
les ~30k lignes et casse les champs contenant CRLF/LF).

## Makefile = orchestrateur

Toute commande passe par une cible `make` (`make pipeline`, `make build-fr`,
`make test`, `make sync-charmap`). N'invoque un script Python à la main que pour le
debug ; le chemin officiel est le `Makefile`.
